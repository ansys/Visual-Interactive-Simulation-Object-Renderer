"""Unit tests for ``LocalApp.sync_camera`` -- the camera trigger.

A module of its own rather than an addition to ``test_local_app.py``: that
module's ``TRIGGER_NAMES`` list drives nine parametrised tests whose meaning is
"one of the six per-part triggers", and ``sync_camera`` is not one of them.  It
carries a whole camera rather than a node id, and it drops a well-formed
payload on its own judgement, which no per-part trigger does.

Coverage targets
----------------
1.  A report tagged ``gesture`` reaches the coordinator exactly once, with the
    seven camera values it arrived with.
2.  A report tagged ``programmatic`` reaches the coordinator not at all --
    asserted against the whole mock, not against one method name, so that a
    drop that leaks through under any other name still fails.
3.  Each arrival produces exactly one debug line, on both paths, so that
    counting arrivals in the server log is a sound measurement.  This is what
    manual check MC-3 reads.
4.  A camera missing any of its seven fields is a logged no-op: whole or
    absent, never partial.
5.  An ``origin`` that is neither value is a logged no-op.
6.  The client's own twelve-field camera snapshot validates, and exactly the
    seven applied fields land.  Extra keys are ignored, not rejected.
7.  With no coordinator injected, the trigger is a logged no-op.
8.  The trigger name survives decoration and is registered with the server.

Every payload here is a hand-written camelCase literal.  The same seven camera
values appear in ``visor-client/src/jest-tests/CameraSyncReporter.test.ts``,
written out there as well, so that the two stacks are compared against one set
of numbers rather than against each other.
"""

from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.app.trame.local_app import LocalApp

# The seven applied camera fields, as the wire carries them.  Shared, by value
# and not by import, with the client-side test of the same trigger.
CAMERA_POSITION = [11.0, 12.0, 13.0]
CAMERA_FOCAL_POINT = [14.0, 15.0, 16.0]
CAMERA_VIEW_UP = [0.0, 1.0, 0.0]
CAMERA_CLIPPING_RANGE = [17.0, 18.0]
CAMERA_PARALLEL_PROJECTION = True
CAMERA_VIEW_ANGLE = 35.0
CAMERA_PARALLEL_SCALE = 19.0


def _camera() -> dict:
    """The seven-field camera the client sends, as a literal dict."""
    return {
        "position": [11.0, 12.0, 13.0],
        "focalPoint": [14.0, 15.0, 16.0],
        "viewUp": [0.0, 1.0, 0.0],
        "clippingRange": [17.0, 18.0],
        "parallelProjection": True,
        "viewAngle": 35.0,
        "parallelScale": 19.0,
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
# ===========================================================================

def test_sync_camera_gesture_delegates_the_camera_once(app, api):
    """A gesture report reaches the coordinator once, with its own values.

    The camera is asserted field by field against literals rather than by
    comparing against a model the test builds the way the code does.
    """
    result = app.sync_camera({"origin": "gesture", "camera": _camera()})

    assert result is None
    api.sync_camera.assert_called_once()
    (camera,), _ = api.sync_camera.call_args
    assert camera.position == CAMERA_POSITION
    assert camera.focal_point == CAMERA_FOCAL_POINT
    assert camera.view_up == CAMERA_VIEW_UP
    assert camera.clipping_range == CAMERA_CLIPPING_RANGE
    assert camera.parallel_projection == CAMERA_PARALLEL_PROJECTION
    assert camera.view_angle == CAMERA_VIEW_ANGLE
    assert camera.parallel_scale == CAMERA_PARALLEL_SCALE


def test_sync_camera_programmatic_delegates_nothing(app, api):
    """A programmatic report does not touch the coordinator at all.

    Asserted as the empty call list of the whole mock rather than as
    ``sync_camera.assert_not_called()``.  The failure this guards against is
    an echo reaching the scene by *any* route, and a per-method assertion
    would pass while some other method carried it.
    """
    app.sync_camera({"origin": "programmatic", "camera": _camera()})

    assert api.mock_calls == []


# ===========================================================================
# Logging -- one line per arrival, which is what MC-3 counts
# ===========================================================================

def test_sync_camera_gesture_logs_one_debug_line_with_origin_and_position(app):
    """An applied arrival is one line, naming the origin and the position."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        app.sync_camera({"origin": "gesture", "camera": _camera()})

    assert log.debug.call_count == 2
    args = log.debug.call_args.args
    assert "gesture" in args
    assert CAMERA_POSITION in args
    assert log.warning.call_count == 0


def test_sync_camera_programmatic_logs_one_debug_line_with_the_origin(app):
    """A dropped arrival is one line too, so drops are countable."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        app.sync_camera({"origin": "programmatic", "camera": _camera()})

    assert log.debug.call_count == 1
    assert "programmatic" in log.debug.call_args.args
    assert log.warning.call_count == 0


# ===========================================================================
# Validation -- whole or absent, never partial
# ===========================================================================

def test_sync_camera_with_a_six_field_camera_is_a_logged_no_op(app, api):
    """A camera missing one of the seven never reaches the handler body."""
    camera = _camera()
    del camera["parallelScale"]

    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.sync_camera({"origin": "gesture", "camera": camera})

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


def test_sync_camera_with_an_unrecognised_origin_is_a_logged_no_op(app, api):
    """``origin`` is validated, not merely compared against "gesture".

    Without the ``Literal`` on the model a typo would validate and then fall
    into the drop branch, where it would be indistinguishable from a genuine
    programmatic report -- and a typo in the *other* direction would be
    indistinguishable from a genuine gesture.
    """
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app.sync_camera({"origin": "Gesture", "camera": _camera()})

    assert result is None
    assert api.mock_calls == []
    assert log.warning.call_count == 1


def test_sync_camera_accepts_the_clients_twelve_field_snapshot(app, api):
    """The five derived fields are ignored; exactly the seven land.

    The client's camera snapshot type carries twelve fields.  Were the client
    to spread that whole object onto the wire, this is what the server would
    do with it: accept it silently.  The test records that, so the next
    session knows the wire shape is pinned on the *client* side and not here.
    """
    camera = _camera()
    camera.update(
        distance=20.0,
        orthographic=True,
        orthographicScale=21.0,
        unitsPerPixel=22.0,
        viewPortHeight=23.0,
    )

    app.sync_camera({"origin": "gesture", "camera": camera})

    api.sync_camera.assert_called_once()
    (applied,), _ = api.sync_camera.call_args
    assert set(applied.model_dump().keys()) == {
        "position",
        "focal_point",
        "view_up",
        "clipping_range",
        "parallel_projection",
        "view_angle",
        "parallel_scale",
    }
    assert applied.position == CAMERA_POSITION


# ===========================================================================
# No coordinator, and registration
# ===========================================================================

def test_sync_camera_is_a_logged_no_op_when_no_coordinator_injected(app_without_api):
    """With nothing injected the trigger logs and returns without raising."""
    with patch("ansys.visor.viewer.app.trame.local_app.logger") as log:
        result = app_without_api.sync_camera({"origin": "gesture", "camera": _camera()})

    assert result is None
    assert log.debug.call_count == 2


def test_sync_camera_trigger_name_is_registered_after_decoration(app, mock_server):
    """``sync_camera`` survives the payload decorator and takes a raw dict."""
    names = [call.args[0] for call in mock_server.trigger.call_args_list]
    functions = [
        call.args[0] for call in mock_server.trigger.return_value.call_args_list
    ]
    registered = dict(zip(names, functions))

    assert "sync_camera" in registered
    assert registered["sync_camera"]({"origin": "programmatic", "camera": _camera()}) is None

