"""
VisorRcaWindow
==============
trame-rca remote-controlled area over a :class:`ServerRenderer`.

trame-rca's scheduler reads :attr:`VisorRcaWindow.img_cols_rows` on the event
loop thread, and its resize and interaction RPCs arrive on the same thread.
Every VTK touch here (resize, interaction, ``Render()`` and read-back) happens
only while holding the scene lock, taken without blocking.  When another thread
holds the lock, the window returns the last frame (or a background placeholder
before the first), asks for a retry, and keeps the deferred size and events for
the next frame that gets the lock.

A forwarded batch that ends a gesture (a button release or a wheel step) has
the renderer record and publish the pipeline camera, and record a dragged
cross-section plane, once, in the same locked section, after the batch.
"""

from __future__ import annotations

from typing import Callable, Protocol

import numpy as np
from numpy.typing import NDArray
from trame_rca.rca.protocol import RemoteControlledAreaProtocol

from ansys.visor.viewer.renderer.server_renderer import INITIAL_WINDOW_SIZE, ServerRenderer

GESTURE_END_EVENT_TYPES: frozenset[str] = frozenset(
    {"LeftButtonRelease", "MiddleButtonRelease", "RightButtonRelease", "MouseWheel"}
)
"""Forwarded event types after which a gesture's camera change is complete.

trame-rca drops a release with no matching press before it reaches the window,
so each gesture forwards one release.
"""


class SceneLock(Protocol):
    """The two lock operations the window uses."""

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire; non-blocking returns False when held elsewhere."""

    def release(self) -> None:
        """Release one level."""


class VisorRcaWindow:
    """trame-rca area over a ServerRenderer that touches VTK only while holding the scene lock."""

    _capture: RemoteControlledAreaProtocol
    _renderer: ServerRenderer
    _vtk_lock: SceneLock
    _reschedule: Callable[[], None]
    _pending_size: tuple[int, int] | None
    _last_size: tuple[int, int]
    _pending_events: list[dict]
    _last_frame: tuple[NDArray, int, int] | None

    def __init__(
        self,
        capture: RemoteControlledAreaProtocol,
        renderer: ServerRenderer,
        vtk_lock: SceneLock,
        reschedule: Callable[[], None],
    ) -> None:
        """All four required."""
        self._capture = capture
        self._renderer = renderer
        self._vtk_lock = vtk_lock
        self._reschedule = reschedule
        self._pending_size = None
        self._last_size = INITIAL_WINDOW_SIZE
        self._pending_events = []
        self._last_frame = None

    @property
    def img_cols_rows(self) -> tuple[NDArray, int, int]:
        """Render and capture under the lock; when another thread holds it, return the last frame and reschedule."""
        if not self._vtk_lock.acquire(blocking=False):
            self._reschedule()
            if self._last_frame is not None:
                return self._last_frame
            return self._placeholder()
        try:
            self._apply_deferred()
            frame = self._capture.img_cols_rows
            self._last_frame = frame
            return frame
        finally:
            self._vtk_lock.release()

    def process_resize_event(self, width: int, height: int) -> None:
        """Record the size; the last size recorded is applied under the lock at the next frame."""
        self._pending_size = (width, height)
        self._last_size = (width, height)

    def process_interaction_event(self, event: dict) -> None:
        """Queue the event; every queued event is forwarded in order under the lock at the next frame."""
        self._pending_events.append(event)

    def _apply_deferred(self) -> None:
        """Apply the last size, forward queued events in order, then record a gesture end once if any forwarded event ends one; caller holds the lock."""
        if self._pending_size is not None:
            self._renderer.set_viewport_size(*self._pending_size)
            self._pending_size = None
        events, self._pending_events = self._pending_events, []
        for event in events:
            self._capture.process_interaction_event(event)
        if any(event["type"] in GESTURE_END_EVENT_TYPES for event in events):
            self._record_gesture_end()

    def _record_gesture_end(self) -> None:
        """Record and publish what a finished gesture changed; caller holds the lock."""
        self._renderer.record_pipeline_camera()
        self._renderer.record_cross_section_plane()

    def _placeholder(self) -> tuple[NDArray, int, int]:
        """A frame of the renderer's background at the last recorded size, (300, 300) before any."""
        cols, rows = self._last_size
        rgb = tuple(round(c * 255) for c in self._renderer.background_rgb)
        return np.full((rows, cols, 3), rgb, dtype=np.uint8), cols, rows

