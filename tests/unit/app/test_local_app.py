"""Unit tests for LocalApp's per-part visual-state triggers.

Coverage targets
----------------
1.  Each of the six triggers unpacks its payload and delegates to the
    identically-named method on the injected coordinator object, returning
    ``None``.
2.  ``association`` is parsed at this boundary into a ``VisorVtkVariableType``
    member -- by exact value lookup, never by upper-casing -- and a value that
    is not a member is a logged no-op that delegates nothing.
3.  ``variableId`` crosses opaquely: forwarded byte-identically, never parsed.
4.  ``diffuseRgb`` of ``None`` is forwarded as ``None`` (a clear), and
    ``set_part_selected`` carries no colour at all.
5.  With no coordinator injected, every trigger is a logged no-op.

The coordinator is a single MagicMock standing in for the injected object;
what each trigger does with the values it forwards is asserted in
tests/unit/vtk/scene/test_base.py against the registry and the VTK objects.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType

TRIGGER_NAMES = [
    "set_part_visibility",
    "set_part_opacity",
    "set_part_diffuse_color",
    "set_part_selected",
    "set_part_color_variable",
    "clear_part_color_variable",
]

# One payload per trigger, written out literally rather than built from the
# production code's key names.
PAYLOADS = {
    "set_part_visibility": {"nodeId": 7, "visible": False},
    "set_part_opacity": {"nodeId": 7, "opacity": 0.25},
    "set_part_diffuse_color": {"nodeId": 7, "diffuseRgb": [1.0, 0.0, 0.0]},
    "set_part_selected": {"nodeId": 7, "selected": True},
    "set_part_color_variable": {
        "nodeId": 7,
        "variableId": "POINT::pressure::1",
        "association": "POINT",
        "arrayName": "pressure",
        "component": 0,
        "min": 0.0,
        "max": 49.0,
    },
    "clear_part_color_variable": {"nodeId": 7},
}


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
    """Provide a mock Trame server."""
    server = MagicMock()
    server.controller = MockController()
    server.http_headers.set_header = MagicMock()
    server.name = "TestServer"
    server._www = None
    return server


@pytest.fixture
def api():
    """Stand-in for the injected per-part coordinator object."""
    return MagicMock(name="scene_part_state_api")


@pytest.fixture
def app(mock_server, api):
    """LocalApp with a coordinator injected."""
    return LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        handle_save_state_response=MagicMock(),
        standalone=True,
        scene_part_state_api=api,
    )


@pytest.fixture
def app_without_api(mock_server):
    """LocalApp with no coordinator injected."""
    return LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        handle_save_state_response=MagicMock(),
        standalone=True,
    )


# ===========================================================================
# Delegation
# ===========================================================================

def test_set_part_visibility_delegates_payload_values(app, api):
    """nodeId and visible reach the coordinator unchanged."""
    app.set_part_visibility({"nodeId": 7, "visible": False})

    api.set_part_visibility.assert_called_once_with(7, False)


def test_set_part_opacity_delegates_payload_values(app, api):
    """nodeId and opacity reach the coordinator unchanged."""
    app.set_part_opacity({"nodeId": 7, "opacity": 0.25})

    api.set_part_opacity.assert_called_once_with(7, 0.25)


def test_set_part_diffuse_color_delegates_payload_values(app, api):
    """nodeId and diffuseRgb reach the coordinator unchanged."""
    app.set_part_diffuse_color({"nodeId": 7, "diffuseRgb": [1.0, 0.0, 0.0]})

    api.set_part_diffuse_color.assert_called_once_with(7, [1.0, 0.0, 0.0])


def test_set_part_diffuse_color_forwards_none_as_a_clear(app, api):
    """A None colour is forwarded as None; no default is substituted here."""
    app.set_part_diffuse_color({"nodeId": 7, "diffuseRgb": None})

    api.set_part_diffuse_color.assert_called_once_with(7, None)


def test_set_part_selected_delegates_payload_values(app, api):
    """nodeId and selected reach the coordinator unchanged."""
    app.set_part_selected({"nodeId": 7, "selected": True})

    api.set_part_selected.assert_called_once_with(7, True)


def test_set_part_selected_carries_no_colour(app, api):
    """The selection trigger passes exactly two arguments -- no colour."""
    app.set_part_selected({"nodeId": 7, "selected": True})

    call = api.set_part_selected.call_args
    assert len(call.args) == 2
    assert call.kwargs == {}


def test_set_part_color_variable_delegates_payload_values(app, api):
    """Every colour-variable field reaches the coordinator in contract order."""
    app.set_part_color_variable(
        {
            "nodeId": 7,
            "variableId": "POINT::pressure::1",
            "association": "POINT",
            "arrayName": "pressure",
            "component": 0,
            "min": 0.0,
            "max": 49.0,
        }
    )

    api.set_part_color_variable.assert_called_once_with(
        7, "POINT::pressure::1", VisorVtkVariableType.POINT, "pressure", 0, 0.0, 49.0
    )


def test_set_part_color_variable_parses_point_association_to_the_enum_member(app, api):
    """'POINT' arrives as the POINT member itself, not as a string."""
    app.set_part_color_variable(
        {
            "nodeId": 7,
            "variableId": "POINT::pressure::1",
            "association": "POINT",
            "arrayName": "pressure",
            "component": 0,
            "min": 0.0,
            "max": 1.0,
        }
    )

    forwarded = api.set_part_color_variable.call_args.args[2]
    assert forwarded is VisorVtkVariableType.POINT


def test_set_part_color_variable_parses_cell_association_to_the_enum_member(app, api):
    """'CELL' arrives as the CELL member itself, not as a string."""
    app.set_part_color_variable(
        {
            "nodeId": 7,
            "variableId": "CELL::temperature::1",
            "association": "CELL",
            "arrayName": "temperature",
            "component": 0,
            "min": 0.0,
            "max": 1.0,
        }
    )

    forwarded = api.set_part_color_variable.call_args.args[2]
    assert forwarded is VisorVtkVariableType.CELL


@pytest.mark.parametrize("association", ["point", "cell", "NODE", "", None])
def test_set_part_color_variable_non_member_association_is_a_logged_no_op(
    app, api, association
):
    """A non-member association warns and delegates nothing -- no upper-casing."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        app.set_part_color_variable(
            {
                "nodeId": 7,
                "variableId": "POINT::pressure::1",
                "association": association,
                "arrayName": "pressure",
                "component": 0,
                "min": 0.0,
                "max": 1.0,
            }
        )

    api.set_part_color_variable.assert_not_called()
    assert mock_logger.warning.call_count == 1


