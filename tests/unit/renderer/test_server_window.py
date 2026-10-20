"""
Unit tests for VisorRcaWindow.

The renderer is a real ServerRenderer, never rendered.  The capture is a
recording double whose ``img_cols_rows`` returns a hand-written frame.  The lock
is a real ``threading.RLock`` held, where a test needs it held, by a second
thread: the lock is re-entrant, so a hold on the test's own thread would let the
window's non-blocking acquire succeed.
"""

from __future__ import annotations

import threading
from typing import Callable
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from ansys.visor.viewer.renderer.server_renderer import ServerRenderer
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow
from tests.helpers.utils.locks import LOCK_TIMEOUT_S, lock_held_by_another_thread

EVENT_1 = {"type": "LeftButtonPress", "x": 10, "y": 20}
EVENT_2 = {"type": "MouseMove", "x": 15, "y": 25}
EVENT_3 = {"type": "LeftButtonRelease", "x": 15, "y": 25}


class _RecordingFrameRequester:
    """Counts frame requests."""

    def __init__(self) -> None:
        self.count = 0

    def request_frame(self) -> None:
        self.count += 1


class _RecordingCapture:
    """Counts captures, returns one literal frame, and records forwarded events."""

    def __init__(self, frame) -> None:
        self.frame = frame
        self.captures = 0
        self.events: list[dict] = []
        self.on_capture: Callable[[], None] | None = None

    @property
    def img_cols_rows(self):
        self.captures += 1
        if self.on_capture is not None:
            self.on_capture()
        return self.frame

    def process_resize_event(self, width: int, height: int) -> None:
        raise AssertionError("the window resizes through the renderer, not the capture")

    def process_interaction_event(self, event: dict) -> None:
        self.events.append(event)


class _RecordingReschedule:
    """Counts reschedule calls."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


def _acquired_by_another_thread(lock) -> bool:
    """Try a non-blocking acquire from a probe thread; release it if taken."""
    result: list[bool] = []

    def probe() -> None:
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
        result.append(acquired)

    prober = threading.Thread(target=probe, daemon=True)
    prober.start()
    prober.join(LOCK_TIMEOUT_S)
    assert result, "the probe thread did not finish"
    return result[0]


@pytest.fixture
def renderer() -> ServerRenderer:
    return ServerRenderer((0.2, 0.4, 0.6), _RecordingFrameRequester(), MagicMock(name="camera_publisher"))


@pytest.fixture
def frame():
    return (np.array([[[1, 2, 3], [4, 5, 6], [7, 8, 9]]], dtype=np.uint8), 3, 1)


@pytest.fixture
def capture(frame) -> _RecordingCapture:
    return _RecordingCapture(frame)


@pytest.fixture
def lock() -> threading.RLock:
    return threading.RLock()


@pytest.fixture
def reschedule() -> _RecordingReschedule:
    return _RecordingReschedule()


@pytest.fixture
def window(capture, renderer, lock, reschedule) -> VisorRcaWindow:
    return VisorRcaWindow(capture, renderer, lock, reschedule)


def test_held_lock_does_not_capture(window, capture, lock):
    with lock_held_by_another_thread(lock):
        window.img_cols_rows
    assert capture.captures == 0


def test_held_lock_returns_last_frame(window, frame, lock):
    assert window.img_cols_rows is frame
    with lock_held_by_another_thread(lock):
        result = window.img_cols_rows
    assert result is frame


def test_held_lock_before_first_frame_returns_placeholder(window, lock):
    with lock_held_by_another_thread(lock):
        result = window.img_cols_rows
    assert result[0].dtype == np.uint8
    assert np.array_equal(result[0], np.full((300, 300, 3), (51, 102, 153), np.uint8))
    assert result[1:] == (300, 300)


def test_held_lock_requests_one_retry(window, lock, reschedule):
    window.img_cols_rows
    assert reschedule.count == 0
    with lock_held_by_another_thread(lock):
        window.img_cols_rows
    assert reschedule.count == 1


def test_capture_runs_under_the_lock(window, capture, lock):
    probes: list[bool] = []
    capture.on_capture = lambda: probes.append(_acquired_by_another_thread(lock))
    window.img_cols_rows
    assert probes == [False]


def test_lock_released_after_frame(window, lock):
    window.img_cols_rows
    assert _acquired_by_another_thread(lock) is True


def test_resize_applied_under_lock_only(window, renderer, lock):
    window.process_resize_event(64, 48)
    assert renderer.render_window.GetSize() == (300, 300)
    with lock_held_by_another_thread(lock):
        window.img_cols_rows
    assert renderer.render_window.GetSize() == (300, 300)
    window.img_cols_rows
    assert renderer.render_window.GetSize() == (64, 48)


def test_resize_coalesces_to_last_size(window, renderer, lock):
    with patch.object(renderer, "set_viewport_size", wraps=renderer.set_viewport_size) as spy:
        with lock_held_by_another_thread(lock):
            window.process_resize_event(64, 48)
            window.process_resize_event(80, 60)
            window.img_cols_rows
        window.img_cols_rows
    assert spy.call_args_list == [call(80, 60)]
    assert renderer.render_window.GetSize() == (80, 60)


def test_deferred_events_in_order_none_dropped(window, capture, lock):
    with lock_held_by_another_thread(lock):
        window.process_interaction_event(EVENT_1)
        window.img_cols_rows
        window.process_interaction_event(EVENT_2)
        window.img_cols_rows
        window.process_interaction_event(EVENT_3)
        assert capture.events == []
    window.img_cols_rows
    assert capture.events == [
        {"type": "LeftButtonPress", "x": 10, "y": 20},
        {"type": "MouseMove", "x": 15, "y": 25},
        {"type": "LeftButtonRelease", "x": 15, "y": 25},
    ]
    window.img_cols_rows
    assert capture.events == [
        {"type": "LeftButtonPress", "x": 10, "y": 20},
        {"type": "MouseMove", "x": 15, "y": 25},
        {"type": "LeftButtonRelease", "x": 15, "y": 25},
    ]

