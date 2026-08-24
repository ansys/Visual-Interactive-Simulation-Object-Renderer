"""
IRenderer
=========
Abstract protocol for the Visor rendering backend.

The scene coordinator programs against this interface. Swapping backends
(VTK/wasm local view -> future non-wasm) means providing a new implementation
without touching scene coordination.

Contract covers node lifecycle, per-part visual mutations,
camera, widget control (cross-section, bounding box), widget fan-out (scene
bounds, actor count), picking, and render/flush. Not covered yet:
state-authority hooks, trigger-facing methods, round-trip additions.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vtkmodules.vtkCommonDataModel import vtkDataObject

    from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
    from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import RendererAnnotation
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode


class IRenderer(ABC):
    """Abstract rendering backend consumed by the scene coordinator."""

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
        """Set actor visibility for *node_id*."""

    @abstractmethod
    def apply_opacity(self, node_id: int, opacity: float) -> None:
        """Set actor opacity for *node_id*."""

    @abstractmethod
    def apply_diffuse_color(
        self, node_id: int, r: float, g: float, b: float
    ) -> None:
        """Set the actor-property diffuse colour for *node_id*."""

    @abstractmethod
    def apply_edge_visibility(self, node_id: int, edge_visible: bool) -> None:
        """Toggle edge / wireframe visibility for *node_id*."""

    @abstractmethod
    def apply_selected(
        self, node_id: int, selected: bool, diffuse_rgb: list
    ) -> None:
        """
        Apply or remove the selection highlight on *node_id*.

        *diffuse_rgb* is the part's stored diffuse colour, used when
        deselecting to restore the property DiffuseColor alongside resetting
        Ambient/Diffuse.
        """

    @abstractmethod
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
        """
        Configure the mapper to colour *node_id* by the given scalar array
        and range.

        Parameters
        ----------
        node_id:
            Scene-graph node to update.
        spectrum_id:
            Server-authoritative opaque ID (stored as-is; not parsed here).
        array_type:
            ``"POINT"`` or ``"CELL"``.
        array_name:
            VTK array name.
        component:
            Component index. ``-1`` means magnitude.
        min_val / max_val:
            Scalar display range.
        """

    @abstractmethod
    def clear_color_variable(self, node_id: int) -> None:
        """Disable scalar colouring on *node_id*, reverting to solid diffuse."""

    @abstractmethod
    def refresh_color_variable_range(
        self,
        node_id: int,
        spectrum_id: str,
        array_type: str,
        array_name: str,
        component: int,
    ) -> None:
        """
        Update only the mapper's scalar range for *node_id* from the current
        input data, without calling ``pipeline.base_algorithm.Update()``.

        Safe to call after in-place data modifications where VTK's pipeline
        MTime is stale.
        """

    # ------------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------------

    @abstractmethod
    def reset_camera(self, bounds: list[float]) -> None:
        """Reset the camera to fit *bounds*."""

    @abstractmethod
    def get_camera_state(self) -> "VisorCameraState | None":
        """
        Return the last camera state synced from the frontend, or ``None`` if
        none has been received.
        """

    @abstractmethod
    def sync_camera(self, camera_state: "VisorCameraState") -> None:
        """Store the camera state synced back from the frontend."""

    # ------------------------------------------------------------------------
    # Widget control (cross-section, bounding box)
    # ------------------------------------------------------------------------

    @abstractmethod
    def set_cross_section_visibility(self, visible: bool) -> None:
        """Show or hide the cross-section clipping plane."""

    @abstractmethod
    def sync_cross_section_plane(
        self, origin: list[float], normal: list[float]
    ) -> None:
        """
        Sync the cross-section plane origin and normal from the frontend back
        to server-side VTK objects.
        """

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
    # Render / flush
    # ------------------------------------------------------------------------

    @abstractmethod
    def render(self) -> None:
        """Trigger a render and flush to the frontend."""

    @abstractmethod
    def render_window_only(self) -> None:
        """Render the VTK window without flushing to the frontend."""

    def flush_wasm_state(self) -> None:
        """
        Serialise current Python VTK object state and push it to the wasm
        client without triggering a VTK pipeline re-render.

        No-op default for non-wasm renderers. The local (wasm) renderer
        overrides this to call ``local_view.update()``.
        """

    # ------------------------------------------------------------------------
    # Frontend addressing
    # ------------------------------------------------------------------------

    @property
    @abstractmethod
    def frontend_ref_name(self) -> str:
        """Name by which the frontend view is addressed in ``server.js_call``.

        Empty string for renderers with no frontend view.
        """

