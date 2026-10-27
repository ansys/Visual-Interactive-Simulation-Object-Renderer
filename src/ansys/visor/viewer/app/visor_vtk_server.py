"""
VisorVTKServer
==============
A :class:`~ansys.visor.viewer.app.visor_vtk.VisorVTK` subclass selected when
``rendering_mode=RenderingMode.SERVER``.

The scene is rendered off-screen on the server and streamed to the browser
through trame-rca.

All lifecycle logic is inherited from
:class:`~ansys.visor.viewer.app.visor_vtk.VisorVTK`.  This class only wires
the SERVER-specific bridge, scene and trame app.
"""

from __future__ import annotations

from ansys.visor.viewer.app.trame.server_app import ServerApp
from ansys.visor.viewer.app.trame.server_loop_bridge import ServerLoopBridge
from ansys.visor.viewer.app.trame.server_state_publisher import ServerStatePublisher
from ansys.visor.viewer.app.visor_vtk import VisorVTK
from ansys.visor.viewer.core.visor_logging import get_trame_logger
from ansys.visor.viewer.vtk.scene.server_scene import VisorServerScene


class VisorVTKServer(VisorVTK):
    """Visor interface for VTK SERVER mode: server-side off-screen rendering streamed through trame-rca."""

    _state_publisher: ServerStatePublisher

    def _initialize_rendering(self, standalone: bool, trame_log_dir: str | None) -> None:
        """Wire the bridge, the state publisher, the server scene and ServerApp.

        One bridge serves both: the scene's renderer requests frames through
        it, and the app binds it to the view handler when the server is ready.
        The publisher writes the renderer's camera record into this viewer's
        server state, and the scene_version bump after each scene change.
        """
        bridge = ServerLoopBridge(self._server_manager.async_runner)
        self._state_publisher = ServerStatePublisher(self._server_manager.async_runner, self.server.state)

        self._scene = VisorServerScene(
            self.server, dark_mode=self._dark_mode, bridge=bridge, camera_publisher=self._state_publisher
        )

        self._trame_app = ServerApp(
            self.server,
            lambda: self._scene.get_scene_details_json(),
            standalone,
            trame_logger=get_trame_logger(trame_log_dir),
            scene_mutation_api=self._scene,
            pick_part_at=self._scene.pick_part_at,
            set_dark_mode=self._scene.set_dark_mode,
            rca_window=self._scene.rca_window,
            bridge=bridge,
        )

    def _post_scene_change_hook(self) -> None:
        """Bump scene_version so connected clients rebuild; requests no frame, the operation already did."""
        self._state_publisher.bump_scene_version()

