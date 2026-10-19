"""
VisorLocalRenderer
==================
:class:`VtkPipelineRenderer` implementation for the wasm / :class:`LocalView`
backend.

Owns the LocalView and its object manager, and publishes each written VTK
object by re-serializing it into the state the wasm client fetches.
"""

from __future__ import annotations

from trame_server import Server
from trame_vtklocal.widgets.vtklocal import LocalView
from vtkmodules.vtkCommonCore import vtkObject
from vtkmodules.vtkRenderingCore import (
    vtkPropPicker,
    vtkRenderWindow,
)
from vtkmodules.vtkSerializationManager import vtkObjectManager

from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.perf_timer import PerfTimer
from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import (
    WasmNodeHandles,
    WasmRendererAnnotation,
    WasmWidgetHandles,
)
from ansys.visor.viewer.renderer.pipeline_renderer import VtkPipelineRenderer
from ansys.visor.viewer.vtk.widgets.visor_bounding_box import VisorBoundingBox
from ansys.visor.viewer.vtk.widgets.visor_cross_section import VisorCrossSectionWidget
from ansys.visor.viewer.vtk.widgets.visor_orientation import VisorOrientationWidget

logger = VisorDefaultLogger(__name__)


class VisorLocalRenderer(VtkPipelineRenderer):
    """IRenderer backend that owns the local wasm / LocalView VTK pipeline."""

    _server: Server
    _local_view: LocalView
    _object_manager: vtkObjectManager

    def __init__(self, server: Server):
        """Build the full local-mode VTK infrastructure and seed wasm state."""
        self._server = server
        super().__init__()

        # Wasm state seeding: the ids and names the client reads to bind to
        # this render window, renderer, interactor and picker.
        self._server.state["wasm_ids"] = {
            "renderWindowId": self._local_view.get_wasm_id(self._render_window),
            "rendererId": self._local_view.get_wasm_id(self._vtk_renderer),
            "interactorId": self._local_view.register_vtk_object(self._render_window_interactor),
            "pickerId": self._local_view.register_vtk_object(vtkPropPicker()),
        }
        self._server.state["wasm_ref_name"] = self._local_view.ref_name
        self._server.state["perf_logging"] = settings.perf_logging


    # ------------------------------------------------------------------
    # IRenderer: wire contract
    # ------------------------------------------------------------------

    def build_renderer_annotation(self) -> WasmRendererAnnotation:
        """See :meth:`IRenderer.build_renderer_annotation`.

        Per-node handles are stamped with ``object_manager.GetId`` on the
        registered pipeline's own objects -- not a re-keyed or re-indexed id
        space.
        """
        get_id = self._object_manager.GetId
        nodes = {
            str(node_id): WasmNodeHandles(
                actor_id=get_id(pipe.actor),
                property_id=get_id(pipe.actor.GetProperty()),
                mapper_id=get_id(pipe.mapper),
            )
            for node_id, pipe in self._pipelines.items()
        }
        widgets = WasmWidgetHandles(
            orientation_widget_id=self._orientation_widget.widget_wasm_id,
            cross_section_plane_id=self._cross_section_widget.plane_wasm_id,
            cross_section_plane_widget_id=self._cross_section_widget.plane_widget_wasm_id,
            cross_section_plane_representation_id=(
                self._cross_section_widget.plane_representation_wasm_id
            ),
            bounding_box_algorithm_id=self._bounding_box_widget.box_algorithm_wasm_id,
            bounding_box_outline_actor_id=self._bounding_box_widget.outline_wasm_actor_id,
            bounding_box_axes_actor_id=self._bounding_box_widget.axes_wasm_actor_id,
        )
        return WasmRendererAnnotation(nodes=nodes, widgets=widgets)

    # ------------------------------------------------------------------
    # VtkPipelineRenderer: publish hooks
    # ------------------------------------------------------------------

    def _publish_part_mapper(self, node_id: int) -> None:
        """Make the state served to the client current for one part's mapper.

        A mapper write without this leaves the served cache holding the old
        content under a new version number, so the next client fetch gets the
        pre-write range.  **Serialize only; do not notify.**  An unknown
        *node_id* is a logged no-op.

        Names the mapper's id alone, derived with ``GetId`` on the object as
        :meth:`_publish_camera` derives the camera's; the id lookup
        and the unregistered-object skip are :meth:`_publish_object`'s.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "_publish_part_mapper: no pipeline for node %s; skipping.", node_id
            )
            return
        self._publish_object(pipe.mapper)

    def _publish_object(self, vtk_object: vtkObject) -> None:
        """Re-serialize one VTK object into the state served to the client.

        ``vtklocal`` advertises each object's modification time off the live
        object but serves its content from a serialization cache, so a write
        without this publishes a new version number against the old content.
        **Serialize only; do not notify.**

        An id of ``0`` is one the store has never held (the ROOT sentinel);
        naming it degrades to an error-logged no-op in VTK, so it is skipped
        here with a debug line and the next full serialization carries the
        object.
        """
        object_id = self._object_manager.GetId(vtk_object)
        if object_id == 0:
            logger.debug(
                "_publish_object: %s is not registered yet; skipping.",
                vtk_object.GetClassName(),
            )
            return
        self._object_manager.UpdateStateFromObject(object_id)

    def _publish_camera(self) -> None:
        """Make the state served to the client current for the camera.

        ``vtklocal`` advertises each object's modification time off the live
        VTK object but serves state out of a serialization cache, so a write
        to the pipeline camera without this call publishes a new
        version number against the old content: the client fetches the
        pre-write camera and applies it over the one just installed.

        ``UpdateStateFromObject`` re-serializes the single already-registered
        id it is given and commits its dependency edges again; a mid-tree node
        re-serialized on its own stays reachable from its parent, so naming
        one id is safe.  It is narrower than ``UpdateStatesFromObjects``,
        which serializes from the roots it is given and registers objects the
        store has not seen: an id the store has never held answers ``GetId``
        ``0``, the ROOT sentinel, and the call degrades to an error-logged
        no-op.

        No ``js_call``: that lives in ``LocalView.update``, so this
        serialises without re-opening the rebuild race
        ``_push_runtime_state`` refuses.
        """
        self._object_manager.UpdateStateFromObject(
            self._object_manager.GetId(self._vtk_renderer.GetActiveCamera())
        )

    def _publish_cross_section(self) -> None:
        """Make the state served to the client current for the plane.

        Two ids, named one at a time, each derived the way
        :meth:`_publish_camera` derives the camera's: ``GetId`` on the
        object itself, not the id ``register_vtk_object`` returned.  Deriving
        it this way means the equivalence of those two id spaces never has to
        be established.

        The plane is the clip function every pipeline holds; the
        representation is the visible handle and is also what the client
        reads on save.  A plane-only re-serialise leaves the client saving a
        stale handle.

        The widget id is deliberately not named: ``set_origin`` and
        ``set_normal`` do not write the widget, whose changing state is
        enablement.
        """
        self._object_manager.UpdateStateFromObject(
            self._object_manager.GetId(self._cross_section_widget.plane)
        )
        self._object_manager.UpdateStateFromObject(
            self._object_manager.GetId(self._cross_section_widget.plane_representation)
        )

    # ------------------------------------------------------------------
    # IRenderer: widget visibility
    #
    # ``set_cross_section_visibility`` and ``set_bounding_box_visibility``
    # stay no-ops: those widgets are driven client-side via the wasm mirror,
    # and nothing in LOCAL reads their enablement.
    # ------------------------------------------------------------------

    def set_cross_section_visibility(self, visible: bool) -> None:
        """No-op: the widget's enablement is driven client-side."""

    def set_bounding_box_visibility(self, visible: bool) -> None:
        """No-op: the widget's enablement is driven client-side."""

    # ------------------------------------------------------------------
    # Local-only: picking
    # ------------------------------------------------------------------

    def pick_geometry(
        self,
        actor_wasm_id: int,
        cell_id: int,
        mode: str,
        world_pos: tuple[float, float, float],
    ) -> dict:
        """
        Resolve a client-initiated pick event to a sub-geometry payload.

        The actor is found by matching each renderer actor's object-manager
        id against *actor_wasm_id*; the coordinator never performs that
        resolution.

        Parameters
        ----------
        actor_wasm_id:
            Client-supplied opaque actor identifier from the wasm-side picker.
        cell_id:
            Cell index within the picked actor's mapper dataset.
        mode:
            ``"vertex" | "edge" | "face"``.
        world_pos:
            World-space pick position from the client picker, used to select
            the nearest vertex/edge for multi-vertex/edge cells.

        Returns
        -------
        dict
            Backend-neutral pick result. Always contains ``"found": bool``.
            When ``found`` is ``True``, contains ``"mode"`` and mode-specific
            fields (``position`` / ``pointA``+``pointB``+``length`` /
            ``points``+``area``).
        """
        import math

        actor_wasm_id = int(actor_wasm_id)
        cell_id = int(cell_id)
        pick_pos = [float(world_pos[0]), float(world_pos[1]), float(world_pos[2])]

        if actor_wasm_id < 0 or cell_id < 0:
            return {"found": False}

        # Locate the actor by iterating the renderer's actors and matching
        # WASM IDs (avoids depending on a GetObjectAtId reverse-lookup API).
        actor = None
        actors = self._vtk_renderer.GetActors()
        actors.InitTraversal()
        a = actors.GetNextActor()
        while a is not None:
            if self._object_manager.GetId(a) == actor_wasm_id:
                actor = a
                break
            a = actors.GetNextActor()

        if actor is None:
            return {"found": False}

        dataset = actor.GetMapper().GetInputDataObject(0, 0)
        if dataset is None or cell_id >= dataset.GetNumberOfCells():
            return {"found": False}

        cell = dataset.GetCell(cell_id)
        if cell is None:
            return {"found": False}

        n_pts = cell.GetNumberOfPoints()
        pts = cell.GetPoints()

        if mode == "vertex":
            best_i = 0
            min_dist2 = float("inf")
            for i in range(n_pts):
                p = pts.GetPoint(i)
                d2 = sum((pick_pos[k] - p[k]) ** 2 for k in range(3))
                if d2 < min_dist2:
                    min_dist2 = d2
                    best_i = i
            position = list(pts.GetPoint(best_i))
            return {"found": True, "mode": "vertex", "position": position}

        if mode == "edge":
            if n_pts < 2:
                return {"found": False}
            best_i, best_j = 0, 1
            min_dist2 = float("inf")
            for i in range(n_pts):
                j = (i + 1) % n_pts
                p0 = pts.GetPoint(i)
                p1 = pts.GetPoint(j)
                seg = [p1[k] - p0[k] for k in range(3)]
                seg_len2 = sum(s * s for s in seg)
                if seg_len2 > 0:
                    t = sum((pick_pos[k] - p0[k]) * seg[k] for k in range(3)) / seg_len2
                    t = max(0.0, min(1.0, t))
                else:
                    t = 0.0
                closest = [p0[k] + t * seg[k] for k in range(3)]
                d2 = sum((pick_pos[k] - closest[k]) ** 2 for k in range(3))
                if d2 < min_dist2:
                    min_dist2 = d2
                    best_i, best_j = i, j
            pt_a = list(pts.GetPoint(best_i))
            pt_b = list(pts.GetPoint(best_j))
            length = math.sqrt(sum((a - b) ** 2 for a, b in zip(pt_a, pt_b)))
            return {
                "found": True,
                "mode": "edge",
                "pointA": pt_a,
                "pointB": pt_b,
                "length": length,
            }

        if mode == "face":
            p0 = pts.GetPoint(0)
            cx, cy, cz = 0.0, 0.0, 0.0
            for i in range(1, n_pts - 1):
                a = pts.GetPoint(i)
                b = pts.GetPoint(i + 1)
                ax, ay, az = a[0] - p0[0], a[1] - p0[1], a[2] - p0[2]
                bx, by, bz = b[0] - p0[0], b[1] - p0[1], b[2] - p0[2]
                cx += ay * bz - az * by
                cy += az * bx - ax * bz
                cz += ax * by - ay * bx
            area = 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
            points = [list(pts.GetPoint(i)) for i in range(n_pts)]
            return {"found": True, "mode": "face", "area": area, "points": points}

        return {"found": False}

    # ------------------------------------------------------------------
    # IRenderer: render
    # ------------------------------------------------------------------

    def render(self) -> None:
        """See :meth:`IRenderer.render`."""
        timer = PerfTimer("render", logger)
        with timer.phase("RenderWindow.Render"):
            self._render_window.Render()
        with timer.phase("LocalView.update"):
            self._local_view.update()
        timer.log()

    # ------------------------------------------------------------------
    # Local-only: window render, wasm flush, frontend addressing
    # ------------------------------------------------------------------

    def render_window_only(self) -> None:
        """Render the VTK window without flushing to the frontend."""
        self._render_window.Render()

    def flush_wasm_state(self) -> None:
        """Push current VTK object state to the wasm client via ``LocalView.update()`` without re-rendering."""
        self._local_view.update()

    @property
    def frontend_ref_name(self) -> str:
        """Name by which the LocalView is addressed in ``server.js_call``."""
        return self._local_view.ref_name

    # ------------------------------------------------------------------
    # VtkPipelineRenderer: backend hooks and init helpers
    # ------------------------------------------------------------------

    @property
    def background_rgb(self) -> tuple[float, float, float]:
        """The colour the window clears to."""
        return VisorColors.BackgroundColor

    def _prepare_widgets(self) -> None:
        """Build the LocalView the widgets register with, and take its object manager."""
        self._local_view = self._initialize_local_view()
        self._object_manager = self._local_view.object_manager

    def _initialize_render_window(self) -> vtkRenderWindow:
        render_window = vtkRenderWindow()
        render_window.AddRenderer(self._vtk_renderer)
        render_window.ShowWindowOff()
        render_window.SetMultiSamples(0)
        render_window.SetEnableTranslucentSurface(True)
        return render_window

    def _initialize_local_view(self) -> LocalView:
        return LocalView(
            self._render_window,
            trame_server=self._server,
            throttle_rate=4,
            eager_sync=True,
            listeners=("wasm_listeners", {}),
        )

    def _initialize_orientation_widget(self) -> VisorOrientationWidget:
        widget = super()._initialize_orientation_widget()
        widget.register_with_local_view(self._local_view)
        return widget

    def _initialize_cross_section_widget(self) -> VisorCrossSectionWidget:
        widget = super()._initialize_cross_section_widget()
        widget.register_with_local_view(self._local_view)
        return widget

    def _initialize_bounding_box_widget(self) -> VisorBoundingBox:
        widget = super()._initialize_bounding_box_widget()
        widget.register_with_local_view(self._local_view)
        return widget

