"""Unit tests for the shared trigger registration ``SceneTriggerApp`` moved into.

Coverage targets
----------------
1.  ``LocalApp`` registers exactly the 21 trigger names it registered before
    the move: the 18 shared ones defined on ``SceneTriggerApp`` plus its own
    three local-only ones.  Neither a missing nor a doubled registration
    passes this.
2.  ``LocalApp`` seeds ``rendering_mode`` into server state as ``"client"``
    before the server starts.

The coordinator and payload behaviour of the 18 shared triggers is already
pinned, trigger by trigger, in ``test_local_app.py`` and its sibling modules;
this module does not restate that.
"""

from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp

# The exact 21 trigger names LocalApp registers: the 18 names shared with
# every rendering mode, plus LocalApp's own three local-only ones.  Written
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
        "pick_geometry",
        "perf_report_wasm",
        "perf_report_server_update",
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
    """The registered trigger names are exactly the hand-written 21, sorted.

    A missing registration shortens the list; a doubled one (``@TrameApp()``
    on both the base and the leaf) duplicates a name in
    ``mock_server.trigger.call_args_list``.  ``sorted`` on the actual names
    makes either failure visible against the hand-written literal.
    """
    LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
    )

    names = sorted(call.args[0] for call in mock_server.trigger.call_args_list)

    assert names == LOCAL_APP_TRIGGER_NAMES


def test_local_app_seeds_rendering_mode_client(mock_server):
    """``rendering_mode`` is written into state as ``"client"`` before start."""
    LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        standalone=True,
    )

    assert mock_server.state["rendering_mode"] == "client"

