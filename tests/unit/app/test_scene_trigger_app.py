"""Unit tests for the shared trigger registration ``SceneTriggerApp`` moved into.

Coverage targets
----------------
1.  ``LocalApp`` registers exactly these 24 trigger names: the 19 shared ones
    defined on ``SceneTriggerApp`` plus its own five local-only ones.
    Neither a missing nor a doubled registration passes this.
2.  ``LocalApp`` seeds ``rendering_mode`` into server state as ``"client"``
    before the server starts.
3.  ``set_geometry_highlight`` hands the coordinator the parsed pick.
4.  ``set_pixel_scale`` hands the coordinator the parsed scale, and a scale
    that is not positive never reaches it.
5.  ``pick_geometry_in_view`` hands the server picker the client's pixel,
    window size, camera and mode, and returns its pick dumped by alias; a
    window with no width never reaches the picker.
6.  ``pick_part_in_view`` hands the server picker the client's pixel,
    window size and camera, and returns its node id.

The coordinator and payload behaviour of the other 18 shared triggers is
already pinned, trigger by trigger, in ``test_local_app.py`` and its sibling
modules; this module does not restate that.
"""

from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.runtime.picking.geometry_pick import EdgePick
from ansys.visor.viewer.vtk.picking.part_cell_hit import PickView

# The exact 24 trigger names LocalApp registers: the 19 names shared with
# every rendering mode, plus LocalApp's own five local-only ones.  Written
# out by hand, not derived from the production trigger list, so a missing or
# a doubled registration fails this rather than following along.
LOCAL_APP_TRIGGER_NAMES = sorted(
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
        "pick_geometry_in_view",
        "pick_part_in_view",
        "perf_report_wasm",
        "perf_report_server_update",
        "set_pixel_scale",
    ]
)


class MockController:
    """Minimal trame controller stand-in that records added handlers."""

    def __init__(self):
        self.handlers = {}
        self.add_call_count = 0

    def add(self, event):
        self.add_call_count += 1

        def decorator(fn):
            self.handlers[event] = fn
            return fn

        return decorator


@pytest.fixture
def mock_server():
    """Provide a mock Trame server with real dict-backed state."""
    server = MagicMock()
    server.controller = MockController()
    server.http_headers.set_header = MagicMock()
    server.name = "TestServer"
    server._www = None
    server.state = {}
    return server


def test_local_app_registers_exactly_these_triggers(mock_server):
    """The registered trigger names are exactly the hand-written 23, sorted.

    A missing registration shortens the list; a doubled one (``@TrameApp()``
    on both the base and the leaf) duplicates a name in
    ``mock_server.trigger.call_args_list``.  ``sorted`` on the actual names
    makes either failure visible against the hand-written literal.
    """
    LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        pick_geometry_in_view=MagicMock(),
        pick_part_in_view=MagicMock(),
    )

    names = sorted(call.args[0] for call in mock_server.trigger.call_args_list)

    assert names == LOCAL_APP_TRIGGER_NAMES


def test_local_app_seeds_rendering_mode_client(mock_server):
    """``rendering_mode`` is written into state as ``"client"`` before start."""
    LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        pick_geometry_in_view=MagicMock(),
        pick_part_in_view=MagicMock(),
    )

    assert mock_server.state["rendering_mode"] == "client"


def test_set_geometry_highlight_forwards_the_parsed_pick(mock_server):
    """The wire payload, keyed by alias, reaches the coordinator as the one pick model it validates as."""
    api = MagicMock(name="scene_mutation_api")
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        scene_mutation_api=api,
        pick_geometry_in_view=MagicMock(),
        pick_part_in_view=MagicMock(),
    )

    result = app.set_geometry_highlight(
        {
            "pick": {
                "found": True,
                "mode": "edge",
                "pointA": [0.0, 0.0, 0.0],
                "pointB": [3.0, 4.0, 0.0],
                "edgeLength": 5.0,
            }
        }
    )

    assert result is None
    api.set_geometry_highlight.assert_called_once_with(
        EdgePick(point_a=[0.0, 0.0, 0.0], point_b=[3.0, 4.0, 0.0], length=5.0)
    )


