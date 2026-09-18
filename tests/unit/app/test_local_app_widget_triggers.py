"""Unit tests for LocalApp's three widget-state triggers.

A module of its own rather than an addition to ``test_local_app.py``: that
module's ``TRIGGER_NAMES`` list drives parametrised tests whose meaning is
"one of the six per-part triggers", and every per-part payload model carries
``node_id: int = Field(alias="nodeId")``.  None of these three carries a node
id -- each is scene-wide and carries a single ``visible`` boolean -- so adding
a name there would multiply the per-part tests by three and rewrite them.

Coverage targets
----------------
1.  Each trigger delegates the value it arrived with, exactly once, to the
    identically-named coordinator method.
2.  A payload missing ``visible`` is a logged no-op: nothing is delegated.
3.  A payload that is not a mapping at all is a logged no-op, not a
    ``TypeError`` -- the ``model_validate`` posture the payload decorator
    documents.
4.  With no coordinator injected, each trigger logs and returns.
5.  All three trigger names survive decoration and are registered with the
    server.

Every payload here is a hand-written literal.  The wire key is ``visible`` on
all three and carries no alias: snake_case and camelCase coincide, which is
itself asserted by the delegation tests passing a literal ``{"visible": ...}``.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp

# The three trigger names, written out rather than imported, so that a rename
# on the production side fails here by name instead of following along.
CROSS_SECTION_TRIGGER = "set_cross_section_visibility"
EDGES_TRIGGER = "set_edges_visible"
BOUNDING_BOX_TRIGGER = "set_bounding_box_visibility"


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
    """Stand-in for the injected scene coordinator."""
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
#
# ``True`` is sent where the server's own default is ``False``, so a handler
# that delegated a default rather than the payload's value would fail.
# ===========================================================================

def test_set_cross_section_visibility_delegates_the_visible_value(app, api):
    """The cross-section trigger hands the coordinator the value it received."""
    result = app.set_cross_section_visibility({"visible": True})

    assert result is None
    api.set_cross_section_visibility.assert_called_once_with(True)


def test_set_edges_visible_delegates_the_visible_value(app, api):
    """The edges trigger hands the coordinator the value it received."""
    result = app.set_edges_visible({"visible": True})

    assert result is None
    api.set_edges_visible.assert_called_once_with(True)


def test_set_bounding_box_visibility_delegates_the_visible_value(app, api):
    """The bounding-box trigger hands the coordinator the value it received."""
    result = app.set_bounding_box_visibility({"visible": True})

    assert result is None
    api.set_bounding_box_visibility.assert_called_once_with(True)


# ===========================================================================
# Validation -- a malformed payload reaches no handler body
# ===========================================================================

def test_set_cross_section_visibility_missing_visible_is_a_logged_no_op(app, api):
    """An empty payload never reaches the handler body."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.set_cross_section_visibility({})

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


def test_set_edges_visible_missing_visible_is_a_logged_no_op(app, api):
    """An empty payload never reaches the handler body."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.set_edges_visible({})

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


def test_set_bounding_box_visibility_missing_visible_is_a_logged_no_op(app, api):
    """An empty payload never reaches the handler body."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.set_bounding_box_visibility({})

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


def test_set_edges_visible_non_mapping_payload_is_a_logged_no_op(app, api):
    """A bare string is a ValidationError, not a TypeError.

    The payload decorator uses ``model_validate`` rather than ``model(**payload)``
    precisely so that a payload which is not a mapping at all is caught by the
    same guard as a payload with a missing key.  Asserted against the whole
    mock, so a leak under any other method name still fails.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.set_edges_visible("visible")

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


# ===========================================================================
# No coordinator injected
# ===========================================================================

def test_set_cross_section_visibility_is_a_logged_no_op_when_no_coordinator_injected(
    app_without_api,
):
    """With nothing injected the trigger logs and returns without raising."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app_without_api.set_cross_section_visibility({"visible": True})

    assert result is None
    assert log.debug.call_count == 2


def test_set_edges_visible_is_a_logged_no_op_when_no_coordinator_injected(app_without_api):
    """With nothing injected the trigger logs and returns without raising."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app_without_api.set_edges_visible({"visible": True})

    assert result is None
    assert log.debug.call_count == 2


def test_set_bounding_box_visibility_is_a_logged_no_op_when_no_coordinator_injected(
    app_without_api,
):
    """With nothing injected the trigger logs and returns without raising."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app_without_api.set_bounding_box_visibility({"visible": True})

    assert result is None
    assert log.debug.call_count == 2


# ===========================================================================
# Registration
# ===========================================================================

def test_widget_trigger_names_are_registered_after_decoration(app, mock_server):
    """All three names survive the payload decorator and take a raw dict.

    ``@trigger`` is outermost above ``@parse_payload``; this asserts the pair
    registers under the name rather than under the wrapper, and that the
    registered callable accepts the raw dict the client sends.
    """
    names = [call.args[0] for call in mock_server.trigger.call_args_list]
    functions = [
        call.args[0] for call in mock_server.trigger.return_value.call_args_list
    ]
    registered = dict(zip(names, functions))

    assert CROSS_SECTION_TRIGGER in registered
    assert EDGES_TRIGGER in registered
    assert BOUNDING_BOX_TRIGGER in registered
    assert registered[EDGES_TRIGGER]({"visible": False}) is None

