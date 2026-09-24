"""Unit tests for ``LocalApp.set_projection`` -- the projection trigger.

A module of its own rather than an addition to ``test_local_app.py``, on the
precedent ``test_local_app_sync_camera.py`` set: that module's
``TRIGGER_NAMES`` list drives parametrised tests whose meaning is "one of the
six per-part triggers", and every per-part payload model carries
``node_id: int = Field(alias="nodeId")``.  ``set_projection`` carries no node
id -- it carries a single ``parallel`` boolean and is scene-wide -- so adding a
name there would multiply the per-part tests by one more and rewrite them.

It is separate from ``test_local_app_widget_triggers.py`` as well, and
deliberately: those three are toggles the server stores, this one is the
camera record's field, and the two increments that added them have different
failure modes.

Coverage targets
----------------
1.  The trigger delegates the value it arrived with, exactly once, to the
    identically-named coordinator method -- for ``True`` and for ``False``, so
    a handler that forwarded a constant fails.
2.  A payload missing ``parallel`` is a logged no-op: nothing is delegated.
3.  A payload that is not a mapping at all is a logged no-op, not a
    ``TypeError`` -- the ``model_validate`` posture the payload decorator
    documents.
4.  With no coordinator injected, the trigger logs and returns.
5.  The trigger name survives decoration and is registered with the server.

Every payload here is a hand-written literal.  The wire key is ``parallel``
and carries no alias: snake_case and camelCase coincide, which is itself
asserted by the delegation tests passing a literal ``{"parallel": ...}``.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp

# The trigger name, written out rather than imported, so that a rename on the
# production side fails here by name instead of following along.
PROJECTION_TRIGGER = "set_projection"


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
    return MagicMock(name="scene_mutation_api")


@pytest.fixture
def app(mock_server, api):
    """LocalApp with a coordinator injected."""
    return LocalApp(
        server=mock_server,
        get_scene_details_json=MagicMock(),
        handle_save_state_response=MagicMock(),
        standalone=True,
        scene_mutation_api=api,
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
# Both values are exercised.  Projection has no server-side store and so no
# default to differ from, which is exactly why the pair is needed here: a
# handler that forwarded a constant would pass either test alone.
# ===========================================================================

def test_set_projection_delegates_the_parallel_value(app, api):
    """The trigger hands the coordinator the value it received."""
    result = app.set_projection({"parallel": True})

    assert result is None
    api.set_projection.assert_called_once_with(True)


def test_set_projection_delegates_a_false_value(app, api):
    """Perspective travels the same path as parallel, and is not a no-op.

    The absolute-value rule applies here as everywhere on this boundary: the
    client sends the value its widget settled on, never a toggle, so "turn it
    off" is a message with a value and not an absent message.
    """
    result = app.set_projection({"parallel": False})

    assert result is None
    api.set_projection.assert_called_once_with(False)


# ===========================================================================
# Validation -- a malformed payload reaches no handler body
# ===========================================================================

def test_set_projection_missing_parallel_is_a_logged_no_op(app, api):
    """An empty payload never reaches the handler body.

    Asserted against the whole mock rather than one method name, so a leak
    under any other name still fails.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.set_projection({})

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


def test_set_projection_non_mapping_payload_is_a_logged_no_op(app, api):
    """A bare string is a ValidationError, not a TypeError.

    The payload decorator uses ``model_validate`` rather than
    ``model(**payload)`` precisely so that a payload which is not a mapping at
    all is caught by the same guard as a payload with a missing key.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.set_projection("parallel")

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


# ===========================================================================
# No coordinator injected
# ===========================================================================

def test_set_projection_is_a_logged_no_op_when_no_coordinator_injected(app_without_api):
    """With nothing injected the trigger logs and returns without raising.

    Two debug lines, both from ``_mutation_api`` and neither from this
    handler: the arrival line every trigger emits, and the "no scene
    part-state API injected" line that says why nothing was delegated.  The
    handler adds no logging of its own, so counting arrivals in the server log
    stays a sound measurement, and the trigger name appears on both lines so
    the count is attributable.

    The literal ``2`` is hand-written from what ``_mutation_api`` does, not
    copied from the neighbouring trigger modules, which assert ``1`` and are
    red at this increment's base commit for exactly that reason.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app_without_api.set_projection({"parallel": True})

    assert result is None
    assert log.debug.call_count == 2
    assert all(PROJECTION_TRIGGER in call.args for call in log.debug.call_args_list)
    assert log.warning.call_count == 0


# ===========================================================================
# Registration
# ===========================================================================

def test_set_projection_trigger_name_is_registered_after_decoration(app, mock_server):
    """The name survives the payload decorator and takes a raw dict.

    ``@trigger`` is outermost above ``@parse_payload``; this asserts the pair
    registers under the name rather than under the wrapper, and that the
    registered callable accepts the raw dict the client sends.
    """
    names = [call.args[0] for call in mock_server.trigger.call_args_list]
    functions = [
        call.args[0] for call in mock_server.trigger.return_value.call_args_list
    ]
    registered = dict(zip(names, functions))

    assert PROJECTION_TRIGGER in registered
    assert registered[PROJECTION_TRIGGER]({"parallel": False}) is None

