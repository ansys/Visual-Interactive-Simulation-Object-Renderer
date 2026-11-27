import threading
from typing import TYPE_CHECKING

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.vtk.io.client_dataset_normalizer import ClientDatasetNormalizer
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase

if TYPE_CHECKING:
    from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick
    from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
    from ansys.visor.viewer.renderer.local_renderer import VisorLocalRenderer
    from ansys.visor.viewer.vtk.picking.part_cell_hit import PickView

logger = VisorDefaultLogger(__name__)

from trame_server import Server

# =============================================================================
# VisorScene — wasm/LocalView subclass (the original production scene)
# =============================================================================

class VisorLocalScene(VisorSceneBase):
    """
    Coordinator for a Visor viewer scene using the wasm/LocalView rendering path.

    :meth:`get_state` is the base class's server-side build and asks the
    frontend for nothing.  :meth:`apply_state` pushes the restored state to
    the frontend via a JS ``set_state`` call through :class:`VisorFrontendBridge`.

    This is the scene used by
    :class:`~ansys.visor.viewer.app.visor_vtk_local.VisorVTKLocal`
    (``RenderingMode.CLIENT``).
    """

    _renderer: "VisorLocalRenderer"

    def __init__(self, server: Server, dark_mode: bool = False):
        from ansys.visor.viewer.renderer.local_renderer import VisorLocalRenderer
        from ansys.visor.viewer.vtk.scene.visor_frontend_bridge import VisorFrontendBridge

        try:
            vtk_renderer = VisorLocalRenderer(server)
            super().__init__(server, dark_mode, renderer=vtk_renderer, vtk_lock=threading.RLock())
            self._frontend_bridge = VisorFrontendBridge(server, self._renderer.frontend_ref_name)
        except RuntimeError as e:
            msg = f"Failed to initialize VTK pipeline: {e}"
            logger.error(msg)
            raise RuntimeError(msg) from e

    # -------------------------------------------------------------------------
    # Dataset admission — arrays the wasm32 client cannot read
    # -------------------------------------------------------------------------

    def check_dataset(self, input: VisorDatasetType) -> None:
        """Raise ValueError naming each vtkIdTypeArray, vtkLongArray or vtkUnsignedLongArray in the point or cell data.

        The wasm32 client reads those classes at a different element width
        from the server's (an upstream VTK serialization defect), so their
        values arrive wrong.  The check does not depend on the host's
        ``long`` width.  Files Visor reads are already converted by
        ``file_to_dataset``; an in-memory dataset is rejected, not converted.
        """
        labels = ClientDatasetNormalizer.platform_width_attribute_arrays(input)
        if labels:
            msg = (
                f"CLIENT mode cannot display {', '.join(labels)}: the wasm32 client misreads "
                "vtkIdTypeArray, vtkLongArray and vtkUnsignedLongArray.  Convert these arrays to "
                "vtkTypeInt64Array or vtkTypeUInt64Array before adding the dataset."
            )
            logger.error(msg)
            raise ValueError(msg)

    # -------------------------------------------------------------------------
    # State delivery hook — wasm: JS set_state
    # -------------------------------------------------------------------------

    def _push_runtime_state(self, runtime_app_state: "RuntimeAppState") -> None:
        """
        Flush the VTK window then push the restored state to the React frontend.

        Use render_window_only() — NOT the full render() which also calls
        local_view.update().  local_view.update() fires onServerUpdateAsync on
        the React frontend, which clears the setState event listener while it
        rebuilds the scene.  If the set_state() JS call below arrives during
        that window the persisted state is silently lost.
        finalize_scene() (called from apply_state, in the statement immediately
        before this one) has already done a full render + wasm sync; all we need
        here is a lightweight VTK flush before the JS payload is sent.
        """
        self._renderer.render_window_only()
        self._frontend_bridge.set_state(runtime_app_state)

    # -------------------------------------------------------------------------
    # Picking — through the client's view, on the server picker
    # -------------------------------------------------------------------------

    def set_pixel_scale(self, pixel_scale: float) -> None:
        """Draw the geometry highlight at this many device pixels per CSS pixel; no push, no notify.

        The next highlight shown carries the new size to the client.
        """
        with self._vtk_lock:
            self._renderer.set_pixel_scale(pixel_scale)

    def pick_part_in_view(self, view: "PickView", x: int, y: int) -> int | None:
        """Find the part under a pixel of a client's view, under the scene lock."""
        with self._vtk_lock:
            return self._renderer.pick_part_in_view(view, x, y)

    def pick_geometry_in_view(self, view: "PickView", x: int, y: int, mode: str) -> "GeometryPick":
        """Find the geometry feature under a pixel of a client's view, under the scene lock."""
        with self._vtk_lock:
            return self._renderer.pick_geometry_in_view(view, x, y, mode)

    # -------------------------------------------------------------------------
    # Wasm-specific helpers (not part of VisorSceneBase)
    # -------------------------------------------------------------------------

    def cleanup_state(self) -> None:
        """Remove transient wasm keys from trame server state."""
        self._server.state.pop("wasm_ids", None)
        self._server.state.pop("wasm_ref_name", None)
        self._server.state.pop("perf_logging", None)

