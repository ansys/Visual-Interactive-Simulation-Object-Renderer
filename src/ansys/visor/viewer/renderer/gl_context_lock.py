"""
GlContextLock
=============
Scene lock for a scene whose render window is drawn on another thread.

An OpenGL context is current on at most one thread.  VTK makes a window's
context current on the calling thread whenever it frees or builds graphics
resources (removing an actor, turning a widget off) and leaves it current.
A frame drawn later on another thread then cannot make the context current,
and draws nothing or aborts the process.

:class:`GlContextLock` is the re-entrant scene lock that every VTK touch of
such a window holds.  When the outermost hold ends, it releases the window's
context if the holding thread has it current, so the next holder, on any
thread, can make it current.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from vtkmodules.vtkRenderingCore import vtkRenderWindow


class SceneLock(Protocol):
    """The lock operations a scene and its streaming window use."""

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire; non-blocking returns False when held elsewhere."""

    def release(self) -> None:
        """Release one level."""

    def __enter__(self) -> object:
        """Acquire, blocking."""

    def __exit__(self, *exc: object) -> None:
        """Release one level."""


class GlContextLock:
    """Re-entrant lock; when the outermost hold ends, the render window's GL context is current on no thread."""

    _render_window: vtkRenderWindow
    _lock: threading.RLock
    _depth: int

    def __init__(self, render_window: vtkRenderWindow) -> None:
        """Wrap a new RLock around *render_window*."""
        self._render_window = render_window
        self._lock = threading.RLock()
        self._depth = 0

    @property
    def depth(self) -> int:
        """Holds taken and not yet released by the holding thread; 0 when free."""
        return self._depth

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire the RLock; on success increment the hold depth."""
        if not self._lock.acquire(blocking):
            return False
        self._depth += 1
        return True

    def release(self) -> None:
        """Decrement the depth; at depth 0 release the context if current here, then release the RLock."""
        self._depth -= 1
        try:
            # Released before the RLock, so no other thread can acquire in between.
            if self._depth == 0 and self._render_window.IsCurrent():
                self._render_window.ReleaseCurrent()
        finally:
            self._lock.release()

    def __enter__(self) -> GlContextLock:
        """Acquire, blocking."""
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        """Release one level."""
        self.release()
