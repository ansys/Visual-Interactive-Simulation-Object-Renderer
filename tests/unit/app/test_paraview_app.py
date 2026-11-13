"""Unit tests for ``ParaviewApp``: its trigger set, the rendering mode it
reports and the stream quality it binds, and the trame-rca scheduler
behaviour that quality relies on.

Everything else is ``ServerApp``'s and is pinned in ``test_server_app.py``.
``RemoteControlledArea`` is replaced by a double, so the app tests build no
real render scheduler; the scheduler test builds one over a counting area.
"""

import asyncio
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from trame_rca.schedulers import RcaImageRenderScheduler

from ansys.visor.viewer.app.trame.paraview_app import ParaviewApp
from ansys.visor.viewer.core.visor_enums import RenderingMode

# The exact 22 trigger names, each registered once.  Written out by hand, not
# derived from the production trigger list.
PARAVIEW_APP_TRIGGER_NAMES = sorted(
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


def _build(mock_server, rca_window=None, bridge=None):
    return ParaviewApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        trame_logger=None,
        scene_mutation_api=MagicMock(),
        pick_part_at=MagicMock(),
        pick_geometry_at=MagicMock(),
        set_dark_mode=MagicMock(),
        rca_window=rca_window if rca_window is not None else MagicMock(name="rca_window"),
        bridge=bridge if bridge is not None else MagicMock(name="bridge"),
    )


def test_paraview_app_registers_each_trigger_once(mock_server, area_cls):
    """The registered trigger names are exactly the hand-written 22, none twice."""
    _build(mock_server)

    names = sorted(call.args[0] for call in mock_server.trigger.call_args_list)

    assert names == PARAVIEW_APP_TRIGGER_NAMES


def test_paraview_app_seeds_rendering_mode_paraview(mock_server, area_cls):
    """``rendering_mode`` is written into state as ``"paraview"`` before start."""
    _build(mock_server)

    assert mock_server.state["rendering_mode"] == "paraview"


def test_paraview_app_reports_paraview_mode(mock_server, area_cls):
    assert _build(mock_server).rendering_mode is RenderingMode.PARAVIEW


def test_paraview_app_streams_every_frame_at_one_quality(mock_server, area_cls):
    """When the server is ready, the view handler is built with equal interactive and still qualities."""
    rca_window = MagicMock(name="rca_window")
    _build(mock_server, rca_window=rca_window)
    area = area_cls.return_value

    for handler in mock_server.controller.handlers["on_server_ready"]:
        handler()

    area.create_view_handler.assert_called_once_with(
        rca_window,
        encoder="jpeg",
        target_fps=30.0,
        interactive_quality=90,
        still_quality=90,
    )


class _CountingArea:
    """A remote-controlled area that counts its captures and returns one literal 1 x 1 frame."""

    def __init__(self) -> None:
        self.captures = 0

    @property
    def img_cols_rows(self):
        self.captures += 1
        return np.zeros((1, 1, 3), dtype=np.uint8), 1, 1

    def process_resize_event(self, width: int, height: int) -> None:
        pass

    def process_interaction_event(self, event: dict) -> None:
        pass


def test_trame_rca_makes_no_still_pass_at_equal_qualities():
    """At equal qualities one render request captures one frame, and none follows once requests stop.

    trame-rca documents only that a frame "may be re-encoded at higher
    quality shortly afterwards"; skipping that pass at equal qualities is
    its undocumented behaviour, pinned here.  At unequal qualities the same
    request captures twice, five frame periods (50 ms at 100 fps) apart.
    """
    area = _CountingArea()

    async def request_one_frame_and_wait() -> None:
        scheduler = RcaImageRenderScheduler(
            area, target_fps=100.0, interactive_quality=90, still_quality=90, rca_encoder="jpeg"
        )
        scheduler.schedule_render()
        await asyncio.sleep(0.5)
        await scheduler.close()

    asyncio.run(request_one_frame_and_wait())

    assert area.captures == 1
