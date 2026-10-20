"""
Unit tests for ServerLoopBridge.

Ruling-6 tests drive a real VisorRcaWindow whose reschedule is the bridge's
``retry_frame``, with the scene lock held by a second thread.  The running loop
is replaced by a recording double, so delayed calls are recorded, not run.
The recording runner reports the test's own thread as its loop thread, so the
bridge binds there.  The loop-thread tests use a real AsyncRunner.
"""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from ansys.visor.viewer.app.trame.async_runner import AsyncRunner
from ansys.visor.viewer.app.trame.server_loop_bridge import ServerLoopBridge
from ansys.visor.viewer.renderer.server_renderer import ServerRenderer
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow
from tests.helpers.utils.locks import lock_held_by_another_thread

WAIT_TIMEOUT_S = 5.0


class _RecordingViewHandler:
    """Records the thread of every schedule_render call."""

    def __init__(self) -> None:
        self.thread_ids: list[int] = []
        self._changed = threading.Condition()

    @property
    def count(self) -> int:
        return len(self.thread_ids)

    def schedule_render(self) -> None:
        with self._changed:
            self.thread_ids.append(threading.get_ident())
            self._changed.notify_all()

    def wait_for(self, count: int) -> bool:
        with self._changed:
            return self._changed.wait_for(lambda: len(self.thread_ids) >= count, WAIT_TIMEOUT_S)


class _RecordingRunner:
    """Records the callbacks handed to call_soon, without running them; its loop thread is the creating thread."""

    def __init__(self) -> None:
        self.callbacks: list = []
        self.thread = threading.current_thread()

    def call_soon(self, callback) -> None:
        self.callbacks.append(callback)


class _RecordingLoop:
    """Records call_later calls, without running them."""

    def __init__(self) -> None:
        self.records: list[tuple[float, object]] = []

    def call_later(self, delay: float, callback) -> None:
        self.records.append((delay, callback))


class _NeverCapture:
    """A capture the held-lock path must never touch."""

    @property
    def img_cols_rows(self):
        raise AssertionError("captured while the lock is held elsewhere")

    def process_resize_event(self, width: int, height: int) -> None:
        raise AssertionError("resized through the capture")

    def process_interaction_event(self, event: dict) -> None:
        raise AssertionError("event forwarded while the lock is held elsewhere")


@pytest.fixture
def runner() -> _RecordingRunner:
    return _RecordingRunner()


@pytest.fixture
def handler() -> _RecordingViewHandler:
    return _RecordingViewHandler()


@pytest.fixture
def bound_bridge(runner, handler) -> ServerLoopBridge:
    bridge = ServerLoopBridge(runner)
    bridge.bind(handler)
    return bridge


@pytest.fixture
def loop():
    recording_loop = _RecordingLoop()
    with patch(
        "ansys.visor.viewer.app.trame.server_loop_bridge.asyncio.get_running_loop",
        return_value=recording_loop,
    ):
        yield recording_loop


@pytest.fixture
def lock() -> threading.RLock:
    return threading.RLock()


@pytest.fixture
def window(bound_bridge, lock) -> VisorRcaWindow:
    renderer = ServerRenderer((0.2, 0.4, 0.6), bound_bridge)
    return VisorRcaWindow(_NeverCapture(), renderer, lock, bound_bridge.retry_frame)


def test_two_locked_calls_leave_one_pending_retry(window, lock, loop):
    with lock_held_by_another_thread(lock):
        window.img_cols_rows
        window.img_cols_rows
    assert [delay for delay, _ in loop.records] == [0.1]


def test_retry_fires_then_rearms(window, lock, loop, handler):
    with lock_held_by_another_thread(lock):
        window.img_cols_rows
    _, fire_retry = loop.records[0]
    fire_retry()
    assert handler.count == 1
    with lock_held_by_another_thread(lock):
        window.img_cols_rows
    assert len(loop.records) == 2


def test_request_frame_runs_on_loop_thread():
    async_runner = AsyncRunner()
    try:
        handler = _RecordingViewHandler()
        bridge = ServerLoopBridge(async_runner)

        async def bind_on_loop_thread() -> None:
            bridge.bind(handler)

        async_runner.run_coroutine_block(bind_on_loop_thread(), patch_return_future=False)
        bridge.request_frame()
        assert handler.wait_for(2)
        loop_thread_id = async_runner.thread.ident
        assert handler.thread_ids == [loop_thread_id, loop_thread_id]
    finally:
        async_runner.dispose()


def test_bind_off_runner_thread_raises():
    async_runner = AsyncRunner()
    try:
        bridge = ServerLoopBridge(async_runner)
        with pytest.raises(RuntimeError):
            bridge.bind(_RecordingViewHandler())
    finally:
        async_runner.dispose()


def test_request_before_bind_is_dropped(runner):
    bridge = ServerLoopBridge(runner)
    bridge.request_frame()
    assert runner.callbacks == []


def test_bind_requests_one_frame(runner, handler):
    bridge = ServerLoopBridge(runner)
    bridge.bind(handler)
    assert len(runner.callbacks) == 1
    runner.callbacks[0]()
    assert handler.count == 1

