import urllib.parse
from logging import Logger
from typing import List, Optional, Protocol

from trame.app.core import Server
from trame.decorators import TrameApp, trigger
from vtk import vtkObject

from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)

# Disable VTK warning display
vtkObject.GlobalWarningDisplayOff()


class ScenePartStateApi(Protocol):
    """Structural type of the per-part coordinator surface LocalApp calls.

    Typing only: there is no ``runtime_checkable`` decoration and no
    ``isinstance`` check anywhere against it.  Declaring it here rather than
    importing the scene keeps this module free of any scene type, so the
    injected object remains LocalApp's only route to the scene.
    """

    def set_part_visibility(self, node_id: int, visible: bool) -> None: ...

    def set_part_opacity(self, node_id: int, opacity: float) -> None: ...

    def set_part_diffuse_color(self, node_id: int, diffuse_rgb: Optional[List[float]]) -> None: ...

    def set_part_selected(self, node_id: int, selected: bool) -> None: ...

    def set_part_color_variable(
        self,
        node_id: int,
        variable_id: str,
        association: VisorVtkVariableType,
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> None: ...

    def clear_part_color_variable(self, node_id: int) -> None: ...



@TrameApp()
class LocalApp:
    """
    LocalApp is a class that provides an interface for initializing and managing a visualization application
    using the VTK rendering engine.
    It supports server-based rendering and interaction with a visualization pipeline.
    Attributes:
        server (Server): the Trame server instance
    Methods:
        get_scene_details_json: returns the scene details in JSON format
        save_state_response: sends the current app state as payload
        pick_geometry: picks the geometry for rendering
        perf_report_wasm: reports the performance of the wasm update cycle
        perf_report_server_update: reports the performance of the server update cycle
        set_part_visibility: sets whether one part is visible
        set_part_opacity: sets one part's opacity
        set_part_diffuse_color: sets or clears one part's custom diffuse colour
        set_part_selected: selects or deselects one part
        set_part_color_variable: colours one part by a scalar variable
        clear_part_color_variable: stops colouring one part by a scalar variable
        set_only_cookie: sets a cookie on the server (note: Trame server only allows a single cookie header)
    Protected Methods:
        _cleanup(): Cleans up the active actor in the visualization pipeline.
    """
    def __init__(
            self,
            server: Server,
            get_scene_details_json: callable,
            handle_save_state_response: callable,
            standalone: bool = True,
            trame_logger: Logger | None = None,
            pick_geometry=None,
            scene_part_state_api: ScenePartStateApi | None = None,
    ):
        self.server = server
        # Callable to get the scene details in JSON format
        self._get_scene_details_json = get_scene_details_json
        # Callable to handle the save state response from the frontend
        self._handle_save_state_response = handle_save_state_response
        # Callable for sub-geometry picking (optional)
        self._pick_geometry = pick_geometry
        # Per-part visual state coordinator (see ScenePartStateApi).  The one
        # production construction site always supplies it; it is optional so
        # that the class stays constructible without a scene.
        self._scene_part_state_api = scene_part_state_api
        # logger for logging trame server lifecycle info
        self.__trame_logger = trame_logger

        """ Set up lifecycle hooks. """
        self._register_lifecycle_hooks()
        self._set_headers()
        self._set_www_path(standalone)

    def _register_lifecycle_hooks(self):
        """ Register server lifecycle event handlers for extra trame logging. """

        @self.server.controller.add("on_server_start")
        def server_start(_):
            if self.__trame_logger:
                self.__trame_logger.debug("Starting server")

        @self.server.controller.add("on_server_ready")
        def server_ready(**state):
            print(f"Server started and ready on {self.server.name}")
            if self.__trame_logger:
                self.__trame_logger.debug("Server is ready.")

        @self.server.controller.add("on_client_connected")
        def client_connected():
            if self.__trame_logger:
                self.__trame_logger.debug("Client connected.")

        @self.server.controller.add("on_client_exited")
        def client_exited():
            if self.__trame_logger:
                self.__trame_logger.debug("Client exited.")

        @self.server.controller.add("on_server_exited")
        def server_exited(**state):
            print("Server stopped")
            if self.__trame_logger:
                self.__trame_logger.debug("Server is exiting.")

    def _set_headers(self):
        """ Set HTTP headers for the server."""
        # If a Dash client is connecting to this Trame server,
        # the Dash client will be running on a different port, so
        # we need to allow cross-origin access to it.
        self.server.http_headers.set_header("Access-Control-Allow-Origin", "*")
        # Always serve assets fresh (not from cache). This
        # will save us some headaches in the future.
        self.server.http_headers.set_header("Cache-Control", "max-age=0")

    def _set_www_path(self, standalone: bool):
        """ Set the www path for the server based on the standalone flag."""
        self.server._www = settings.get_client_bundle(standalone)
        logger.debug(f"Standalone client path: {self.server._www}")

    @trigger("get_visor_scene_details_json")
    def get_visor_scene_details_json(self):
        """ returns the scene details in JSON format. """
        return self._get_scene_details_json()

    @trigger("save_state_response")
    def save_state_response(self, request_id: int, payload: dict):
        """Frontend → Backend: the frontend sends the current app state as payload."""
        return self._handle_save_state_response(request_id, payload)

    @trigger("pick_geometry")
    def pick_geometry(self, actor_wasm_id, cell_id, mode: str, world_x: float, world_y: float, world_z: float):
        """Frontend → Backend: perform sub-geometry picking given a WASM actor/cell ID and world-space point."""
        if self._pick_geometry is None:
            return {"found": False}
        return self._pick_geometry(actor_wasm_id, cell_id, mode, world_x, world_y, world_z)

    @trigger("perf_report_wasm")
    def perf_report_wasm(self, payload: dict):
        """
        Frontend -> Backend: client ships its updateAsync perf counters after
        each wasm update cycle. Written as a [PERF] line so PerfLogReader can
        include client-side timing in the same JSON report.
        Silently ignored when perf logging is disabled.
        """
        if not settings.perf_logging:
            return
        c = payload
        logger.info(
            f"[PERF] client updateAsync"
            f" | states={c.get('stateCount', 0)} ({c.get('stateTotalBytes', 0) / 1e6:.3f} MB)"
            f" | blobs={c.get('blobCount', 0)} ({c.get('blobTotalBytes', 0) / 1e6:.3f} MB total"
            f", largest={c.get('blobMaxBytes', 0) / 1e6:.3f} MB in {c.get('blobMaxDur', 0):.2f}ms)"
            f" | wasm={c.get('wasmMs', 0):.2f}ms resize={c.get('resizeMs', 0):.2f}ms"
            f" | total={c.get('totalMs', 0):.2f}ms"
        )

    @trigger("perf_report_server_update")
    def perf_report_server_update(self, payload: dict):
        """
        Frontend -> Backend: client ships the onServerUpdateAsync duration —
        the React UI rebuild triggered by the trame state change, after the
        wasm cycle completes.
        Silently ignored when perf logging is disabled.
        """
        if not settings.perf_logging:
            return
        logger.info(
            f"[PERF] client onServerUpdateAsync"
            f" | handler={payload.get('handlerMs', 0):.2f}ms"
        )

    # ------------------------------------------------------------------
    # Per-part visual state triggers
    #
    # Frontend -> Backend.  Each takes a single ``payload: dict`` argument and
    # returns ``None``; each delegates to the identically-named method on the
    # injected coordinator.  Every payload carries the absolute target value,
    # never a toggle or a delta, so a message the client suppresses as
    # redundant is indistinguishable from one that set a value a part already
    # had.  Required payload keys are read directly: a missing key raises
    # KeyError on the trame event-loop thread, which is accepted because the
    # only caller is the client written against this contract.
    # ------------------------------------------------------------------

    def _part_state_api(self, trigger_name: str) -> ScenePartStateApi | None:
        """Return the injected coordinator, or ``None`` after logging."""
        if self._scene_part_state_api is None:
            logger.debug("%s: no scene part-state API injected; ignoring.", trigger_name)
            return None
        return self._scene_part_state_api

    @trigger("set_part_visibility")
    def set_part_visibility(self, payload: dict) -> None:
        """Frontend -> Backend: set whether one part is visible."""
        api = self._part_state_api("set_part_visibility")
        if api is None:
            return
        api.set_part_visibility(payload["nodeId"], payload["visible"])

    @trigger("set_part_opacity")
    def set_part_opacity(self, payload: dict) -> None:
        """Frontend -> Backend: set one part's opacity."""
        api = self._part_state_api("set_part_opacity")
        if api is None:
            return
        api.set_part_opacity(payload["nodeId"], payload["opacity"])

    @trigger("set_part_diffuse_color")
    def set_part_diffuse_color(self, payload: dict) -> None:
        """Frontend -> Backend: set one part's custom diffuse colour.

        ``diffuseRgb`` of ``None`` clears the custom colour and is forwarded
        as ``None``; no default colour is substituted here.
        """
        api = self._part_state_api("set_part_diffuse_color")
        if api is None:
            return
        api.set_part_diffuse_color(payload["nodeId"], payload["diffuseRgb"])

    @trigger("set_part_selected")
    def set_part_selected(self, payload: dict) -> None:
        """Frontend -> Backend: select or deselect one part.

        No colour crosses this trigger: the server reads the part's stored
        diffuse colour from its own record.
        """
        api = self._part_state_api("set_part_selected")
        if api is None:
            return
        api.set_part_selected(payload["nodeId"], payload["selected"])

    @trigger("set_part_color_variable")
    def set_part_color_variable(self, payload: dict) -> None:
        """Frontend -> Backend: colour one part by a scalar variable.

        ``association`` is parsed here, at the boundary, into a
        :class:`VisorVtkVariableType` by exact value lookup -- never
        upper-cased, never passed on as a bare string.  A value that is not a
        member is a logged no-op, matching the posture the pipeline takes on an
        unknown array name.  ``variableId`` is forwarded verbatim and is never
        parsed by the server.
        """
        api = self._part_state_api("set_part_color_variable")
        if api is None:
            return
        try:
            association = VisorVtkVariableType(payload["association"])
        except ValueError:
            logger.warning(
                "set_part_color_variable: %r is not a VisorVtkVariableType; ignoring.",
                payload["association"],
            )
            return
        api.set_part_color_variable(
            payload["nodeId"],
            payload["variableId"],
            association,
            payload["arrayName"],
            payload["component"],
            payload["min"],
            payload["max"],
        )

    @trigger("clear_part_color_variable")
    def clear_part_color_variable(self, payload: dict) -> None:
        """Frontend -> Backend: stop colouring one part by a scalar variable."""
        api = self._part_state_api("clear_part_color_variable")
        if api is None:
            return
        api.clear_part_color_variable(payload["nodeId"])

    def set_only_cookie(self, key: str, value: str):
        """
        Sets a cookie on the server. NOTE: there is a limitation
        with Trame server whereby it only allows you to set a single cookie header.
        """
        key = urllib.parse.quote(key)
        value = urllib.parse.quote(value)
        self.server.http_headers.set_header("Set-Cookie", f"{key}={value};Path=/;")
