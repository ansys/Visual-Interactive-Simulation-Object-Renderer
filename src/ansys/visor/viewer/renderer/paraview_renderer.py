"""
ParaviewRenderer
================
:class:`IRenderer` over a ParaView render view on pvserver.

Each registered part is a representation of a pvserver proxy, written
through a :class:`ParaviewSession`.  Like :class:`ServerRenderer`, it never
renders on the calling thread: every write ends in a frame request, and only
the capture renders.  Each camera write also hands the record to a
:class:`ViewRecordPublisher`.

Composite input is not supported yet: :meth:`ParaviewRenderer.open_source`
raises for it, so every part is the opened source itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ansys.visor.viewer.core.errors import UnsupportedInModeError, VisorAddDatasetError
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_helpers import is_composite_dataset
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.renderer.base import IRenderer

if TYPE_CHECKING:
    from vtkmodules.vtkCommonDataModel import vtkDataObject
    from vtkmodules.vtkRenderingCore import vtkRenderWindow

    from ansys.visor.viewer.core.visor_types import VisorDatasetType
    from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
    from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick
    from ansys.visor.viewer.renderer.paraview_session import (
        ParaviewSession,
        PvRepresentation,
        PvSource,
    )
    from ansys.visor.viewer.renderer.streamed_protocols import FrameRequester, ViewRecordPublisher
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode

logger = VisorDefaultLogger(__name__)

SELECTED_AMBIENT_RGB: tuple[float, float, float] = (0 / 255, 62 / 255, 111 / 255)
"""Ambient tint of a selected part, as the VTK pipeline applies it."""

_ASSOCIATIONS: dict[VisorVtkVariableType, str] = {
    VisorVtkVariableType.POINT: "POINTS",
    VisorVtkVariableType.CELL: "CELLS",
}


@dataclass
class _Part:
    """One registered part: the proxy it shows, its representation and the local dataset it mirrors."""

    source_key: str
    shown: PvSource
    is_extract: bool
    rep: PvRepresentation
    dataset: vtkDataObject


class ParaviewRenderer(IRenderer):
    """IRenderer over a ParaView render view; per-part representations of block extracts."""

    def __init__(
        self,
        session: ParaviewSession,
        background_rgb: tuple[float, float, float],
        frame_requester: FrameRequester,
        view_record_publisher: ViewRecordPublisher,
    ) -> None:
        """Hold the session; every write ends in a frame request, every camera write also publishes the record."""
        super().__init__()
        self._session = session
        self._frame_requester = frame_requester
        self._view_record_publisher = view_record_publisher
        self._sources: dict[str, PvSource] = {}
        # id() of each local leaf dataset -> (dataset key, the leaf).  The leaf
        # is held so its id cannot be reused while the entry exists.
        self._leaf_index: dict[int, tuple[str, vtkDataObject]] = {}
        self._parts: dict[int, _Part] = {}
        self._bounds: list[float] | None = None
        self._actor_count = 0
        self._background_rgb = background_rgb
        self._session.set_background(background_rgb)

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def open_source(self, dataset_key: str, server_path: str, local_root: VisorDatasetType) -> None:
        """Open server_path on pvserver and index local_root's leaves; raise UnsupportedInModeError for composite input.

        A non-composite root is its own single leaf, shown with no extract.
        """
        if is_composite_dataset(local_root):
            raise UnsupportedInModeError("composite dataset is not supported in PARAVIEW mode")
        self._sources[dataset_key] = self._session.open(server_path)
        self._leaf_index[id(local_root)] = (dataset_key, local_root)

    def close_source(self, dataset_key: str) -> None:
        """Delete the source and every extract of it on pvserver."""
        source = self._sources.pop(dataset_key, None)
        if source is None:
            logger.debug("close_source: no source for %s; skipping.", dataset_key)
            return
        for node_id in [nid for nid, part in self._parts.items() if part.source_key == dataset_key]:
            part = self._parts.pop(node_id)
            if part.is_extract:
                self._session.delete(part.shown)
        self._leaf_index = {k: v for k, v in self._leaf_index.items() if v[0] != dataset_key}
        self._session.delete(source)

    # ------------------------------------------------------------------
    # IRenderer: wire contract
    # ------------------------------------------------------------------

    def build_renderer_annotation(self) -> None:
        """None: no client-side handles."""
        return None

    # ------------------------------------------------------------------
    # IRenderer: node lifecycle
    # ------------------------------------------------------------------

    def register_node(self, node: VisorSceneGraphPartNode, dataset: vtkDataObject) -> None:
        """Show the node's proxy and check its point count; idempotent.

        Raises :class:`VisorAddDatasetError` when no opened source holds
        *dataset*, or when pvserver's point count differs from the local
        dataset's: either means the part would show the wrong geometry.
        """
        if node.id in self._parts:
            return
        entry = self._leaf_index.get(id(dataset))
        if entry is None:
            raise VisorAddDatasetError(f"No pvserver source holds part {node.name!r}")
        dataset_key = entry[0]
        shown = self._sources[dataset_key]
        rep = self._session.show(shown)
        local_points = dataset.GetNumberOfPoints()
        server_points = self._session.point_count(shown)
        if server_points != local_points:
            raise VisorAddDatasetError(
                f"Part {node.name!r}: pvserver reports {server_points} points, "
                f"the local dataset has {local_points}"
            )
        self._parts[node.id] = _Part(dataset_key, shown, False, rep, dataset)

    def deregister_node(self, node_id: int) -> None:
        """Delete the node's extract, or hide the source it shows; silent if unknown."""
        part = self._parts.pop(node_id, None)
        if part is None:
            logger.debug("deregister_node: no part for node %s; skipping.", node_id)
            return
        if part.is_extract:
            self._session.delete(part.shown)
        else:
            self._session.set_property(part.rep, "Visibility", 0)

    def deregister_all(self) -> None:
        """Delete every extract and source."""
        for part in self._parts.values():
            if part.is_extract:
                self._session.delete(part.shown)
        self._parts.clear()
        for source in self._sources.values():
            self._session.delete(source)
        self._sources.clear()
        self._leaf_index.clear()

    # ------------------------------------------------------------------
    # IRenderer: per-part visual mutations
    # ------------------------------------------------------------------

    def _part(self, node_id: int, operation: str) -> _Part | None:
        """The registered part for node_id, or None after a debug log."""
        part = self._parts.get(node_id)
        if part is None:
            logger.debug("%s: no part for node %s; skipping.", operation, node_id)
        return part

    def apply_visibility(self, node_id: int, visible: bool) -> None:
        """Write Visibility, then request a frame."""
        part = self._part(node_id, "apply_visibility")
        if part is None:
            return
        self._session.set_property(part.rep, "Visibility", 1 if visible else 0)
        self._frame_requester.request_frame()

    def apply_opacity(self, node_id: int, opacity: float) -> None:
        """Write Opacity, then request a frame."""
        part = self._part(node_id, "apply_opacity")
        if part is None:
            return
        self._session.set_property(part.rep, "Opacity", opacity)
        self._frame_requester.request_frame()

    def apply_diffuse_color(self, node_id: int, r: float, g: float, b: float) -> None:
        """Write DiffuseColor, then request a frame."""
        part = self._part(node_id, "apply_diffuse_color")
        if part is None:
            return
        self._session.set_property(part.rep, "DiffuseColor", [r, g, b])
        self._frame_requester.request_frame()

    def apply_selected(self, node_id: int, selected: bool, diffuse_rgb: list) -> None:
        """Write AmbientColor, Ambient and Diffuse as the pipeline renderer does, and DiffuseColor; then request a frame."""
        part = self._part(node_id, "apply_selected")
        if part is None:
            return
        rep = part.rep
        if selected:
            self._session.set_property(rep, "AmbientColor", list(SELECTED_AMBIENT_RGB))
            self._session.set_property(rep, "Diffuse", 0.5)
            self._session.set_property(rep, "Ambient", 0.5)
        else:
            self._session.set_property(rep, "Diffuse", 1.0)
            self._session.set_property(rep, "Ambient", 0.0)
        self._session.set_property(rep, "DiffuseColor", list(diffuse_rgb))
        self._frame_requester.request_frame()

    def apply_color_variable(
        self,
        node_id: int,
        array_type: VisorVtkVariableType,
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> None:
        """ColorBy with a separate map, then rescale, then request a frame.

        Component ``-1`` is ParaView's ``"Magnitude"``; component ``n`` is
        passed as ``str(n)``, which ParaView reads as an index when no
        component carries that name.  An association that is not a
        :class:`VisorVtkVariableType`, and an array the part's dataset does
        not have, are logged no-ops, as in the pipeline renderer.
        """
        part = self._part(node_id, "apply_color_variable")
        if part is None:
            return
        association = _ASSOCIATIONS.get(array_type) if isinstance(array_type, VisorVtkVariableType) else None
        if association is None:
            logger.warning(
                "apply_color_variable: association %r is not a VisorVtkVariableType; skipping.", array_type
            )
            return
        field = part.dataset.GetPointData() if association == "POINTS" else part.dataset.GetCellData()
        if field.GetArray(array_name) is None:
            logger.warning(
                "apply_color_variable: array %r not found for association %s; skipping.", array_name, array_type
            )
            return
        component_name = "Magnitude" if component == -1 else str(component)
        self._session.color_by(part.rep, association, array_name, component_name)
        self._session.rescale(part.rep, min_val, max_val)
        self._frame_requester.request_frame()

    def clear_color_variable(self, node_id: int) -> None:
        """ColorBy None, then request a frame."""
        part = self._part(node_id, "clear_color_variable")
        if part is None:
            return
        self._session.clear_color(part.rep)
        self._frame_requester.request_frame()

    # ------------------------------------------------------------------
    # IRenderer: camera
    # ------------------------------------------------------------------

    def reset_camera(self, bounds: list[float]) -> None:
        """Reset the view camera to bounds and record it; publish, then request a frame."""
        self._session.reset_camera(bounds)
        self._last_camera_state = self._session.read_camera()
        self._publish_camera_record()
        self._frame_requester.request_frame()

    def sync_camera(self, camera_state: VisorCameraState) -> None:
        """Record, then write the view camera; publish, then request a frame."""
        super().sync_camera(camera_state)
        self._session.write_camera(camera_state)
        self._publish_camera_record()
        self._frame_requester.request_frame()

    def set_projection(self, parallel: bool) -> None:
        """Record, then write CameraParallelProjection; publish, then request a frame.

        The view write is unconditional, with or without a record, as in the
        pipeline renderer.
        """
        super().set_projection(parallel)
        camera = self._session.read_camera()
        camera.parallel_projection = parallel
        self._session.write_camera(camera)
        self._publish_camera_record()
        self._frame_requester.request_frame()

    def _publish_camera_record(self) -> None:
        """Hand the camera record to the record publisher; requests no frame."""
        self._view_record_publisher.publish_camera(self.get_camera_state())

    # ------------------------------------------------------------------
    # IRenderer: widget control and fan-out
    # ------------------------------------------------------------------

    def set_edges_visible(self, visible: bool) -> None:
        """Write the edges representation on every part, then request a frame."""
        representation = "Surface With Edges" if visible else "Surface"
        for part in self._parts.values():
            self._session.set_property(part.rep, "Representation", representation)
        self._frame_requester.request_frame()

    def set_cross_section_visibility(self, visible: bool) -> None:
        """Log WARNING: not supported in PARAVIEW mode."""
        logger.warning("cross-section is not supported in PARAVIEW mode")

    def set_bounding_box_visibility(self, visible: bool) -> None:
        """Log WARNING: not supported in PARAVIEW mode."""
        logger.warning("bounding box is not supported in PARAVIEW mode")

    def update_bounds(self, bounds: list[float]) -> None:
        """Record bounds."""
        self._bounds = list(bounds)

    def update_actor_count(self, count: int) -> None:
        """Record the part count."""
        self._actor_count = count

    def show_geometry_highlight(self, pick: GeometryPick) -> None:
        """Log WARNING: not supported in PARAVIEW mode."""
        logger.warning("geometry highlight is not supported in PARAVIEW mode")

    # ------------------------------------------------------------------
    # IRenderer: render
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Request a frame; never renders on the calling thread."""
        self._frame_requester.request_frame()

    # ------------------------------------------------------------------
    # RCA render-target surface
    # ------------------------------------------------------------------

    @property
    def render_window(self) -> vtkRenderWindow:
        """The window the RCA capture reads."""
        return self._session.render_window

    def set_viewport_size(self, width: int, height: int) -> None:
        """Resize the view; requests no frame."""
        self._session.set_viewport_size(width, height)

    def set_pixel_scale(self, pixel_scale: float) -> None:
        """Accept and ignore: no highlight to rescale."""

    def set_background_rgb(self, background_rgb: tuple[float, float, float]) -> None:
        """Clear to this colour from the next frame; requests no frame."""
        self._background_rgb = background_rgb
        self._session.set_background(background_rgb)

    def record_pipeline_camera(self) -> None:
        """Read the view camera, record it and publish it; requests no frame."""
        super().sync_camera(self._session.read_camera())
        self._publish_camera_record()

    def record_cross_section_plane(self) -> None:
        """Nothing: no plane widget."""

    @property
    def background_rgb(self) -> tuple[float, float, float]:
        """The colour the view clears to."""
        return self._background_rgb
