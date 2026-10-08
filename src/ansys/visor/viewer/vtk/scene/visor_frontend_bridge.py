"""Frontend bridge.

This module contains :class:`VisorFrontendBridge`, a small abstraction around making
calls into the frontend via ``server.js_call``.
"""

from __future__ import annotations

from ansys.visor.viewer.core.visor_helpers import get_random_javascript_safe_id
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.runtime.requests.visor_load_state_request import VisorLoadStateRequest

logger = VisorDefaultLogger(__name__)


class VisorFrontendBridge:
    """Bridge for Python -> JS calls.

    Sends the "setState" call that delivers a loaded state to the frontend.
    The call is fire-and-forget: nothing waits for a reply.
    """

    def __init__(self, server, ref_name: str):
        self._server = server
        self._ref_name = ref_name

    def set_state(self, runtime_app_state) -> int:
        """Send a load-state request to the frontend.

        Generates a request id, wraps the state in a ``VisorLoadStateRequest``
        and sends it with js_call "setState".

        Returns
        -------
        int
            The generated request_id.
        """
        request_id = get_random_javascript_safe_id()
        load_request = VisorLoadStateRequest(request_id=request_id, app_state=runtime_app_state)
        self._server.js_call(self._ref_name, "setState", load_request.model_dump(by_alias=True))
        return int(request_id)
