"""
NullRenderer
============
Behaviour-free test double for :class:`IRenderer`.

Implements every abstract method as a no-op so that the scene coordinator can
be unit-tested without a VTK environment.  Methods whose return type is
annotated return the simplest valid empty value for that type; all others are
``pass``.  No VTK imports, no local view, no side effects.

The camera and cross-section plane records, and their readers and writers,
are inherited from :class:`IRenderer`: there is no pipeline camera and no
widget here to project them onto.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ansys.visor.viewer.renderer.base import IRenderer

if TYPE_CHECKING:
    from vtkmodules.vtkCommonDataModel import vtkDataObject

    from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
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

    def apply_selected(self, node_id: int, selected: bool, diffuse_rgb: list) -> None:
        pass

    def apply_color_variable(
        self,
        node_id: int,
        array_type: "VisorVtkVariableType",
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> None:
        pass

    def clear_color_variable(self, node_id: int) -> None:
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


    # ------------------------------------------------------------------
    # Widget control (cross-section, bounding box, edges)
    # ------------------------------------------------------------------

    def set_edges_visible(self, visible: bool) -> None:
        """No pipelines to fan out over; nothing to do."""

    def set_cross_section_visibility(self, visible: bool) -> None:
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
    # Render
    # ------------------------------------------------------------------

    def render(self) -> None:
        pass