def test_set_pixel_scale_forwards_the_parsed_scale(mock_server):
    """The client's device pixel ratio reaches the coordinator as the float it sent."""
    api = MagicMock(name="scene_mutation_api")
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        scene_mutation_api=api,
        pick_geometry_in_view=MagicMock(),
        pick_part_in_view=MagicMock(),
    )

    result = app.set_pixel_scale({"scale": 2.0})

    assert result is None
    api.set_pixel_scale.assert_called_once_with(2.0)


@pytest.mark.parametrize("scale", [0.0, -1.0])
def test_set_pixel_scale_ignores_a_scale_that_is_not_positive(mock_server, scale):
    """A scale of zero or less would draw no highlight at all, so it never reaches the coordinator."""
    api = MagicMock(name="scene_mutation_api")
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        scene_mutation_api=api,
        pick_geometry_in_view=MagicMock(),
        pick_part_in_view=MagicMock(),
    )

    app.set_pixel_scale({"scale": scale})

    api.set_pixel_scale.assert_not_called()


# The camera record and the window, as the client sends them for a pick.
_PICK_CAMERA = {
    "position": [1.0, 2.0, 3.0],
    "focalPoint": [4.0, 5.0, 6.0],
    "viewUp": [0.0, 0.0, 1.0],
    "clippingRange": [0.5, 50.0],
    "parallelProjection": False,
    "viewAngle": 25.0,
    "parallelScale": 7.0,
}


def test_pick_geometry_in_view_forwards_a_pick_view_and_dumps_by_alias(mock_server):
    """The client's pixel, window size, camera and mode reach the server picker; its pick returns keyed by alias."""
    picker = MagicMock(
        name="pick_geometry_in_view",
        return_value=EdgePick(point_a=[0.0, 0.0, 0.0], point_b=[3.0, 4.0, 0.0], length=5.0),
    )
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        pick_geometry_in_view=picker,
        pick_part_in_view=MagicMock(),
    )

    result = app.pick_geometry_in_view(
        {"x": 150, "y": 100, "width": 600, "height": 400, "mode": "edge", "camera": _PICK_CAMERA}
    )

    picker.assert_called_once_with(
        PickView(
            camera_state=VisorCameraState(
                position=[1.0, 2.0, 3.0],
                focal_point=[4.0, 5.0, 6.0],
                view_up=[0.0, 0.0, 1.0],
                clipping_range=[0.5, 50.0],
                parallel_projection=False,
                view_angle=25.0,
                parallel_scale=7.0,
            ),
            width=600,
            height=400,
        ),
        150,
        100,
        "edge",
    )
    assert result == {
        "found": True,
        "mode": "edge",
        "pointA": [0.0, 0.0, 0.0],
        "pointB": [3.0, 4.0, 0.0],
        "edgeLength": 5.0,
    }


def test_pick_geometry_in_view_rejects_a_zero_width(mock_server):
    """A window with no width has no pixel to pick, so the server picker is never asked."""
    picker = MagicMock(name="pick_geometry_in_view")
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        pick_geometry_in_view=picker,
        pick_part_in_view=MagicMock(),
    )

    result = app.pick_geometry_in_view(
        {"x": 0, "y": 0, "width": 0, "height": 400, "mode": "vertex", "camera": _PICK_CAMERA}
    )

    assert result is None
    picker.assert_not_called()


def test_pick_part_in_view_forwards_a_pick_view_and_returns_the_node(mock_server):
    """The client's pixel, window size and camera reach the server picker; its node id returns unchanged."""
    picker = MagicMock(name="pick_part_in_view", return_value=7)
    app = LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
        pick_geometry_in_view=MagicMock(),
        pick_part_in_view=picker,
    )

    result = app.pick_part_in_view({"x": 150, "y": 100, "width": 600, "height": 400, "camera": _PICK_CAMERA})

    picker.assert_called_once_with(
        PickView(
            camera_state=VisorCameraState(
                position=[1.0, 2.0, 3.0],
                focal_point=[4.0, 5.0, 6.0],
                view_up=[0.0, 0.0, 1.0],
                clipping_range=[0.5, 50.0],
                parallel_projection=False,
                view_angle=25.0,
                parallel_scale=7.0,
            ),
            width=600,
            height=400,
        ),
        150,
        100,
    )
    assert result == 7
