"""
NullRenderer
============
Behaviour-free test double for :class:`IRenderer`.

Implements every abstract method as a no-op so that the scene coordinator can
be unit-tested without a VTK environment.  Methods whose return type is
annotated return the simplest valid empty value for that type; all others are
``pass``.  No VTK imports, no local view, no side effects.

One exception to "no state": the camera record, ``_last_camera_state``, and
the cross-section plane record, ``_last_cross_section_state``.  The record
half of the :class:`IRenderer` camera and plane contracts is not optional on
any implementation -- only the projection half is, and here it is a no-op
because there is no pipeline camera and no widget to project onto.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.renderer.base import IRenderer

if TYPE_CHECKING:
    from vtkmodules.vtkCommonDataModel import vtkDataObject

    from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode

logger = VisorDefaultLogger(__name__)


class NullRenderer(IRenderer):
    """Null-object implementation of :class:`IRenderer` for use in tests."""

    _last_camera_state: Optional["VisorCameraState"]
    _last_cross_section_state: Optional["VisorCrossSectionState"]

    def __init__(self) -> None:
        """Initialize the camera and cross-section records."""
        self._last_camera_state = None
        self._last_cross_section_state = None

    # ------------------------------------------------------------------
    # Wire contract
    # ------------------------------------------------------------------

    def build_renderer_annotation(self) -> None:
        """See :meth:`IRenderer.build_renderer_annotation`.

        ``None``: a renderer with no client-side handles is represented by
        wire absence, not by a value.
        """
        return None

    # ------------------------------------------------------------------
    # Node lifecycle
    # ------------------------------------------------------------------

    def register_node(
        self, node: "VisorSceneGraphPartNode", dataset: "vtkDataObject"
    ) -> None:
        pass

    def deregister_node(self, node_id: int) -> None:
        pass

    def deregister_all(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Per-part visual mutations
    # ------------------------------------------------------------------

    def apply_visibility(self, node_id: int, visible: bool) -> None:
        pass

    def apply_opacity(self, node_id: int, opacity: float) -> None:
        pass

    def apply_diffuse_color(self, node_id: int, r: float, g: float, b: float) -> None:
        pass

    def apply_selected(self, node_id: int, selected: bool, diffuse_rgb: list) -> None:
        pass

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
        pass

    def clear_color_variable(self, node_id: int) -> None:
        pass

    def refresh_color_variable_range(
        self,
        node_id: int,
        spectrum_id: str,
        array_type: str,
        array_name: str,
        component: int,
    ) -> None:
        pass

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    def reset_camera(self, bounds: list[float]) -> None:
        """See :meth:`IRenderer.reset_camera`.

        Deliberately does not write the record: with no pipeline camera there
        is nothing to derive a camera for *bounds* from, and clearing it would
        destroy a camera the frontend reported.
        """

    def get_camera_state(self) -> "VisorCameraState | None":
        """See :meth:`IRenderer.get_camera_state`."""
        return self._last_camera_state

    def sync_camera(self, camera_state: "VisorCameraState") -> None:
        """See :meth:`IRenderer.sync_camera`."""
        self._last_camera_state = camera_state

    def set_projection(self, parallel: bool) -> None:
        """See :meth:`IRenderer.set_projection`.

        Record only: there is no pipeline camera to project onto.
        """
        if self._last_camera_state is not None:
            self._last_camera_state.parallel_projection = parallel
        else:
            logger.debug(
                "set_projection: no camera record; nothing to write."
            )

    def serialize_camera_state(self) -> None:
        """See :meth:`IRenderer.serialize_camera_state`.

        No-op: this renderer serves the client no VTK object state.
        """


    # ------------------------------------------------------------------
    # Widget control (cross-section, bounding box, edges)
    # ------------------------------------------------------------------

    def set_edges_visible(self, visible: bool) -> None:
        """No pipelines to fan out over; nothing to do."""

    def set_cross_section_visibility(self, visible: bool) -> None:
        pass

    def sync_cross_section_plane(
        self, origin: list[float], normal: list[float]
    ) -> None:
        """See :meth:`IRenderer.sync_cross_section_plane`.

        Record only: there are no VTK widget objects to project onto.  The
        record takes a copy of each list, as :class:`VisorLocalRenderer` does.
        """
        self._last_cross_section_state = VisorCrossSectionState(
            origin=list(origin), normal=list(normal)
        )

    def get_cross_section_plane(self) -> "VisorCrossSectionState | None":
        """See :meth:`IRenderer.get_cross_section_plane`.

        ``None`` unless :meth:`sync_cross_section_plane` wrote one: there is
        no widget here for :meth:`update_bounds` to seed a record from.
        """
        return self._last_cross_section_state

    def serialize_cross_section_state(self) -> None:
        """See :meth:`IRenderer.serialize_cross_section_state`.

        No-op: this renderer serves the client no VTK object state.
        """

    def set_bounding_box_visibility(self, visible: bool) -> None:
        pass

    # ------------------------------------------------------------------
    # Widget fan-out
    # ------------------------------------------------------------------

    def update_bounds(self, bounds: list[float]) -> None:
        pass

    def update_actor_count(self, count: int) -> None:
        pass

    # ------------------------------------------------------------------
    # Picking
    # ------------------------------------------------------------------

    def pick_geometry(
        self,
        actor_wasm_id: int,
        cell_id: int,
        mode: str,
        world_pos: tuple[float, float, float],
    ) -> dict:
        return {}

    # ------------------------------------------------------------------
    # Render / flush
    # ------------------------------------------------------------------

    def render(self) -> None:
        pass

    def render_window_only(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Frontend addressing
    # ------------------------------------------------------------------

    @property
    def frontend_ref_name(self) -> str:
        return ""

