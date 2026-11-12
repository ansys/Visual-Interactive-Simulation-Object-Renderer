"""
Unit tests for ServerStatePublisher.

The state is a recording double.  The loop-thread test uses a real
AsyncRunner; the others use a recording runner whose callbacks run only when
the test calls them.  Expected records are hand-written literals.
"""

from __future__ import annotations

import threading

import pytest

from ansys.visor.viewer.app.trame.async_runner import AsyncRunner
from ansys.visor.viewer.app.trame.server_state_publisher import ServerStatePublisher
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState

WAIT_TIMEOUT_S = 5.0

CAMERA_RECORD = {
    "position": [0.0, 0.0, 9.0],
    "focalPoint": [0.0, 0.0, 0.0],
    "viewUp": [0.0, 1.0, 0.0],
    "clippingRange": [1.0, 20.0],
    "parallelProjection": False,
    "viewAngle": 25.0,
    "parallelScale": 3.0,
}


def _camera() -> VisorCameraState:
    return VisorCameraState(
        position=[0.0, 0.0, 9.0],
        focal_point=[0.0, 0.0, 0.0],
        view_up=[0.0, 1.0, 0.0],
        clipping_range=[1.0, 20.0],
        parallel_projection=False,
        view_angle=25.0,
        parallel_scale=3.0,
    )


class _RecordingState:
    """Records each key write and each flush, with the thread it ran on; a read returns the last value set, or None."""

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.thread_ids: list[int] = []
        self._values: dict = {}
        self._changed = threading.Condition()

    def _record(self, event: tuple) -> None:
        with self._changed:
            self.events.append(event)
            self.thread_ids.append(threading.get_ident())
            self._changed.notify_all()

    def __getitem__(self, key):
        return self._values.get(key)

    def __setitem__(self, key, value) -> None:
        self._values[key] = value
        self._record(("set", key, value))

    def flush(self) -> None:
        self._record(("flush",))

    def wait_for(self, count: int) -> bool:
        with self._changed:
            return self._changed.wait_for(lambda: len(self.events) >= count, WAIT_TIMEOUT_S)


class _RecordingRunner:
    """Records the callbacks handed to call_soon, without running them."""

    def __init__(self) -> None:
        self.callbacks: list = []

    def call_soon(self, callback) -> None:
        self.callbacks.append(callback)


@pytest.fixture
def state() -> _RecordingState:
    return _RecordingState()


@pytest.fixture
def runner() -> _RecordingRunner:
    return _RecordingRunner()


def test_publish_camera_writes_state_on_loop_thread(state):
    async_runner = AsyncRunner()
    try:
        publisher = ServerStatePublisher(async_runner, state)
        publisher.publish_camera(_camera())
        assert state.wait_for(2)
        loop_thread_id = async_runner.thread.ident
        assert state.events == [("set", "server_camera_state", CAMERA_RECORD), ("flush",)]
        assert state.thread_ids == [loop_thread_id, loop_thread_id]
    finally:
        async_runner.dispose()


def test_publish_camera_dumps_at_call_time(runner, state):
    camera = _camera()
    ServerStatePublisher(runner, state).publish_camera(camera)
    # A later camera write mutates the record in place before the loop runs.
    camera.parallel_projection = True
    runner.callbacks[0]()
    assert state.events == [("set", "server_camera_state", CAMERA_RECORD), ("flush",)]


def test_publish_camera_none_writes_none(runner, state):
    ServerStatePublisher(runner, state).publish_camera(None)
    runner.callbacks[0]()
    assert state.events == [("set", "server_camera_state", None), ("flush",)]


def test_publish_cross_section_writes_record(runner, state):
    plane = VisorCrossSectionState(origin=[0.0, 0.0, 0.5], normal=[0.0, 1.0, 0.0])
    ServerStatePublisher(runner, state).publish_cross_section(plane)
    runner.callbacks[0]()
    assert state.events == [
        ("set", "server_cross_section_state", {"origin": [0.0, 0.0, 0.5], "normal": [0.0, 1.0, 0.0]}),
        ("flush",),
    ]


def test_publish_cross_section_none_writes_none(runner, state):
    ServerStatePublisher(runner, state).publish_cross_section(None)
    runner.callbacks[0]()
    assert state.events == [("set", "server_cross_section_state", None), ("flush",)]


def test_bumps_queued_together_count_up(runner, state):
    """Both bumps are queued before either runs, so each must read the value on the loop."""
    publisher = ServerStatePublisher(runner, state)
    publisher.bump_scene_version()
    publisher.bump_scene_version()
    for callback in runner.callbacks:
        callback()
    assert state.events == [
        ("set", "scene_version", 1),
        ("flush",),
        ("set", "scene_version", 2),
        ("flush",),
    ]


def test_bump_writes_on_loop_thread(state):
    async_runner = AsyncRunner()
    try:
        ServerStatePublisher(async_runner, state).bump_scene_version()
        assert state.wait_for(2)
        loop_thread_id = async_runner.thread.ident
        assert state.events == [("set", "scene_version", 1), ("flush",)]
        assert state.thread_ids == [loop_thread_id, loop_thread_id]
    finally:
        async_runner.dispose()

