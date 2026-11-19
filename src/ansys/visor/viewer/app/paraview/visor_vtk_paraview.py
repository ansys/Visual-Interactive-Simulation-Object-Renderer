"""
VisorVTKParaview
================
A :class:`~ansys.visor.viewer.app.visor_vtk.VisorVTK` subclass whose scene is
rendered by a pvserver and streamed to the browser through trame-rca.

The ParaView session is connected by the caller and injected.  Constructed
with keywords only: ``VisorVTK.__new__`` accepts no positional argument other
than the rendering mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ansys.visor.viewer.app.trame.paraview_app import ParaviewApp
from ansys.visor.viewer.app.trame.server_loop_bridge import ServerLoopBridge
from ansys.visor.viewer.app.trame.server_state_publisher import ServerStatePublisher
from ansys.visor.viewer.app.visor_vtk import VisorVTK
from ansys.visor.viewer.core.errors import UnsupportedInModeError
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_logging import get_trame_logger
from ansys.visor.viewer.vtk.scene.paraview_scene import VisorParaviewScene

if TYPE_CHECKING:
    from ansys.visor.viewer.core.pvserver_address import PvserverAddress
    from ansys.visor.viewer.renderer.paraview_session import ParaviewSession


class VisorVTKParaview(VisorVTK):
    """VisorVTK for PARAVIEW mode: the scene renders through a pvserver and is streamed through trame-rca."""

    _state_publisher: ServerStatePublisher

    def __init__(
        self,
        *,
        url: str | None,
        standalone: bool,
        dark_mode: bool | None,
        trame_log_dir: str | None,
        pvserver: PvserverAddress,
        session: ParaviewSession,
    ) -> None:
        """Store the pvserver address and the connected session, then build the base.

        Both are stored first because the base constructor builds the scene.
        """
        self._pvserver = pvserver
        self._session = session
        super().__init__(
            url=url,
            rendering_mode=RenderingMode.PARAVIEW,
            standalone=standalone,
            dark_mode=dark_mode,
            trame_log_dir=trame_log_dir,
        )

    def _initialize_rendering(self, standalone: bool, trame_log_dir: str | None) -> None:
        """Wire the bridge, the state publisher, the ParaView scene and ParaviewApp.

        One bridge serves both: the scene's renderer requests frames through
        it, and the app binds it to the view handler when the server is ready.
        """
        bridge = ServerLoopBridge(self._server_manager.async_runner)
        self._state_publisher = ServerStatePublisher(self._server_manager.async_runner, self.server.state)

        self._scene = VisorParaviewScene(
            self.server,
            dark_mode=self._dark_mode,
            bridge=bridge,
            view_record_publisher=self._state_publisher,
            session=self._session,
        )

        self._trame_app = ParaviewApp(
            self.server,
            lambda: self._scene.get_scene_details_json(),
            standalone,
            trame_logger=get_trame_logger(trame_log_dir),
            scene_mutation_api=self._scene,
            pick_part_at=self._scene.pick_part_at,
            pick_geometry_at=self._scene.pick_geometry_at,
            set_dark_mode=self._scene.set_dark_mode,
            rca_window=self._scene.rca_window,
            bridge=bridge,
        )

    def _post_scene_change_hook(self) -> None:
        """Bump scene_version so connected clients rebuild; requests no frame, the operation already did."""
        self._state_publisher.bump_scene_version()

    def update_variables(self, dataset_id: int, variables: list[dict[str, Any]]) -> None:
        """Raise UnsupportedInModeError: pvserver holds its own copy of the arrays."""
        raise UnsupportedInModeError("update_variables is not supported in PARAVIEW mode")
