"""Frontend bridge.

This module contains :class:`FrontendBridge`, a small abstraction around making calls
into the frontend (via ``server.js_call``) and correlating async responses.

Important: This class intentionally mirrors the previous logic that lived in
``base.py``. It aims for parity, not enhancements.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Dict, Optional

from pydantic import ValidationError

from ansys.visor.viewer.core.visor_helpers import get_random_javascript_safe_id
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.runtime.requests.visor_load_state_request import VisorLoadStateRequest
from ansys.visor.viewer.models.runtime.requests.visor_save_state_request import VisorSaveStateRequest
from ansys.visor.viewer.models.runtime.requests.visor_save_state_response import VisorSaveStateResponse

logger = VisorDefaultLogger(__name__)


class VisorFrontendBridge:
    """Bridge for JS -> Python request/response flows.

    Currently used for the "getState" request, where the frontend later triggers
    back a payload that we validate and resolve against the pending async waiter.
    """

    def __init__(self, server, ref_name: str):
        self._server = server
        self._ref_name = ref_name

        self._pending_lock = threading.Lock()
        # request_id (int) -> asyncio.Future[VisorSaveStateResponse]
        self._pending_requests: Dict[int, asyncio.Future] = {}
        # The asyncio loop that owns the pending futures (set on first request call)
        self._pending_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_state(self, runtime_app_state) -> int:
        """Send a load-state request to the frontend.

        This method intentionally mirrors the exact logic that previously lived in
        ``VisorScene.apply_state`` (generate request_id, create VisorLoadStateRequest,
        js_call "setState" with model_dump).

        Returns
        -------
        int
            The generated request_id.
        """
        request_id = get_random_javascript_safe_id()
        load_request = VisorLoadStateRequest(request_id=request_id, app_state=runtime_app_state)
        self._server.js_call(self._ref_name, "setState", load_request.model_dump(by_alias=True))
        return int(request_id)

    async def request_state(self, timeout: float) -> VisorSaveStateResponse:
        """Request frontend state and await response.

        Mirrors the previous ``VisorScene.get_state`` request/await logic.
        """
        request_id = get_random_javascript_safe_id()

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        with self._pending_lock:
            # Remember which loop owns these futures so callbacks from other threads can complete them safely.
            self._pending_loop = loop
            self._pending_requests[int(request_id)] = fut

        save_request = VisorSaveStateRequest(request_id=request_id)
        self._server.js_call(self._ref_name, "getState", save_request.model_dump(exclude_none=True, by_alias=True))

        try:
            response = await asyncio.wait_for(fut, timeout=timeout)
        finally:
            with self._pending_lock:
                self._pending_requests.pop(int(request_id), None)
                # If no pending requests remain, clear loop reference to avoid keeping it alive.
                if not self._pending_requests:
                    self._pending_loop = None

        return response

    @staticmethod
    def _threadsafe_set_exception(
            loop: Optional[asyncio.AbstractEventLoop],
            f: asyncio.Future, exc: BaseException
    ) -> None:
        if f is None or f.done():
            return
        if loop is not None:
            loop.call_soon_threadsafe(f.set_exception, exc)
        else:
            # Best-effort fallback (should only happen if no async waiter exists)
            f.set_exception(exc)

    @staticmethod
    def _threadsafe_set_result(
        loop: Optional[asyncio.AbstractEventLoop],
        f: asyncio.Future,
        value: VisorSaveStateResponse,
    ) -> None:
        if f is None or f.done():
            return
        if loop is not None:
            loop.call_soon_threadsafe(f.set_result, value)
        else:
            # Best-effort fallback (should only happen if no async waiter exists)
            f.set_result(value)

    def resolve_save_state_response(self, request_id: int, response: dict) -> None:
        """Resolve a pending request from a frontend callback.

        This is meant to be called by the Trame trigger when the frontend replies.
        """
        # Snapshot loop for threadsafe scheduling (callback may run off the loop thread)
        with self._pending_lock:
            loop = self._pending_loop

        try:
            save_state_response = VisorSaveStateResponse.model_validate(response)
        except ValidationError as e:
            print(f"Invalid save state response received: {e}")
            # Fail fast: if we can't parse the response, any awaiting request call
            # would otherwise hang until timeout. Propagate the error to pending waiters.
            with self._pending_lock:
                fut = self._pending_requests.get(request_id)
            self._threadsafe_set_exception(loop, fut, e)
            raise ValueError(f"Invalid save state response: {e}") from e
        except Exception as e:
            print("Unexpected error while handling save state response")
            with self._pending_lock:
                fut = self._pending_requests.get(request_id)
            self._threadsafe_set_exception(loop, fut, e)
            raise


        with self._pending_lock:
            fut = self._pending_requests.get(request_id)

        if fut:
            self._threadsafe_set_result(loop, fut, save_state_response)
        else:
            logger.warning(f"Late save_state_response with id={request_id} (no pending async waiter)")
