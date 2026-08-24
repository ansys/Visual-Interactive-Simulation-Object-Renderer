"""
NullRenderer
============
Behaviour-free test double for :class:`IRenderer`.

Implements every abstract method as a no-op so that the scene coordinator can
be unit-tested without a VTK environment.  Methods whose return type is
annotated return the simplest valid empty value for that type; all others are
``pass``.  No VTK imports, no local view, no side effects, no state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ansys.visor.viewer.renderer.base import IRenderer

if TYPE_CHECKING:
    from vtkmodules.vtkCommonDataModel import vtkDataObject

    from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode


class NullRenderer(IRenderer):
    """Null-object implementation of :class:`IRenderer` for use in tests."""

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

    def apply_edge_visibility(self, node_id: int, edge_visible: bool) -> None:
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
        pass

    def get_camera_state(self) -> "VisorCameraState | None":
        return None

    def sync_camera(self, camera_state: "VisorCameraState") -> None:
        pass

    # ------------------------------------------------------------------
    # Widget control (cross-section, bounding box)
    # ------------------------------------------------------------------

    def set_cross_section_visibility(self, visible: bool) -> None:
        pass

    def sync_cross_section_plane(
        self, origin: list[float], normal: list[float]
    ) -> None:
        pass

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

