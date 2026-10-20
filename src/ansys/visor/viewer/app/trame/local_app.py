from logging import Logger

from trame.app.core import Server
from trame.decorators import TrameApp, trigger
from vtk import vtkObject

from ansys.visor.viewer.app.trame.scene_trigger_app import SceneMutationApi, SceneTriggerApp
from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)

# Disable VTK warning display
vtkObject.GlobalWarningDisplayOff()


@TrameApp()
class LocalApp(SceneTriggerApp):
    """
    LocalApp serves the scene triggers shared by every rendering mode, plus
    the local-only triggers for sub-geometry picking and client performance
    reporting, for client-side rendering via VTK-WASM in the browser.

    Attributes:
        server (Server): the Trame server instance
    Methods:
        pick_geometry: picks the geometry for rendering
        perf_report_wasm: reports the performance of the wasm update cycle
        perf_report_server_update: reports the performance of the server update cycle
        set_only_cookie: sets a cookie on the server (note: Trame server only allows a single cookie header)
    """
    def __init__(
            self,
            server: Server,
            get_scene_details_json: callable,
            standalone: bool = True,
            trame_logger: Logger | None = None,
            pick_geometry=None,
            scene_mutation_api: SceneMutationApi | None = None,
    ):
        # Callable for sub-geometry picking (optional), local-only.
        self._pick_geometry = pick_geometry
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

