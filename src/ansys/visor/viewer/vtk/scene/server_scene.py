"""
VisorServerScene
================
:class:`VisorSceneBase` for a scene rendered on the server and streamed to the
client through trame-rca.

The streamed frames carry no transparency, so the window clears to the
client's viewer background for the current theme rather than leaving the
background to the page's CSS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trame_rca.rca import VtkRemoteControlledArea
from trame_server import Server

from ansys.visor.viewer.renderer.server_renderer import ServerRenderer
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow
from ansys.visor.viewer.vtk.scene.base import VisorSceneBase

if TYPE_CHECKING:
    from ansys.visor.viewer.app.trame.server_loop_bridge import ServerLoopBridge
    from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
    from ansys.visor.viewer.renderer.server_renderer import CameraPublisher

BACKGROUND_RGB: dict[bool, tuple[float, float, float]] = {
    False: (247 / 255, 247 / 255, 247 / 255),
    True: (54 / 255, 60 / 255, 67 / 255),
}
"""Viewer background per theme, keyed on dark.

The values of ``--visor-viewer-background`` in the client's
``public/css/theme-light.css`` and ``public/css/theme-dark.css``.
"""


class VisorServerScene(VisorSceneBase):
    """Coordinator for a viewer scene rendered on the server and streamed to the client."""

    _renderer: ServerRenderer
    _rca_window: VisorRcaWindow

    def __init__(
        self,
        server: Server,
        dark_mode: bool,
        bridge: ServerLoopBridge,
        camera_publisher: CameraPublisher,
    ) -> None:
        """Build the ServerRenderer and the RCA window over this scene's lock."""
        renderer = ServerRenderer(BACKGROUND_RGB[dark_mode], bridge, camera_publisher)
        super().__init__(server, dark_mode, renderer=renderer)
        self._rca_window = VisorRcaWindow(
            VtkRemoteControlledArea(renderer.render_window),
            renderer,
            self._vtk_lock,
            bridge.retry_frame,
        )

    @property
    def rca_window(self) -> VisorRcaWindow:
        """The trame-rca area the app streams."""
        return self._rca_window

    def pick_part_at(self, x: int, y: int) -> int | None:
        """Return the node under a render-window pixel, under the scene lock."""
        with self._vtk_lock:
            return self._renderer.pick_part_at(x, y)

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

