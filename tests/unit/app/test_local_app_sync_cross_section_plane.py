"""Unit tests for ``LocalApp.sync_cross_section_plane`` -- the plane trigger.

A module of its own rather than an addition to ``test_local_app.py``, on the
precedent ``test_local_app_sync_camera.py`` set: that module's
``TRIGGER_NAMES`` list drives parametrised tests whose meaning is "one of the
six per-part triggers", and every per-part payload model carries
``node_id: int = Field(alias="nodeId")``.  This trigger carries no node id --
it carries two three-component vectors and is scene-wide -- so adding a name
there would multiply the per-part tests by one more and rewrite them.

Two tests, not six.  The no-coordinator path and the not-a-mapping path run
through ``_part_state_api`` and ``parse_payload``, which three sibling trigger
modules already pin against the same two functions; repeating them here would
be a third and fourth copy of one failure mode rather than a new one.  What is
unique to this trigger is that it forwards *two* vectors in a fixed order, and
that its name has to survive the payload decorator.

Every payload here is a hand-written literal.  The wire keys are ``origin``
and ``normal`` and carry no alias: snake_case and camelCase coincide, which is
itself asserted by the delegation test passing a literal dict.
"""

from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp

# The trigger name, written out rather than imported, so that a rename on the
# production side fails here by name instead of following along.
PLANE_TRIGGER = "sync_cross_section_plane"

# Hand-written literals.  No component is shared between the origin and the
# normal and neither is a permutation of the other, so a handler that swapped
# the two arguments fails on value rather than coinciding.
REPORTED_ORIGIN = [1.5, 2.5, 3.5]
REPORTED_NORMAL = [0.0, 1.0, 0.0]


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


# ===========================================================================
# Delegation
# ===========================================================================

def test_sync_cross_section_plane_delegates_the_origin_and_normal(app, api):
    """The trigger hands the coordinator both vectors, in that order.

    Positional, and asserted positionally, because the coordinator's signature
    is ``(origin, normal)`` and a handler that passed them the other way round
    would type-check, validate and run -- and would leave the plane at right
    angles to where the user dragged it.  The two literals share no component,
    so the swap fails on value.
    """
    result = app.sync_cross_section_plane(
        {"origin": REPORTED_ORIGIN, "normal": REPORTED_NORMAL}
    )

    assert result is None
    api.sync_cross_section_plane.assert_called_once_with(
        REPORTED_ORIGIN, REPORTED_NORMAL
    )


# ===========================================================================
# Registration
# ===========================================================================

def test_sync_cross_section_plane_trigger_name_is_registered_after_decoration(
    app, mock_server
):
    """The name survives the payload decorator, once, and takes a raw dict.

    ``@trigger`` is outermost above ``@parse_payload``; this asserts the pair
    registers under the name rather than under the wrapper, and that the
    registered callable accepts the raw dict the client sends.

    Registered exactly once: a second registration under the same name would
    leave which handler the client reaches dependent on registration order,
    and nothing else in the suite would see it.
    """
    names = [call.args[0] for call in mock_server.trigger.call_args_list]
    functions = [
        call.args[0] for call in mock_server.trigger.return_value.call_args_list
    ]
    registered = dict(zip(names, functions))

    assert names.count(PLANE_TRIGGER) == 1
    assert PLANE_TRIGGER in registered
    assert registered[PLANE_TRIGGER](
        {"origin": REPORTED_ORIGIN, "normal": REPORTED_NORMAL}
    ) is None

