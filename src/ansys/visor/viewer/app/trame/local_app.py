from logging import Logger
from typing import Callable, Protocol

from trame.app.core import Server
from trame.decorators import TrameApp, trigger
from vtk import vtkObject

from ansys.visor.viewer.app.trame.scene_trigger_app import (
    SceneMutationApi,
    SceneTriggerApp,
    parse_payload,
)
from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick
from ansys.visor.viewer.models.runtime.requests.geometry_pick_payloads import (
    PickGeometryInViewPayload,
    PickPartInViewPayload,
)
from ansys.visor.viewer.models.runtime.requests.pixel_scale_payload import SetPixelScalePayload
from ansys.visor.viewer.vtk.picking.part_cell_hit import PickView

logger = VisorDefaultLogger(__name__)

# Disable VTK warning display
vtkObject.GlobalWarningDisplayOff()


class LocalSceneMutationApi(SceneMutationApi, Protocol):
    """The scene surface LocalApp's triggers call: the shared one plus the client-only pixel scale."""

    def set_pixel_scale(self, pixel_scale: float) -> None: ...


@TrameApp()
class LocalApp(SceneTriggerApp):
    """
    LocalApp serves the scene triggers shared by every rendering mode, plus
    the local-only triggers for part and sub-geometry picking through the
    client's view and client performance reporting, for client-side rendering
    via VTK-WASM in the browser.

    Attributes:
        server (Server): the Trame server instance
    Methods:
        pick_part_in_view: picks the part under a pixel of the client's window
        pick_geometry_in_view: picks the geometry feature under a pixel of the client's window
        perf_report_wasm: reports the performance of the wasm update cycle
        perf_report_server_update: reports the performance of the server update cycle
        set_pixel_scale: sets the device pixel ratio the geometry highlight is drawn at
        set_only_cookie: sets a cookie on the server (note: Trame server only allows a single cookie header)
    """
    def __init__(
            self,
            server: Server,
            get_scene_details_json: callable,
            standalone: bool = True,
            trame_logger: Logger | None = None,
            scene_mutation_api: LocalSceneMutationApi | None = None,
            *,
            pick_geometry_in_view: Callable[[PickView, int, int, str], GeometryPick],
            pick_part_in_view: Callable[[PickView, int, int], int | None],
    ):
        self._pick_geometry_in_view = pick_geometry_in_view
        self._pick_part_in_view = pick_part_in_view
        super().__init__(
            server=server,
            get_scene_details_json=get_scene_details_json,
            standalone=standalone,
            trame_logger=trame_logger,
            scene_mutation_api=scene_mutation_api,
        )

    @property
    def rendering_mode(self) -> RenderingMode:
        """This app serves client-side rendering via VTK-WASM in the browser."""
        return RenderingMode.CLIENT

    @trigger("pick_part_in_view")
    @parse_payload(PickPartInViewPayload)
    def pick_part_in_view(self, payload) -> int | None:
        """Frontend -> Backend: the node under a pixel of the client's window, seen through its camera, or None; selects nothing."""
        view = PickView(camera_state=payload.camera, width=payload.width, height=payload.height)
        return self._pick_part_in_view(view, payload.x, payload.y)

    @trigger("pick_geometry_in_view")
    @parse_payload(PickGeometryInViewPayload)
    def pick_geometry_in_view(self, payload) -> dict:
        """Frontend -> Backend: the geometry feature under a pixel of the client's window, dumped by alias.

        Picked through the client's camera and window size; highlights nothing.
        """
        view = PickView(camera_state=payload.camera, width=payload.width, height=payload.height)
        return self._pick_geometry_in_view(view, payload.x, payload.y, payload.mode).model_dump(by_alias=True)

    @trigger("set_pixel_scale")
    @parse_payload(SetPixelScalePayload)
    def set_pixel_scale(self, payload) -> None:
        """Frontend -> Backend: the client reports its device pixel ratio for the geometry highlight.

        Server mode learns the same ratio from the remote-canvas size report,
        so only client mode registers this.
        """
        api = self._mutation_api("set_pixel_scale", payload)
        if api is None:
            return
        api.set_pixel_scale(payload.scale)

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

