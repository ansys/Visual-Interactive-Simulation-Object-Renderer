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
6.  A malformed payload is a logged no-op and never reaches a handler body:
    a missing required key, a wrong-typed value, a payload that is not a
    mapping at all, a ``diffuseRgb`` that is not exactly three components,
    or an opacity outside ``[0.0, 1.0]``.
7.  An unknown extra key is ignored, not rejected: the rest of the payload
    is still forwarded.
8.  All six trigger names are still registered with the trame server after
    the payload decorator wraps the handlers, and the registered callable
    still accepts a raw ``dict``.
9.  The two logged-no-op paths stay distinct: an invalid payload logs
    ``warning`` and no ``debug``; a missing coordinator logs ``debug`` and
    no ``warning``.

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


# ===========================================================================
# Payload validation
# ===========================================================================

# One required key per trigger, removed to make an otherwise valid payload
# malformed.  Written out per trigger rather than derived from the models.
MISSING_KEY = {
    "set_part_visibility": "visible",
    "set_part_opacity": "opacity",
    "set_part_diffuse_color": "diffuseRgb",
    "set_part_selected": "selected",
    "set_part_color_variable": "arrayName",
    "clear_part_color_variable": "nodeId",
}


@pytest.mark.parametrize("name", TRIGGER_NAMES)
def test_missing_required_key_is_a_logged_no_op(app, api, name):
    """A payload short one required key delegates nothing and warns once."""
    payload = {k: v for k, v in PAYLOADS[name].items() if k != MISSING_KEY[name]}

    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert getattr(app, name)(payload) is None

    getattr(api, name).assert_not_called()
    assert mock_logger.warning.call_count == 1


def test_wrong_typed_bool_value_is_a_logged_no_op(app, api):
    """2 is not a bool: pydantic accepts 0 and 1 only, so this fails."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert app.set_part_visibility({"nodeId": 7, "visible": 2}) is None

    api.set_part_visibility.assert_not_called()
    assert mock_logger.warning.call_count == 1


def test_wrong_typed_int_value_is_a_logged_no_op(app, api):
    """A non-numeric string is not coerced to int: 'x' fails nodeId."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert app.set_part_visibility({"nodeId": "x", "visible": False}) is None

    api.set_part_visibility.assert_not_called()
    assert mock_logger.warning.call_count == 1


@pytest.mark.parametrize("payload", ["nope", 42, None, [1, 2, 3]])
def test_non_dict_payload_is_a_logged_no_op_not_a_type_error(app, api, payload):
    """A payload that is not a mapping is caught, not raised as TypeError.

    This is why the decorator uses ``model_validate`` rather than
    ``Model(**payload)``: the latter raises TypeError on a non-mapping,
    which would escape the guard and land on the trame daemon thread.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert app.set_part_visibility(payload) is None

    api.set_part_visibility.assert_not_called()
    assert mock_logger.warning.call_count == 1


def test_unknown_extra_key_is_forwarded_not_rejected(app, api):
    """A key this server does not know about is dropped, not an error."""
    app.set_part_visibility({"nodeId": 7, "visible": False, "someFutureKey": 1})

    api.set_part_visibility.assert_called_once_with(7, False)


def test_set_part_diffuse_color_absent_key_is_a_validation_failure(app, api):
    """An absent diffuseRgb is malformed -- distinct from an explicit null."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert app.set_part_diffuse_color({"nodeId": 7}) is None

    api.set_part_diffuse_color.assert_not_called()
    assert mock_logger.warning.call_count == 1


def test_set_part_diffuse_color_two_element_colour_is_a_logged_no_op(app, api):
    """The torn write: a short colour must not reach the coordinator.

    The coordinator writes the store first and only then indexes the colour
    at [0], [1] and [2] to apply it.  A two-element list therefore left the
    store holding a malformed colour, the VTK object untouched, and an
    IndexError on the trame daemon thread.  Rejecting it here means nothing
    is delegated, so nothing is written.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert app.set_part_diffuse_color({"nodeId": 7, "diffuseRgb": [1.0, 0.0]}) is None

    api.set_part_diffuse_color.assert_not_called()
    assert mock_logger.warning.call_count == 1


def test_set_part_opacity_out_of_range_is_a_logged_no_op(app, api):
    """An opacity outside [0.0, 1.0] never reaches VTK to be clamped."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert app.set_part_opacity({"nodeId": 7, "opacity": 5.0}) is None

    api.set_part_opacity.assert_not_called()
    assert mock_logger.warning.call_count == 1


# ===========================================================================
# Trigger registration survives decoration
# ===========================================================================

def _registered_triggers(mock_server):
    """Recover {trigger name: registered callable} from the mock server.

    TrameApp's wrapped __init__ registers each handler as
    ``server.trigger(name)(fn)``, so the i-th name passed to ``trigger``
    pairs with the i-th function passed to its return value.
    """
    names = [call.args[0] for call in mock_server.trigger.call_args_list]
    functions = [call.args[0] for call in mock_server.trigger.return_value.call_args_list]
    return dict(zip(names, functions))


@pytest.mark.parametrize("name", TRIGGER_NAMES)
def test_trigger_name_is_still_registered_after_decoration(app, mock_server, name):
    """Wrapping the handlers does not lose the @trigger registration."""
    assert name in _registered_triggers(mock_server)


def test_the_registered_callable_still_accepts_a_raw_dict(app, api, mock_server):
    """Dispatch reaches the coordinator through the wrapper, not past it."""
    registered = _registered_triggers(mock_server)

    registered["set_part_visibility"]({"nodeId": 7, "visible": False})

    api.set_part_visibility.assert_called_once_with(7, False)


# ===========================================================================
# The warning and debug paths stay distinct
# ===========================================================================
#
# Note: the parse now runs before the API lookup, so a malformed payload
# reaching a LocalApp with no coordinator injected logs warning, where it
# would previously have logged debug.  Both are logged no-ops.

@pytest.mark.parametrize("name", TRIGGER_NAMES)
def test_invalid_payload_logs_warning_and_not_debug(app, api, name):
    """The validation no-op is a warning and is not confused with the other."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert getattr(app, name)({"junk": True}) is None

    getattr(api, name).assert_not_called()
    assert mock_logger.warning.call_count == 1
    assert mock_logger.debug.call_count == 0


@pytest.mark.parametrize("name", TRIGGER_NAMES)
def test_missing_coordinator_logs_debug_and_not_warning(app_without_api, name):
    """The not-injected no-op is a debug and is not confused with the other."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as mock_logger:
        assert getattr(app_without_api, name)(PAYLOADS[name]) is None

    assert mock_logger.debug.call_count == 1
    assert mock_logger.warning.call_count == 0


