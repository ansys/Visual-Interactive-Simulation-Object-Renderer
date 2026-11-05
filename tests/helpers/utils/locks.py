"""Lock helpers for tests that need a lock held by a thread other than the test's own."""

import threading
from contextlib import contextmanager
from typing import Iterator

LOCK_TIMEOUT_S = 5.0


class LockSpy:
    """Re-entrant lock that records its own acquisition depth.

    Wraps a real RLock so nesting still behaves, and exposes ``depth`` so a
    test can assert the lock was *held* at the moment some inner call ran,
    rather than merely acquired at some point.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.enter_count = 0
        self.exit_count = 0
        self.depth = 0
        self.max_depth = 0

    def __enter__(self):
        self._lock.acquire()
        self.enter_count += 1
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.depth -= 1
        self.exit_count += 1
        self._lock.release()
        return False


@contextmanager
def lock_held_by_another_thread(lock) -> Iterator[None]:
    """Hold ``lock`` from a second thread for the body of the ``with`` block.

    A re-entrant lock held by the test's own thread would still be acquirable by
    a non-blocking ``acquire`` on that thread, so a same-thread hold proves nothing.
    """
    held = threading.Event()
    release = threading.Event()

    def hold() -> None:
        lock.acquire()
        try:
            held.set()
            release.wait(LOCK_TIMEOUT_S)
        finally:
            lock.release()

    holder = threading.Thread(target=hold, daemon=True)
    holder.start()
    if not held.wait(LOCK_TIMEOUT_S):
        raise AssertionError("the holder thread never acquired the lock")
    try:
        yield
    finally:
        release.set()
        holder.join(LOCK_TIMEOUT_S)
        if holder.is_alive():
            raise AssertionError("the holder thread did not release the lock")

