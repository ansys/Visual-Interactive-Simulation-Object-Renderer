"""Unit tests for ``ParaviewApp``: its trigger set and the rendering mode it
reports.

Everything else is ``ServerApp``'s and is pinned in ``test_server_app.py``.
``RemoteControlledArea`` is replaced by a double, so nothing here builds a
real render scheduler.
"""

from unittest.mock import MagicMock, patch

import pytest

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


def _build(mock_server):
    return ParaviewApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        trame_logger=None,
        scene_mutation_api=MagicMock(),
        pick_part_at=MagicMock(),
        pick_geometry_at=MagicMock(),
        set_dark_mode=MagicMock(),
        rca_window=MagicMock(name="rca_window"),
        bridge=MagicMock(name="bridge"),
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
