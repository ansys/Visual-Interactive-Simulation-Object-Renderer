"""
ServerLoopBridge
================
Carries frame requests from any thread onto the trame event loop.

trame-rca's scheduler waits on an ``asyncio.Event`` that is not thread-safe,
so a frame request from a caller thread is handed to the loop through the
:class:`AsyncRunner` that runs the trame server.
"""

from __future__ import annotations

import threading

from trame_rca.view_adapter import RcaViewAdapter

from ansys.visor.viewer.app.trame.async_runner import AsyncRunner
from ansys.visor.viewer.renderer.server_renderer import FrameRequester


class ServerLoopBridge(FrameRequester):
    """Carries frame requests from any thread onto the trame event loop."""

    RETRY_DELAY_S: float = 0.1
    """Delay before a retried frame.

    A retry is requested from inside the scheduler's render step, which clears
    its request event when that step returns; a request made without a delay
    would be erased.
    """

    _async_runner: AsyncRunner
    _view_handler: RcaViewAdapter | None
    _retry_pending: bool

    def __init__(self, async_runner: AsyncRunner) -> None:
        """Unbound until the server is ready."""
        self._async_runner = async_runner
        self._view_handler = None
        self._retry_pending = False

    def bind(self, view_handler: RcaViewAdapter) -> None:
        """Start delivering frame requests to the view handler, then request one frame; runner's thread only.

        Raises:
            RuntimeError: when called from any thread other than the runner's.  The
                handler's scheduler is built on the calling thread's loop, so a handler
                bound from another thread would never render.
        """
        if threading.get_ident() != self._async_runner.thread.ident:
            raise RuntimeError("ServerLoopBridge.bind must run on the AsyncRunner's loop thread")
        self._view_handler = view_handler
        self.request_frame()

    def request_frame(self) -> None:
        """Schedule a render on the loop thread; dropped before bind."""
        view_handler = self._view_handler
        if view_handler is None:
            return
        self._async_runner.call_soon(view_handler.schedule_render)

    def retry_frame(self) -> None:
        """Ask for one frame after RETRY_DELAY_S unless one is pending; loop thread only; dropped before bind."""
        if self._view_handler is None or self._retry_pending:
            return
        self._retry_pending = True
        self._async_runner.call_later(self.RETRY_DELAY_S, self._fire_retry)

    def _fire_retry(self) -> None:
        """Clear the pending mark, then schedule a render."""
        self._retry_pending = False
        self._view_handler.schedule_render()

