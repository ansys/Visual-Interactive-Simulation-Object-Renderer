"""
ServerApp
=========
Trame app for server-side rendering: the shared scene triggers, part picking,
the client theme report, and the trame-rca area the rendered frames stream
through.
"""

from __future__ import annotations

from logging import Logger
from typing import Callable

from pydantic import BaseModel
from trame.app.core import Server
from trame.decorators import TrameApp, trigger
from trame_rca.widgets.rca import RemoteControlledArea

from ansys.visor.viewer.app.trame.scene_trigger_app import (
    SceneMutationApi,
    SceneTriggerApp,
    parse_payload,
)
from ansys.visor.viewer.app.trame.server_loop_bridge import ServerLoopBridge
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.renderer.server_window import VisorRcaWindow

RCA_AREA_NAME: str = "view"
"""Name of the trame-rca area the client subscribes to."""


class PickPartAtPayload(BaseModel):
    """Payload of the pick_part_at trigger: render-window device pixels, origin bottom-left."""

    x: int
    y: int


class SetDarkThemePayload(BaseModel):
    """Payload of the set_dark_theme trigger."""

    dark: bool


@TrameApp()
class ServerApp(SceneTriggerApp):
    """Serves the scene triggers, part picking and the streamed view for server-side rendering."""

    def __init__(
        self,
        server: Server,
        get_scene_details_json: Callable[[], str],
        standalone: bool,
        trame_logger: Logger | None,
        scene_mutation_api: SceneMutationApi,
        pick_part_at: Callable[[int, int], int | None],
        set_dark_mode: Callable[[bool], None],
        rca_window: VisorRcaWindow,
        bridge: ServerLoopBridge,
    ) -> None:
        """Create the area before start; the view handler is built when the server is ready."""
        self._pick_part_at = pick_part_at
        self._set_dark_mode = set_dark_mode
        self._rca_window = rca_window
        self._bridge = bridge
        super().__init__(
            server=server,
            get_scene_details_json=get_scene_details_json,
            standalone=standalone,
            trame_logger=trame_logger,
            scene_mutation_api=scene_mutation_api,
        )
        # The server is passed explicitly: a widget left to resolve its own
        # would register the stream protocol on the default server.
        self._rca_area = RemoteControlledArea(name=RCA_AREA_NAME, trame_server=server)

        @self.server.controller.add("on_server_ready")
        def bind_stream(**_):
            self._bind_stream()

    @property
    def rendering_mode(self) -> RenderingMode:
        """RenderingMode.SERVER."""
        return RenderingMode.SERVER

    def _bind_stream(self) -> None:
        """Build the view handler over the RCA window and bind the bridge to it; loop thread, server ready.

        The encoder is named because trame-rca ignores the fps and quality
        arguments without one.
        """
        view_handler = self._rca_area.create_view_handler(
            self._rca_window,
            encoder="jpeg",
            target_fps=30.0,
            interactive_quality=60,
            still_quality=90,
        )
        self._bridge.bind(view_handler)

    @trigger("pick_part_at")
    @parse_payload(PickPartAtPayload)
    def pick_part_at(self, payload) -> int | None:
        """Frontend -> Backend: the node under a render-window pixel, or None; selects nothing."""
        return self._pick_part_at(payload.x, payload.y)

    @trigger("set_dark_theme")
    @parse_payload(SetDarkThemePayload)
    def set_dark_theme(self, payload) -> None:
        """Frontend -> Backend: the theme the client shows; the streamed background follows it."""
        self._set_dark_mode(payload.dark)

