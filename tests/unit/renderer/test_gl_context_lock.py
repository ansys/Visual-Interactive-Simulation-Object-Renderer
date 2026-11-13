"""
Unit tests for GlContextLock.

A recording window stands in for the VTK render window: it reports a settable
``IsCurrent`` and counts ``ReleaseCurrent`` calls.  No OpenGL context is made.
"""

from __future__ import annotations

import threading

from ansys.visor.viewer.renderer.gl_context_lock import GlContextLock


class _RecordingWindow:
    """Reports a settable current flag; ReleaseCurrent counts and clears it."""

    def __init__(self, current: bool) -> None:
        self.current = current
        self.release_count = 0
        self.on_release = None

    def IsCurrent(self) -> bool:  # noqa: N802
        return self.current

    def ReleaseCurrent(self) -> None:  # noqa: N802
        self.release_count += 1
        self.current = False
        if self.on_release is not None:
            self.on_release()


def _acquire_on_other_thread(lock: GlContextLock) -> bool:
    """Whether a non-blocking acquire on a new thread succeeds; released again if it does."""
    result: list[bool] = []

    def probe() -> None:
        acquired = lock.acquire(blocking=False)
        result.append(acquired)
        if acquired:
            lock.release()

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return result[0]


def test_nested_release_keeps_context():
    window = _RecordingWindow(current=True)
    lock = GlContextLock(window)
    with lock:
        with lock:
            pass
        assert window.release_count == 0


def test_outermost_release_releases_once():
    window = _RecordingWindow(current=True)
    lock = GlContextLock(window)
    with lock:
        with lock:
            pass
    assert window.release_count == 1


def test_not_current_is_not_released():
    window = _RecordingWindow(current=False)
    lock = GlContextLock(window)
    with lock:
        pass
    assert window.release_count == 0


def test_release_happens_while_lock_held():
    window = _RecordingWindow(current=True)
    lock = GlContextLock(window)
    acquired_during_release: list[bool] = []
    window.on_release = lambda: acquired_during_release.append(_acquire_on_other_thread(lock))
    with lock:
        pass
    assert acquired_during_release == [False]


def test_failed_nonblocking_acquire_keeps_depth():
    lock = GlContextLock(_RecordingWindow(current=False))
    with lock:
        assert _acquire_on_other_thread(lock) is False
        assert lock.depth == 1
