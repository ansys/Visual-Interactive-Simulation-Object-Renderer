"""
VtkPipelineRenderer
===================
Abstract :class:`IRenderer` that owns a server-side VTK pipeline.

Builds the VTK renderer, render window, interactor and the three widgets, owns
one :class:`VtkNodePipeline` per registered part node, and writes part, camera
and widget state through them.  How a written object becomes visible to the
client is left to the subclass, through the four ``_publish_*`` hooks.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from vtkmodules.vtkCommonCore import vtkObject
from vtkmodules.vtkCommonDataModel import vtkDataObject
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import (
    vtkCellPicker,
    vtkRenderer,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
)

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.renderer.base import IRenderer
from ansys.visor.viewer.vtk.node_pipeline import VtkNodePipeline
from ansys.visor.viewer.vtk.widgets.visor_bounding_box import VisorBoundingBox
from ansys.visor.viewer.vtk.widgets.visor_cross_section import VisorCrossSectionWidget
from ansys.visor.viewer.vtk.widgets.visor_orientation import VisorOrientationWidget

if TYPE_CHECKING:
    from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode

logger = VisorDefaultLogger(__name__)

PART_PICK_TOLERANCE: float = 0.005
"""Cell-picker tolerance, as a fraction of the render-window diagonal."""


class VtkPipelineRenderer(IRenderer):
    """Owns the VTK renderer, window, interactor, widgets and per-node pipelines, and writes part, camera and widget state through them."""

    _vtk_renderer: vtkRenderer
    _render_window: vtkRenderWindow
    _render_window_interactor: vtkRenderWindowInteractor
    _orientation_widget: VisorOrientationWidget
    _cross_section_widget: VisorCrossSectionWidget
    _bounding_box_widget: VisorBoundingBox
    # Registered pipelines keyed by scene-graph node id.  Sole owner;
    # mutated exclusively via register_node / deregister_node.
    _pipelines: dict[int, VtkNodePipeline]

    def __init__(self) -> None:
        """Build renderer, window, interactor, the widgets' host, then the three widgets, in that order."""
        super().__init__()
        self._pipelines = {}

        self._vtk_renderer = self._initialize_vtk_renderer()
        self._render_window = self._initialize_render_window()
        self._render_window_interactor = self._initialize_render_window_interactor()
        self._prepare_widgets()
        self._orientation_widget = self._initialize_orientation_widget()
        self._cross_section_widget = self._initialize_cross_section_widget()
        self._bounding_box_widget = self._initialize_bounding_box_widget()

    # ------------------------------------------------------------------
    # Backend hooks
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def background_rgb(self) -> tuple[float, float, float]:
        """The colour the window clears to."""

    @abstractmethod
    def _initialize_render_window(self) -> vtkRenderWindow:
        """Return this backend's window with the renderer added."""

    @abstractmethod
    def _prepare_widgets(self) -> None:
        """Set up what the widgets need from this backend before they are built."""

    @abstractmethod
    def _publish_object(self, vtk_object: vtkObject) -> None:
        """Make one written VTK object visible to the client."""

    @abstractmethod
    def _publish_part_mapper(self, node_id: int) -> None:
        """Make one part's written mapper visible to the client."""

    @abstractmethod
    def _publish_camera(self) -> None:
        """Make the written pipeline camera visible to the client."""

    @abstractmethod
    def _publish_cross_section(self) -> None:
        """Make the written cross-section plane visible to the client."""

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

        Resolves the pipeline and delegates to
        :meth:`VtkNodePipeline.set_visibility`.  An unknown *node_id* is a
        logged no-op, never a raise.

        Ends with :meth:`_publish_object` on the actor, after the
        write, so the state served to the client carries the new visibility.
        Does not notify the client.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_visibility: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.set_visibility(visible)
        self._publish_object(pipe.actor)

    def apply_opacity(self, node_id: int, opacity: float) -> None:
        """See :meth:`IRenderer.apply_opacity`.

        Resolves the pipeline and delegates to
        :meth:`VtkNodePipeline.set_opacity`.  An unknown *node_id* is a
        logged no-op, never a raise.

        Ends with :meth:`_publish_object` on the actor's property,
        after the write, so the state served to the client carries the new
        opacity.  Does not notify the client.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_opacity: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.set_opacity(opacity)
        self._publish_object(pipe.actor.GetProperty())

    def apply_diffuse_color(
        self, node_id: int, r: float, g: float, b: float
    ) -> None:
        """See :meth:`IRenderer.apply_diffuse_color`.

        Resolves the pipeline and delegates to
        :meth:`VtkNodePipeline.set_diffuse_color`.  An unknown *node_id*
        is a logged no-op, never a raise.

        Ends with :meth:`_publish_object` on the actor's property,
        after the write, so the state served to the client carries the new
        colour.  Does not notify the client.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_diffuse_color: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.set_diffuse_color(r, g, b)
        self._publish_object(pipe.actor.GetProperty())

    def apply_selected(
        self, node_id: int, selected: bool, diffuse_rgb: list
    ) -> None:
        """See :meth:`IRenderer.apply_selected`.

        Resolves the pipeline and delegates to
        :meth:`VtkNodePipeline.set_selected`.  *diffuse_rgb* is passed
        through as given; supplying a default when the part has no stored
        colour is the coordinator's job, not the renderer's.  An unknown
        *node_id* is a logged no-op, never a raise.

        Ends with :meth:`_publish_object` on the actor's property,
        after the write, so the state served to the client carries the new
        lighting terms and colour.  Does not notify the client.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_selected: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.set_selected(selected, diffuse_rgb)
        self._publish_object(pipe.actor.GetProperty())

    def apply_color_variable(
        self,
        node_id: int,
        array_type: "VisorVtkVariableType",
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> None:
        """See :meth:`IRenderer.apply_color_variable`.

        Resolves the pipeline and delegates to
        :meth:`VtkNodePipeline.set_color_variable`.  *array_type* must
        already be a :class:`VisorVtkVariableType`; it is parsed at the
        trigger boundary, never here, and the pipeline compares it by
        identity, so any other value is a logged no-op there.  An unknown
        *node_id* is a logged no-op, never a raise.

        Ends with :meth:`_publish_part_mapper`, after the mapper write, so
        the state served to the client carries the new range.  Does not
        notify the client.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "apply_color_variable: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.set_color_variable(array_type, array_name, component, min_val, max_val)
        self._publish_part_mapper(node_id)

    def clear_color_variable(self, node_id: int) -> None:
        """See :meth:`IRenderer.clear_color_variable`.

        Resolves the pipeline and delegates to
        :meth:`VtkNodePipeline.clear_color_variable`.  An unknown
        *node_id* is a logged no-op, never a raise.

        Ends with :meth:`_publish_part_mapper`, after the mapper write, so
        the state served to the client has scalar colouring off.  Does not
        notify the client.
        """
        pipe = self._pipelines.get(node_id)
        if pipe is None:
            logger.debug(
                "clear_color_variable: no pipeline for node %s; skipping.", node_id
            )
            return
        pipe.clear_color_variable()
        self._publish_part_mapper(node_id)

    # ------------------------------------------------------------------
    # IRenderer: camera
    # ------------------------------------------------------------------

    def reset_camera(self, bounds: list[float]) -> None:
        """See :meth:`IRenderer.reset_camera`.

        Ends with :meth:`_publish_camera`, after the reset, so the
        state served to the client carries the reset camera.  Does not
        notify the client.
        """
        self._vtk_renderer.ResetCamera(bounds)
        self._last_camera_state = self._read_pipeline_camera()
        self._publish_camera()

    def sync_camera(self, camera_state: "VisorCameraState") -> None:
        """See :meth:`IRenderer.sync_camera`; then project onto the pipeline camera.

        Records through ``super()`` before projecting, so a raising VTK setter
        still leaves the record holding what the caller asked for.  Ends with
        :meth:`_publish_camera`, after the projection.  Does not
        notify the client.
        """
        super().sync_camera(camera_state)
        self._apply_to_pipeline_camera(camera_state)
        self._publish_camera()

    def set_projection(self, parallel: bool) -> None:
        """See :meth:`IRenderer.set_projection`; then apply it to the pipeline camera.

        Record first, through ``super()``, pipeline second, for the reason
        :meth:`sync_camera` gives.  The pipeline write is unconditional, with
        or without a record.  Ends with :meth:`_publish_camera`, after
        the pipeline write.  Does not notify the client.
        """
        super().set_projection(parallel)
        self._vtk_renderer.GetActiveCamera().SetParallelProjection(parallel)
        self._publish_camera()

    # ------------------------------------------------------------------
    # Pipeline camera helpers
    #
    # Neither takes a lock.  The caller-holds convention applies exactly as
    # it does to every other IRenderer method: the scene coordinator holds
    # ``VisorSceneBase._vtk_lock`` across every path that reaches these.
    # ------------------------------------------------------------------

    def _read_pipeline_camera(self) -> VisorCameraState:
        """Read the active pipeline camera into a fresh camera state.

        ``GetParallelProjection`` returns an ``int``; the explicit ``bool()``
        keeps the field's type off pydantic's non-strict coercion.
        """
        camera = self._vtk_renderer.GetActiveCamera()
        return VisorCameraState(
            position=list(camera.GetPosition()),
            focal_point=list(camera.GetFocalPoint()),
            view_up=list(camera.GetViewUp()),
            clipping_range=list(camera.GetClippingRange()),
            parallel_projection=bool(camera.GetParallelProjection()),
            view_angle=camera.GetViewAngle(),
            parallel_scale=camera.GetParallelScale(),
        )

    def _apply_to_pipeline_camera(self, camera_state: "VisorCameraState") -> None:
        """Write *camera_state*'s onto the active pipeline camera."""
        camera = self._vtk_renderer.GetActiveCamera()
        camera.SetPosition(camera_state.position)
        camera.SetFocalPoint(camera_state.focal_point)
        camera.SetViewUp(camera_state.view_up)
        camera.SetClippingRange(camera_state.clipping_range)
        camera.SetParallelProjection(camera_state.parallel_projection)
        camera.SetViewAngle(camera_state.view_angle)
        camera.SetParallelScale(camera_state.parallel_scale)

    # ------------------------------------------------------------------
    # IRenderer: widget control (edges, cross-section plane)
    # ------------------------------------------------------------------

    def set_edges_visible(self, visible: bool) -> None:
        """See :meth:`IRenderer.set_edges_visible`.

        Fans out over every registered pipeline.  Scene-wide, so there is no
        node id to resolve and no logged-no-op branch: a scene with no
        pipelines is a no-op by iteration, not by guard.

        Each pipeline's property is re-serialized with
        :meth:`_publish_object` right after its own write, so the state
        served to the client carries the new edge flag on every part.  Does
        not notify the client.
        """
        for pipe in self._pipelines.values():
            pipe.set_edge_visibility(visible)
            self._publish_object(pipe.actor.GetProperty())

    def sync_cross_section_plane(
        self, origin: list[float], normal: list[float]
    ) -> None:
        """See :meth:`IRenderer.sync_cross_section_plane`; then write both VTK objects.

        Records through ``super()``, then writes both VTK objects.  ``set_origin`` and
        ``set_normal`` each write the plane *and* the representation, so the
        clip function and the draggable handle cannot diverge on this path --
        which is the defect the client's own set/get asymmetry has.

        Ends with :meth:`_publish_cross_section`, after both writes,
        so the state served to the client carries the new plane.  Does not
        notify the client.
        """
        super().sync_cross_section_plane(origin, normal)
        self._cross_section_widget.set_origin(origin)
        self._cross_section_widget.set_normal(normal)
        self._publish_cross_section()

    # ------------------------------------------------------------------
    # IRenderer: widget fan-out
    # ------------------------------------------------------------------

    def update_bounds(self, bounds: list[float]) -> None:
        """See :meth:`IRenderer.update_bounds`.

        Seeds the cross-section record from the values the widget's own
        ``update_bounds`` just wrote through ``set_origin``/``set_normal``, so
        the record is never ``None`` once a scene has been populated and
        ``get_state`` can assign it unconditionally, as it does the camera's.

        **The seed runs only when there is no record.**  This method is not
        reached once per scene: ``set_part_visibility`` fans out to
        ``_update_widget_bounds``, so a part toggle or a dataset add reaches
        here too.  Seeding unconditionally would therefore discard a plane the
        user had dragged, on the next toggle, and the widget's own
        ``update_bounds`` would already have overwritten both VTK objects with
        the default plane.  With a record present this writes the record
        *back* to the widget instead -- after the widget's own call, never
        before -- and leaves the record itself untouched.

        Ordering is load-bearing in both branches.  Seeded before the widget
        call, the record holds the previous plane and is one populate behind;
        written back before it, the widget's defaults win and the drag is
        lost.  Either compiles, and either passes any test that does not
        assert the order.
        """
        self._cross_section_widget.update_bounds(bounds)
        self._bounding_box_widget.update_bounds(bounds)
        if self._last_cross_section_state is None:
            plane = self._cross_section_widget.plane
            self._last_cross_section_state = VisorCrossSectionState(
                origin=list(plane.GetOrigin()),
                normal=list(plane.GetNormal()),
            )
        else:
            self._cross_section_widget.set_origin(self._last_cross_section_state.origin)
            self._cross_section_widget.set_normal(self._last_cross_section_state.normal)

    def update_actor_count(self, count: int) -> None:
        """See :meth:`IRenderer.update_actor_count`."""
        self._bounding_box_widget.update_node_count(count)

    # ------------------------------------------------------------------
    # Part picking
    # ------------------------------------------------------------------

    def pick_part_at(self, x: int, y: int) -> int | None:
        """Return the node id of the part under a render-window pixel, origin bottom-left, or None.

        *x* and *y* are render-window device pixels.  Only part actors are
        pickable: the pick list holds every registered pipeline's actor and
        nothing else, so the bounding-box outline and the widgets never hide a
        part behind them.  A software ray cast; it does not render.  Takes no
        lock: the caller holds the scene lock, as for every other method.
        """
        picker = vtkCellPicker()
        picker.SetTolerance(PART_PICK_TOLERANCE)
        picker.InitializePickList()
        for pipe in self._pipelines.values():
            picker.AddPickList(pipe.actor)
        picker.PickFromListOn()
        if not picker.Pick(x, y, 0, self._vtk_renderer):
            return None
        picked_actor = picker.GetActor()
        for node_id, pipe in self._pipelines.items():
            if pipe.actor is picked_actor:
                return node_id
        return None

    # ------------------------------------------------------------------
    # Internal init helpers
    # ------------------------------------------------------------------

    def _initialize_vtk_renderer(self) -> vtkRenderer:
        renderer = vtkRenderer()
        renderer.SetBackground(self.background_rgb)
        return renderer

    def _initialize_render_window_interactor(self) -> vtkRenderWindowInteractor:
        interactor = vtkRenderWindowInteractor()
        interactor.SetRenderWindow(self._render_window)
        interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        # vtkCellPicker so GetCellId() is available on the WASM side.
        cell_picker = vtkCellPicker()
        cell_picker.SetTolerance(PART_PICK_TOLERANCE)
        interactor.SetPicker(cell_picker)
        return interactor

    def _initialize_orientation_widget(self) -> VisorOrientationWidget:
        return VisorOrientationWidget(self._vtk_renderer, self._render_window_interactor)

    def _initialize_cross_section_widget(self) -> VisorCrossSectionWidget:
        return VisorCrossSectionWidget(self._render_window_interactor)

    def _initialize_bounding_box_widget(self) -> VisorBoundingBox:
        widget = VisorBoundingBox(self._vtk_renderer.GetActiveCamera())
        widget.attach_to_renderer(self._vtk_renderer)
        return widget

