"""
IRenderer
=========
Abstract protocol for the Visor rendering backend.

The scene coordinator programs against this interface. Swapping backends
(VTK/wasm local view -> future non-wasm) means providing a new implementation
without touching scene coordination.

Contract covers node lifecycle, per-part visual mutations,
camera, widget control (cross-section, bounding box, edges), widget fan-out
(scene bounds, actor count), picking, and render.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState

if TYPE_CHECKING:
    from vtkmodules.vtkCommonDataModel import vtkDataObject

    from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
    from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
    from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import RendererAnnotation
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode

logger = VisorDefaultLogger(__name__)


class IRenderer(ABC):
    """Abstract rendering backend consumed by the scene coordinator.

    Holds the camera record and the cross-section plane record, and owns the
    record half of the camera and plane contracts.  An implementation that has
    a pipeline camera or widget to project onto overrides the writers, calling
    ``super()`` first, and adds the projection.
    """

    _last_camera_state: "VisorCameraState | None"
    _last_cross_section_state: "VisorCrossSectionState | None"

    def __init__(self) -> None:
        """Initialize the camera and cross-section records to ``None``."""
        self._last_camera_state = None
        self._last_cross_section_state = None

    # ------------------------------------------------------------------------
    # Wire contract
    # ------------------------------------------------------------------------

    @abstractmethod
    def build_renderer_annotation(self) -> "RendererAnnotation | None":
        """Return this renderer's annotation for the current scene, or ``None``.

        The annotation carries every renderer-specific handle a client needs in
        order to bind to the scene description: per-node handles for registered
        part nodes, and handles for the renderer's singleton widgets.

        ``None`` for a renderer with no client-side handles -- absence is the
        wire representation, not a value.

        The return type is concrete per renderer and is discriminated on the wire
        by ``rendererKind``. It is never a free-form dict.

        Contract, load-bearing for the geometry picker: the per-node actor handle
        MUST be the value returned by the renderer's own object manager for the
        registered pipeline's actor -- the same call that produces the id the wasm
        picker reports at click time. It is never re-keyed or re-indexed.
        """

    # ------------------------------------------------------------------------
    # Node lifecycle
    # ------------------------------------------------------------------------

    @abstractmethod
    def register_node(
        self, node: "VisorSceneGraphPartNode", dataset: "vtkDataObject"
    ) -> None:
        """
        Build the VTK pipeline for *node* from *dataset* and register its actor.

        The renderer owns the resulting :class:`VtkNodePipeline` and is the
        sole caller of :meth:`VtkNodePipeline.from_dataset`. Must be
        idempotent: calling twice for the same node must not create a
        duplicate actor.
        """

    @abstractmethod
    def deregister_node(self, node_id: int) -> None:
        """
        Remove the actor for *node_id* and destroy its pipeline.

        Silently does nothing when *node_id* is not registered.
        """

    @abstractmethod
    def deregister_all(self) -> None:
        """Deregister every registered node and destroy every pipeline.

        Equivalent to calling :meth:`deregister_node` for every currently
        registered node id. Idempotent; safe on an empty registry.
        """

    # ------------------------------------------------------------------------
    # Per-part visual mutations
    # ------------------------------------------------------------------------

    @abstractmethod
    def apply_visibility(self, node_id: int, visible: bool) -> None:
        """Set actor visibility for *node_id*.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    @abstractmethod
    def apply_opacity(self, node_id: int, opacity: float) -> None:
        """Set actor opacity for *node_id*.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    @abstractmethod
    def apply_diffuse_color(
        self, node_id: int, r: float, g: float, b: float
    ) -> None:
        """Set the actor-property diffuse colour for *node_id*.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    @abstractmethod
    def apply_selected(
        self, node_id: int, selected: bool, diffuse_rgb: list
    ) -> None:
        """
        Apply or remove the selection highlight on *node_id*.

        *diffuse_rgb* is the part's stored diffuse colour, used when
        deselecting to restore the property DiffuseColor alongside resetting
        Ambient/Diffuse.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    @abstractmethod
    def apply_color_variable(
        self,
        node_id: int,
        array_type: "VisorVtkVariableType",
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> None:
        """
        Configure the mapper to colour *node_id* by the given scalar array
        and range.

        Parameters
        ----------
        node_id:
            Scene-graph node to update.
        array_type:
            The array's association, already parsed at the trigger boundary.
        array_name:
            VTK array name.
        component:
            Component index. ``-1`` means magnitude.
        min_val / max_val:
            Scalar display range.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    @abstractmethod
    def clear_color_variable(self, node_id: int) -> None:
        """Disable scalar colouring on *node_id*, reverting to solid diffuse.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    # ------------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------------

    @abstractmethod
    def reset_camera(self, bounds: list[float]) -> None:
        """Reset the camera to fit *bounds*, and write the result to the record.

        An implementation with no pipeline camera leaves the record at its
        previous value rather than clearing it, so that a reset cannot destroy
        a camera the frontend reported.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    def get_camera_state(self) -> "VisorCameraState | None":
        """Return the camera record, or ``None`` if nothing has written one yet."""
        return self._last_camera_state

    def sync_camera(self, camera_state: "VisorCameraState") -> None:
        """Store *camera_state* as the record, without copying.

        Callers rely on object identity through :meth:`get_camera_state`.
        An implementation with a pipeline camera overrides this, calls
        ``super()`` first, then projects the record onto the pipeline, so a
        raising VTK setter still leaves the record holding what was asked.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """
        self._last_camera_state = camera_state

    def set_projection(self, parallel: bool) -> None:
        """Write ``parallel_projection`` on the record in place; no record, no write.

        In place, preserving :meth:`sync_camera`'s identity contract.  A
        ``None`` record is not seeded: an implementation with a pipeline
        camera still applies the projection there, but the value is not
        recorded until the next :meth:`reset_camera` imports it.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """
        if self._last_camera_state is not None:
            self._last_camera_state.parallel_projection = parallel
        else:
            logger.debug("set_projection: no camera record; nothing to write.")

    # ------------------------------------------------------------------------
    # Widget control (cross-section, bounding box, edges)
    # ------------------------------------------------------------------------

    @abstractmethod
    def set_edges_visible(self, visible: bool) -> None:
        """Show or hide edges on every part in the scene.

        Scene-wide, not per-node: edges are a single global toggle.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """

    @abstractmethod
    def set_cross_section_visibility(self, visible: bool) -> None:
        """Show or hide the cross-section clipping plane."""

    def sync_cross_section_plane(
        self, origin: list[float], normal: list[float]
    ) -> None:
        """Store a copy of *origin* and *normal* as the plane record.

        An implementation with a widget overrides this, calls ``super()``
        first, then writes the widget's VTK objects.

        On return, the state this renderer serves to the client reflects the
        write, and the client is not notified.
        """
        self._last_cross_section_state = VisorCrossSectionState(
            origin=list(origin), normal=list(normal)
        )

    def get_cross_section_plane(self) -> "VisorCrossSectionState | None":
        """Return the plane record, or ``None`` if nothing has written one yet."""
        return self._last_cross_section_state


    @abstractmethod
    def set_bounding_box_visibility(self, visible: bool) -> None:
        """Show or hide the bounding-box outline."""

    # ------------------------------------------------------------------------
    # Widget fan-out (renderer primitives -- coordinator computes, renderer
    # dispatches to its owned widgets)
    # ------------------------------------------------------------------------

    @abstractmethod
    def update_bounds(self, bounds: list[float]) -> None:
        """
        Propagate scene bounds to bounds-consuming widgets
        (cross-section, bounding box).
        """

    @abstractmethod
    def update_actor_count(self, count: int) -> None:
        """Propagate the current part-node count to widgets."""

    # ------------------------------------------------------------------------
    # Picking
    # ------------------------------------------------------------------------

    @abstractmethod
    def pick_geometry(
        self,
        actor_wasm_id: int,
        cell_id: int,
        mode: str,
        world_pos: tuple[float, float, float],
    ) -> dict:
        """
        Resolve a client-initiated pick event to a sub-geometry payload.

        The renderer resolves the client-supplied opaque actor identifier to
        an internal actor; the coordinator never performs that resolution.

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

    # ------------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------------

    @abstractmethod
    def render(self) -> None:
        """Trigger a render and flush to the frontend."""


