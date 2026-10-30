"""Unit tests for ``ServerApp``: its trigger set, its mode seed, its two
server-only triggers, the stream binding made when the server is ready, and the
render-window size a client's size report gives.

The shared triggers' coordinator and payload behaviour is pinned in
``test_local_app.py`` and its sibling modules and is not restated here.
``RemoteControlledArea`` is replaced by a double, so nothing here builds a
real render scheduler; the real stream is exercised in
``tests/integration/test_server_stream.py``.
"""

import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from trame_rca.view_adapter import RcaViewAdapter

from ansys.visor.viewer.app.trame.server_app import ServerApp
from ansys.visor.viewer.models.runtime.picking.geometry_pick import EdgePick
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow

# The exact 22 trigger names ServerApp registers: the 19 shared with every
# rendering mode, plus its own three.  Written out by hand, not derived from the
# production trigger list.
SERVER_APP_TRIGGER_NAMES = sorted(
    [
        "get_visor_scene_details_json",
        "set_part_visibility",
        "set_part_opacity",
        "set_part_diffuse_color",
        "set_part_selected",
        "set_part_color_variable",
        "clear_part_color_variable",
        "set_variable_range",
        "sync_camera",
        "set_cross_section_visibility",
        "set_edges_visible",
        "set_bounding_box_visibility",
        "set_projection",
        "sync_cross_section_plane",
        "set_panel_top_left_panel_collapsed",
        "set_panel_top_right_panel_collapsed",
        "set_panel_top_right_legend_collapsed",
        "set_panel_top_right_tab_index",
        "set_geometry_highlight",
        "pick_part_at",
        "pick_geometry_at",
        "set_dark_theme",
    ]
)


class MockController:
    """Trame controller stand-in that keeps every handler added per event."""

    def __init__(self):
        self.handlers = {}

    def add(self, event):
        def decorator(fn):
            self.handlers.setdefault(event, []).append(fn)
            return fn

        return decorator


@pytest.fixture
def mock_server():
    """A mock trame server with real dict-backed state."""
    server = MagicMock()
    server.controller = MockController()
    server.http_headers.set_header = MagicMock()
    server.name = "TestServer"
    server._www = None
    server.state = {}
    return server


@pytest.fixture
def area_cls():
    """The RemoteControlledArea class as ServerApp sees it, replaced by a double."""
    with patch("ansys.visor.viewer.app.trame.server_app.RemoteControlledArea") as cls:
        yield cls


class _Recorder:
    """A callable that records its arguments and returns a fixed value."""

    def __init__(self, result=None):
        self.calls = []
        self._result = result

    def __call__(self, *args):
        self.calls.append(args)
        return self._result


def _build(
    mock_server, pick_part_at=None, pick_geometry_at=None, set_dark_mode=None, rca_window=None, bridge=None
):
    return ServerApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        trame_logger=None,
        scene_mutation_api=MagicMock(),
        pick_part_at=pick_part_at if pick_part_at is not None else _Recorder(),
        pick_geometry_at=pick_geometry_at if pick_geometry_at is not None else _Recorder(),
        set_dark_mode=set_dark_mode if set_dark_mode is not None else _Recorder(),
        rca_window=rca_window if rca_window is not None else MagicMock(name="rca_window"),
        bridge=bridge if bridge is not None else MagicMock(name="bridge"),
    )


def test_server_app_registers_exactly_these_triggers(mock_server, area_cls):
    """The registered trigger names are exactly the hand-written 22, sorted."""
    _build(mock_server)

    names = sorted(call.args[0] for call in mock_server.trigger.call_args_list)

    assert names == SERVER_APP_TRIGGER_NAMES


def test_server_app_seeds_rendering_mode_server(mock_server, area_cls):
    """``rendering_mode`` is written into state as ``"server"`` before start."""
    _build(mock_server)

    assert mock_server.state["rendering_mode"] == "server"


def test_pick_part_at_forwards_and_returns(mock_server, area_cls):
    """The pixel reaches the injected pick, and its node id is the trigger's return."""
    pick = _Recorder(result=7)
    app = _build(mock_server, pick_part_at=pick)

    result = app.pick_part_at({"x": 3, "y": 4})

    assert result == 7
    assert pick.calls == [(3, 4)]


def test_pick_part_at_rejects_bad_payload(mock_server, area_cls):
    """A payload missing a coordinate is a logged no-op: nothing is picked."""
    pick = _Recorder(result=7)
    app = _build(mock_server, pick_part_at=pick)

    result = app.pick_part_at({"x": 1})

    assert result is None
    assert pick.calls == []


