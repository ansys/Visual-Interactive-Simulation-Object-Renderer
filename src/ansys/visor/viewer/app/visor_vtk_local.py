"""
VisorVTKLocal
=============
A :class:`~ansys.visor.viewer.app.visor_vtk.VisorVTK` subclass selected when
``rendering_mode=RenderingMode.LOCAL``.

This implementation uses **VTK-WASM** (via trame-vtklocal / LocalView) for
client-side rendering in the browser.

All lifecycle logic (start/stop, add/remove dataset, save/load state, …) is
inherited from :class:`~ansys.visor.viewer.app.visor_vtk.VisorVTK`.
This class only wires the LOCAL-specific scene and trame app.
"""

from __future__ import annotations

from ansys.visor.viewer.app.trame.local_app import LocalApp
from ansys.visor.viewer.app.visor_vtk import VisorVTK
from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger, get_trame_logger
from ansys.visor.viewer.vtk.scene.local_scene import VisorLocalScene

logger = VisorDefaultLogger(__name__)


class VisorVTKLocal(VisorVTK):
    """
    Visor interface for VTK LOCAL mode: browser-side rendering via VTK-WASM.

    All public API is inherited from :class:`VisorVTK`.  Only the rendering
    wiring (scene, trame app) is specific to this class.

    Use ``Visor(rendering_mode=RenderingMode.LOCAL)`` to obtain an instance.
    """

    def _initialize_rendering(self, standalone: bool, trame_log_dir: str | None) -> None:
        """Wire up the LOCAL scene, and LocalApp."""
        dark_mode = self._dark_mode if self._dark_mode is not None else settings.default_dark_mode

        self._scene = VisorLocalScene(self.server, dark_mode=dark_mode)

        self._trame_app = LocalApp(
            self.server,
            lambda: self._scene.get_scene_details_json(),
            lambda request_id, response: self._scene.handle_save_state_response(request_id, response),
            standalone,
            trame_logger=get_trame_logger(trame_log_dir),
            pick_geometry=lambda
                actor_wasm_id,
                cell_id,
                mode,
                world_x,
                world_y,
                world_z: self._scene.pick_geometry(actor_wasm_id, cell_id, mode, world_x, world_y, world_z),
        )

