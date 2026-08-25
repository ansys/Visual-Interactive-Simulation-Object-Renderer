from typing import TYPE_CHECKING

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase

if TYPE_CHECKING:
    from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState

logger = VisorDefaultLogger(__name__)

from trame_server import Server

# =============================================================================
# VisorScene — wasm/LocalView subclass (the original production scene)
# =============================================================================

class VisorLocalScene(VisorSceneBase):
    """
    Coordinator for a Visor viewer scene using the wasm/LocalView rendering path.

    The React frontend is authority for camera state.  :meth:`get_state` asks
    the frontend for the current camera via :class:`VisorFrontendBridge` and
    waits for the response.  :meth:`apply_state` pushes the restored state back
    to the frontend via a JS ``set_state`` call.

    This is the scene used by
    :class:`~ansys.visor.viewer.app.visor_vtk_local.VisorVTKLocal`
    (``RenderingMode.LOCAL``).
    """

    def __init__(self, server: Server, dark_mode: bool = False):
        from ansys.visor.viewer.renderer.local_renderer import VisorLocalRenderer
        from ansys.visor.viewer.vtk.scene.visor_frontend_bridge import VisorFrontendBridge

        try:
            vtk_renderer = VisorLocalRenderer(server)
            super().__init__(server, dark_mode, renderer=vtk_renderer)
            self._frontend_bridge = VisorFrontendBridge(server, self._renderer.frontend_ref_name)
        except RuntimeError as e:
            msg = f"Failed to initialize VTK pipeline: {e}"
            logger.error(msg)
            raise RuntimeError(msg) from e

    # -------------------------------------------------------------------------
    # State authority hooks — wasm: frontend round-trip
    # -------------------------------------------------------------------------

    async def _get_runtime_state_async(self, timeout: float) -> "RuntimeAppState":
        """Ask the React frontend for the current app state (camera, UI, …)."""
        response = await self._frontend_bridge.request_state(timeout=timeout)
        return response.app_state

    def _apply_runtime_state_to_render(self, runtime_app_state: "RuntimeAppState") -> None:
        """
        Flush the VTK window then push the restored state to the React frontend.

        Use render_window_only() — NOT the full render() which also calls
        local_view.update().  local_view.update() fires onServerUpdateAsync on
        the React frontend, which clears the setState event listener while it
        rebuilds the scene.  If the set_state() JS call below arrives during
        that window the persisted state is silently lost.
        finalize_scene() (called just before apply_state when loading from an
        empty scene) has already done a full render + wasm sync; all we need
        here is a lightweight VTK flush before the JS payload is sent.
        """
        self._renderer.render_window_only()
        self._frontend_bridge.set_state(runtime_app_state)

    # -------------------------------------------------------------------------
    # Wasm-specific helpers (not part of VisorSceneBase)
    # -------------------------------------------------------------------------

    def handle_save_state_response(self, request_id: int, response: dict) -> None:
        """Called by LocalApp trigger when the frontend responds."""
        self._frontend_bridge.resolve_save_state_response(request_id, response)

    def cleanup_state(self) -> None:
        """Remove transient wasm keys from trame server state."""
        self._server.state.pop("wasm_ids", None)
        self._server.state.pop("wasm_ref_name", None)
        self._server.state.pop("perf_logging", None)

