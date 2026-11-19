"""
VisorParaviewScene
==================
:class:`VisorSceneBase` for a scene rendered by pvserver and streamed to the
client through trame-rca.

Each dataset is read locally for the scene graph and opened again on pvserver
from the same file, under a key this scene assigns.  Removing the dataset
deletes its pvserver source.  Picking is not supported: both picks log a
warning and return nothing.
"""

from __future__ import annotations

import itertools
import threading
from typing import TYPE_CHECKING

from trame_server import Server

from ansys.visor.viewer.core.errors import UnsupportedInModeError
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.runtime.picking.geometry_pick import NoGeometryPick
from ansys.visor.viewer.renderer.paraview_capture import ParaviewCapture
from ansys.visor.viewer.renderer.paraview_renderer import ParaviewRenderer
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow
from ansys.visor.viewer.renderer.streamed_protocols import BACKGROUND_RGB
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase

if TYPE_CHECKING:
    from ansys.visor.viewer.app.trame.server_loop_bridge import ServerLoopBridge
    from ansys.visor.viewer.core.metadata import ExtendedMetadata
    from ansys.visor.viewer.core.visor_types import VisorDatasetType
    from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick
    from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
    from ansys.visor.viewer.renderer.paraview_session import ParaviewSession
    from ansys.visor.viewer.renderer.streamed_protocols import ViewRecordPublisher

logger = VisorDefaultLogger(__name__)


class VisorParaviewScene(VisorSceneBase):
    """Coordinator for a scene rendered by pvserver and streamed to the client."""

    _renderer: ParaviewRenderer
    _rca_window: VisorRcaWindow

    def __init__(
        self,
        server: Server,
        dark_mode: bool,
        bridge: ServerLoopBridge,
        view_record_publisher: ViewRecordPublisher,
        session: ParaviewSession,
    ) -> None:
        """Build the ParaviewRenderer over session, then the RCA window over its capture and this scene's lock."""
        self._key_counter = itertools.count()
        self._dataset_keys: dict[int, str] = {}
        renderer = ParaviewRenderer(session, BACKGROUND_RGB[dark_mode], bridge, view_record_publisher)
        super().__init__(server, dark_mode, renderer=renderer, vtk_lock=threading.RLock())
        self._rca_window = VisorRcaWindow(
            ParaviewCapture(session, renderer.flush_writes),
            renderer,
            self._vtk_lock,
            bridge.retry_frame,
        )

    @property
    def rca_window(self) -> VisorRcaWindow:
        """The trame-rca area the app streams."""
        return self._rca_window

    def add_dataset(self, input: VisorDatasetType, metadata: ExtendedMetadata) -> int:
        """Open the server path on pvserver under a fresh key, then add as the base does, under the scene lock.

        The source is closed again if the base add fails.
        """
        with self._vtk_lock:
            dataset_key = f"pv-{next(self._key_counter)}"
            self._renderer.open_source(dataset_key, self.server_path(metadata), local_root=input)
            try:
                dataset_id = super().add_dataset(input, metadata)
            except Exception:
                self._renderer.close_source(dataset_key)
                raise
            self._dataset_keys[dataset_id] = dataset_key
            return dataset_id

    def remove_dataset(self, dataset_id: int) -> None:
        """Remove as the base does, then delete the dataset's pvserver source, under the scene lock."""
        with self._vtk_lock:
            super().remove_dataset(dataset_id)
            dataset_key = self._dataset_keys.pop(dataset_id, None)
            if dataset_key is None:
                logger.debug("remove_dataset: no pvserver source for dataset %s; skipping.", dataset_id)
                return
            self._renderer.close_source(dataset_key)

    def clear(self) -> None:
        """Clear as the base does, which deletes every pvserver source, then forget every dataset key."""
        with self._vtk_lock:
            super().clear()
            self._dataset_keys.clear()

    def pick_part_at(self, x: int, y: int) -> int | None:
        """None, logged at WARNING: part picking is not supported."""
        logger.warning("part picking is not supported in PARAVIEW mode")
        return None

    def pick_geometry_at(self, x: int, y: int, mode: str) -> GeometryPick:
        """An empty pick, logged at WARNING: geometry picking is not supported."""
        logger.warning("geometry picking is not supported in PARAVIEW mode")
        return NoGeometryPick()

    def set_dark_mode(self, dark_mode: bool) -> None:
        """Set the theme on the UI record and re-colour the background, under the scene lock; requests one frame."""
        with self._vtk_lock:
            self.dark_mode = dark_mode
            self._apply_background()
            self._renderer.render()

    def _apply_background(self) -> None:
        """Set the renderer background from the current theme; caller holds the lock."""
        self._renderer.set_background_rgb(BACKGROUND_RGB[self.dark_mode])

    def _push_runtime_state(self, runtime_app_state: RuntimeAppState) -> None:
        """Re-colour the background from the restored theme, then request a frame."""
        self._apply_background()
        self._renderer.render()

    @staticmethod
    def server_path(metadata: ExtendedMetadata) -> str:
        """The file pvserver opens: the restored snapshot when loading state, else the input file.

        Raises :class:`UnsupportedInModeError` when the metadata names neither:
        pvserver can only open a file.
        """
        snapshot_path = metadata.state.serialized_dataset_path
        if snapshot_path:
            return snapshot_path
        if metadata.file_path:
            return metadata.file_path
        raise UnsupportedInModeError("in-memory dataset input is not supported in PARAVIEW mode")
