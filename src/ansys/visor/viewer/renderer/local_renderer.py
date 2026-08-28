"""
VisorLocalRenderer
==================
:class:`IRenderer` implementation for the wasm / :class:`LocalView` backend.

Owns all VTK render-window / actor / widget / LocalView / object-manager
objects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from trame_server import Server
from trame_vtklocal.widgets.vtklocal import LocalView
from vtkmodules.vtkCommonDataModel import vtkDataObject
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import (
    vtkCellPicker,
    vtkPropPicker,
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
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
from ansys.visor.viewer.renderer.base import IRenderer
from ansys.visor.viewer.vtk.node_pipeline import VtkNodePipeline
from ansys.visor.viewer.vtk.widgets.visor_bounding_box import VisorBoundingBox
from ansys.visor.viewer.vtk.widgets.visor_cross_section import VisorCrossSectionWidget
from ansys.visor.viewer.vtk.widgets.visor_orientation import VisorOrientationWidget

if TYPE_CHECKING:
    from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode

logger = VisorDefaultLogger(__name__)


class VisorLocalRenderer(IRenderer):
    """IRenderer backend that owns the local wasm / LocalView VTK pipeline."""

    _server: Server
    _vtk_renderer: vtkRenderer
    _render_window: vtkRenderWindow
    _render_window_interactor: vtkRenderWindowInteractor
    _local_view: LocalView
    _object_manager: vtkObjectManager
    _orientation_widget: VisorOrientationWidget
    _cross_section_widget: VisorCrossSectionWidget
    _bounding_box_widget: VisorBoundingBox
    # Registered pipelines keyed by scene-graph node id.  Sole owner as of
    # Increment I5; mutated exclusively via register_node / deregister_node.
    _pipelines: dict[int, VtkNodePipeline]
    _last_camera_state: Optional["VisorCameraState"]

    def __init__(self, server: Server):
        """Build the full local-mode VTK infrastructure and seed wasm state."""
        self._server = server
        self._pipelines = {}
        self._last_camera_state = None

        self._vtk_renderer = self._initialize_vtk_renderer()
        self._render_window = self._initialize_render_window()
        self._render_window_interactor = self._initialize_render_window_interactor()
        self._local_view = self._initialize_local_view()
        self._object_manager = self._local_view.object_manager
        self._orientation_widget = self._initialize_orientation_widget()
        self._cross_section_widget = self._initialize_cross_section_widget()
        self._bounding_box_widget = self._initialize_bounding_box_widget()

        # Wasm state seeding -- moved verbatim from
        # ``VisorScene._initialize_vtk_pipeline`` so the client-visible
        # payload is byte-identical to main.
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

        Per-node handles are stamped from the same ``object_manager.GetId``
        call that :class:`SceneGraphStateBuilder` uses today to stamp
        ``SceneGraphNodeInfo.wasm_actor_id`` etc. (the R2 accommodation
        invariant) -- not a re-keyed or re-indexed id space.
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
    # IRenderer: node lifecycle
    # ------------------------------------------------------------------

    def register_node(
        self, node: "VisorSceneGraphPartNode", dataset: vtkDataObject
    ) -> None:
        """See :meth:`IRenderer.register_node`."""
        node_id = node.id
        if node_id in self._pipelines:
            return  # idempotent
        pipe = VtkNodePipeline.from_dataset(dataset)
        pipe.set_clipping_plane(self._cross_section_widget.plane)
        pipe.mapper.SetScalarVisibility(False)
        self._vtk_renderer.AddActor(pipe.actor)
        self._pipelines[node_id] = pipe

    def deregister_node(self, node_id: int) -> None:
        """See :meth:`IRenderer.deregister_node`."""
        pipe = self._pipelines.pop(node_id, None)
        if pipe is not None:
            self._vtk_renderer.RemoveActor(pipe.actor)

    def deregister_all(self) -> None:
        """See :meth:`IRenderer.deregister_all`."""
        for node_id in list(self._pipelines.keys()):
            self.deregister_node(node_id)

    # ------------------------------------------------------------------
    # IRenderer: per-part visual mutations
    # ------------------------------------------------------------------

    def apply_visibility(self, node_id: int, visible: bool) -> None:
        """See :meth:`IRenderer.apply_visibility`.

        Mutates the actor itself, not its property.  An unknown *node_id*
        is a logged no-op, never a raise.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_visibility: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.actor.SetVisibility(1 if visible else 0)

    def apply_opacity(self, node_id: int, opacity: float) -> None:
        """See :meth:`IRenderer.apply_opacity`.

        Mutates the actor's property.  An unknown *node_id* is a logged
        no-op, never a raise.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_opacity: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.actor.GetProperty().SetOpacity(opacity)

    def apply_diffuse_color(
        self, node_id: int, r: float, g: float, b: float
    ) -> None:
        """See :meth:`IRenderer.apply_diffuse_color`.

        Mutates the actor property's diffuse colour only.  An unknown
        *node_id* is a logged no-op, never a raise.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_diffuse_color: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.actor.GetProperty().SetDiffuseColor(r, g, b)

    def apply_edge_visibility(self, node_id: int, edge_visible: bool) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    def apply_selected(
        self, node_id: int, selected: bool, diffuse_rgb: list
    ) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    def apply_color_variable(
        self,
        node_id: int,
        spectrum_id: str,
        array_type: str,
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    def clear_color_variable(self, node_id: int) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    def refresh_color_variable_range(
        self,
        node_id: int,
        spectrum_id: str,
        array_type: str,
        array_name: str,
        component: int,
    ) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    # ------------------------------------------------------------------
    # IRenderer: camera
    # ------------------------------------------------------------------

    def reset_camera(self, bounds: list[float]) -> None:
        """See :meth:`IRenderer.reset_camera`."""
        self._vtk_renderer.ResetCamera(bounds)

    def get_camera_state(self) -> Optional["VisorCameraState"]:
        """See :meth:`IRenderer.get_camera_state`.

        Returns ``None`` on this branch: no coordinator caller and no
        frontend round-trip populates the store.  Phase 3 wires the sync.
        """
        return self._last_camera_state

    def sync_camera(self, camera_state: "VisorCameraState") -> None:
        """See :meth:`IRenderer.sync_camera`.

        Stores the state for :meth:`get_camera_state` to return.  No
        coordinator caller on this branch; Phase 3 wires the round-trip.
        """
        self._last_camera_state = camera_state

    # ------------------------------------------------------------------
    # IRenderer: widget control (cross-section, bounding box)
    #
    # No coordinator caller on this branch. Phase 3 populates.
    # ------------------------------------------------------------------

    def set_cross_section_visibility(self, visible: bool) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    def sync_cross_section_plane(
        self, origin: list[float], normal: list[float]
    ) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    def set_bounding_box_visibility(self, visible: bool) -> None:
        """No-op in Story 1.2. Phase 3 populates."""

    # ------------------------------------------------------------------
    # IRenderer: widget fan-out (called by coordinator today)
    # ------------------------------------------------------------------

    def update_bounds(self, bounds: list[float]) -> None:
        """See :meth:`IRenderer.update_bounds`."""
        self._cross_section_widget.update_bounds(bounds)
        self._bounding_box_widget.update_bounds(bounds)

    def update_actor_count(self, count: int) -> None:
        """See :meth:`IRenderer.update_actor_count`."""
        self._bounding_box_widget.update_node_count(count)

    # ------------------------------------------------------------------
    # IRenderer: picking
    # ------------------------------------------------------------------

    def pick_geometry(
        self,
        actor_wasm_id: int,
        cell_id: int,
        mode: str,
        world_pos: tuple[float, float, float],
    ) -> dict:
        """See :meth:`IRenderer.pick_geometry`.

        Body moved verbatim from ``VisorScene.pick_geometry``; only the
        world-position packing changes (tuple in, three scalars out).
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
    # IRenderer: render / flush
    # ------------------------------------------------------------------

    def render(self) -> None:
        """See :meth:`IRenderer.render`."""
        timer = PerfTimer("render", logger)
        with timer.phase("RenderWindow.Render"):
            self._render_window.Render()
        with timer.phase("LocalView.update"):
            self._local_view.update()
        timer.log()

    def render_window_only(self) -> None:
        """See :meth:`IRenderer.render_window_only`."""
        self._render_window.Render()

    def flush_wasm_state(self) -> None:
        """See :meth:`IRenderer.flush_wasm_state`.

        Local (wasm) backend override: pushes current Python VTK object
        state to the wasm client via ``LocalView.update()``.
        """
        self._local_view.update()

    # ------------------------------------------------------------------
    # IRenderer: frontend addressing
    # ------------------------------------------------------------------

    @property
    def frontend_ref_name(self) -> str:
        """See :meth:`IRenderer.frontend_ref_name`."""
        return self._local_view.ref_name

    # ------------------------------------------------------------------
    # Internal init helpers (moved verbatim from VisorScene)
    # ------------------------------------------------------------------

    def _initialize_vtk_renderer(self) -> vtkRenderer:
        renderer = vtkRenderer()
        renderer.SetBackground(VisorColors.BackgroundColor)
        return renderer

    def _initialize_render_window(self) -> vtkRenderWindow:
        render_window = vtkRenderWindow()
        render_window.AddRenderer(self._vtk_renderer)
        render_window.ShowWindowOff()
        render_window.SetMultiSamples(0)
        render_window.SetEnableTranslucentSurface(True)
        return render_window

    def _initialize_render_window_interactor(self) -> vtkRenderWindowInteractor:
        interactor = vtkRenderWindowInteractor()
        interactor.SetRenderWindow(self._render_window)
        interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        # vtkCellPicker so GetCellId() is available on the WASM side.
        cell_picker = vtkCellPicker()
        cell_picker.SetTolerance(0.005)
        interactor.SetPicker(cell_picker)
        return interactor

    def _initialize_local_view(self) -> LocalView:
        return LocalView(
            self._render_window,
            trame_server=self._server,
            throttle_rate=4,
            eager_sync=True,
            listeners=("wasm_listeners", {}),
        )

    def _initialize_orientation_widget(self) -> VisorOrientationWidget:
        widget = VisorOrientationWidget(self._vtk_renderer, self._render_window_interactor)
        widget.register_with_local_view(self._local_view)
        return widget

    def _initialize_cross_section_widget(self) -> VisorCrossSectionWidget:
        widget = VisorCrossSectionWidget(self._render_window_interactor)
        widget.register_with_local_view(self._local_view)
        return widget

    def _initialize_bounding_box_widget(self) -> VisorBoundingBox:
        widget = VisorBoundingBox(self._vtk_renderer.GetActiveCamera())
        widget.attach_to_renderer(self._vtk_renderer)
        widget.register_with_local_view(self._local_view)
        return widget