def test_pick_geometry_at_forwards_and_dumps_by_alias(mock_server, area_cls):
    """The pixel and mode reach the injected pick, and its result is returned in the wire's alias form."""
    pick = _Recorder(result=EdgePick(point_a=[0.0, 1.0, 2.0], point_b=[3.0, 4.0, 5.0], length=6.0))
    app = _build(mock_server, pick_geometry_at=pick)

    result = app.pick_geometry_at({"x": 3, "y": 4, "mode": "edge"})

    assert result == {
        "found": True,
        "mode": "edge",
        "pointA": [0.0, 1.0, 2.0],
        "pointB": [3.0, 4.0, 5.0],
        "edgeLength": 6.0,
    }
    assert pick.calls == [(3, 4, "edge")]


def test_pick_geometry_at_rejects_unknown_mode(mock_server, area_cls):
    """A mode outside vertex, edge and face is a logged no-op: nothing is picked."""
    pick = _Recorder(result=EdgePick(point_a=[0.0, 1.0, 2.0], point_b=[3.0, 4.0, 5.0], length=6.0))
    app = _build(mock_server, pick_geometry_at=pick)

    result = app.pick_geometry_at({"x": 3, "y": 4, "mode": "bogus"})

    assert result is None
    assert pick.calls == []


def test_set_dark_theme_calls_set_dark_mode(mock_server, area_cls):
    """The client's theme reaches the injected set_dark_mode."""
    set_dark_mode = _Recorder()
    app = _build(mock_server, set_dark_mode=set_dark_mode)

    app.set_dark_theme({"dark": True})

    assert set_dark_mode.calls == [(True,)]


def test_set_dark_theme_rejects_bad_payload(mock_server, area_cls):
    """A payload without ``dark`` is a logged no-op: the theme is not changed."""
    set_dark_mode = _Recorder()
    app = _build(mock_server, set_dark_mode=set_dark_mode)

    app.set_dark_theme({})

    assert set_dark_mode.calls == []


def test_server_ready_builds_handler_and_binds(mock_server, area_cls):
    """When the server is ready, the view handler is built over the RCA window
    with the JPEG encoder, and the bridge is bound to that handler."""
    rca_window = MagicMock(name="rca_window")
    bridge = MagicMock(name="bridge")
    _build(mock_server, rca_window=rca_window, bridge=bridge)
    area = area_cls.return_value

    for handler in mock_server.controller.handlers["on_server_ready"]:
        handler()

    area.create_view_handler.assert_called_once_with(
        rca_window,
        encoder="jpeg",
        target_fps=30.0,
        interactive_quality=60,
        still_quality=90,
    )
    bridge.bind.assert_called_once_with(area.create_view_handler.return_value)


class _RecordingScheduler:
    """A render scheduler over one area that only counts render requests."""

    def __init__(self, rca) -> None:
        self.rca = rca
        self.renders = 0

    def set_push_callback(self, _callback) -> None:
        pass

    def schedule_render(self) -> None:
        self.renders += 1


class _SizeRecordingRenderer:
    """The part of a ServerRenderer the RCA window uses; records each viewport size."""

    background_rgb = (0.0, 0.0, 0.0)

    def __init__(self) -> None:
        self.sizes: list[tuple[int, int]] = []

    def set_viewport_size(self, width: int, height: int) -> None:
        self.sizes.append((width, height))


class _StillCapture:
    """A capture that returns one literal frame and accepts events."""

    img_cols_rows = (np.zeros((1, 1, 3), dtype=np.uint8), 1, 1)

    def process_interaction_event(self, _event: dict) -> None:
        pass


def test_client_resize_sizes_render_window(mock_server, area_cls):
    """A client size of 401 x 301 CSS px at pixel ratio 1.5 gives the render
    window 601 x 451 device pixels at the next frame: the handler ServerApp
    builds neither rescales nor caps the size."""
    renderer = _SizeRecordingRenderer()
    rca_window = VisorRcaWindow(_StillCapture(), renderer, threading.RLock(), lambda: None)
    bridge = MagicMock(name="bridge")
    area_cls.return_value.create_view_handler.side_effect = lambda window, **_: RcaViewAdapter(
        window, "view", scheduler=_RecordingScheduler(window)
    )
    _build(mock_server, rca_window=rca_window, bridge=bridge)
    for handler in mock_server.controller.handlers["on_server_ready"]:
        handler()
    view_handler = bridge.bind.call_args.args[0]

    view_handler.update_size("ServerCanvas", {"w": 401, "h": 301, "p": 1.5})
    rca_window.img_cols_rows

    assert renderer.sizes == [(601, 451)]