def test_set_part_color_variable_forwards_variable_id_byte_identically(app, api):
    """variableId crosses opaquely: not split, not rebuilt, not normalised."""
    variable_id = "CELL::Von Mises::3"
    app.set_part_color_variable(
        {
            "nodeId": 7,
            "variableId": variable_id,
            "association": "CELL",
            "arrayName": "Von Mises",
            "component": 2,
            "min": -1.5,
            "max": 1.5,
        }
    )

    assert api.set_part_color_variable.call_args.args[1] == "CELL::Von Mises::3"


def test_clear_part_color_variable_delegates_payload_values(app, api):
    """nodeId reaches the coordinator unchanged."""
    app.clear_part_color_variable({"nodeId": 7})

    api.clear_part_color_variable.assert_called_once_with(7)


# ===========================================================================
# Return value and the not-injected guard
# ===========================================================================

@pytest.mark.parametrize("name", TRIGGER_NAMES)
def test_trigger_returns_none(app, name):
    """No trigger returns the coordinator's return value."""
    assert getattr(app, name)(PAYLOADS[name]) is None


@pytest.mark.parametrize("name", TRIGGER_NAMES)
def test_trigger_is_a_logged_no_op_when_no_coordinator_injected(app_without_api, name):
    """With nothing injected, each trigger logs and returns without raising."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert getattr(app_without_api, name)(PAYLOADS[name]) is None

    assert mock_logger.debug.call_count == 1

