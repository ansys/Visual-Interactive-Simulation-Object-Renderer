"""
CellFeatureFinder
=================
Finds the vertex, edge or face of one picked cell that a geometry pick
reports.
"""

from __future__ import annotations

import math

from vtkmodules.vtkCommonDataModel import vtkCell

from ansys.visor.viewer.models.runtime.picking.geometry_pick import (
    EdgePick,
    FacePick,
    GeometryPick,
    NoGeometryPick,
    VertexPick,
)


class CellFeatureFinder:
    """Finds the feature of one picked cell that a geometry pick reports: the vertex or edge nearest the pick point, or the whole cell."""

    def __init__(self, cell: vtkCell, pick_position: tuple[float, float, float]) -> None:
        """Hold the cell and the world-space point the pick met it at."""
        self._cell = cell
        self._pick_position = pick_position

    @classmethod
    def from_dataset(
        cls, dataset, cell_id: int, pick_position: tuple[float, float, float]
    ) -> CellFeatureFinder | None:
        """None when dataset is None, cell_id is outside [0, cell count), or the dataset has no cell there."""
        if dataset is None or cell_id < 0 or cell_id >= dataset.GetNumberOfCells():
            return None
        cell = dataset.GetCell(cell_id)
        if cell is None:
            return None
        return cls(cell, pick_position)

    def nearest_vertex(self) -> VertexPick:
        """The cell point closest to the pick position."""
        pick_pos = self._pick_position
        n_pts = self._cell.GetNumberOfPoints()
        pts = self._cell.GetPoints()
        best_i = 0
        min_dist2 = float("inf")
        for i in range(n_pts):
            p = pts.GetPoint(i)
            d2 = sum((pick_pos[k] - p[k]) ** 2 for k in range(3))
            if d2 < min_dist2:
                min_dist2 = d2
                best_i = i
        return VertexPick(position=list(pts.GetPoint(best_i)))

    def nearest_edge(self) -> EdgePick | NoGeometryPick:
        """The cell edge closest to the pick position; not found for fewer than two points."""
        pick_pos = self._pick_position
        n_pts = self._cell.GetNumberOfPoints()
        if n_pts < 2:
            return NoGeometryPick()
        pts = self._cell.GetPoints()
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
        return EdgePick(point_a=pt_a, point_b=pt_b, length=length)

    def whole_face(self) -> FacePick:
        """Every cell point and the fan-triangulated area."""
        n_pts = self._cell.GetNumberOfPoints()
        pts = self._cell.GetPoints()
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
        return FacePick(area=area, points=points)

    def find(self, mode: str) -> GeometryPick:
        """The feature for mode; an unknown mode is not found."""
        if mode == "vertex":
            return self.nearest_vertex()
        if mode == "edge":
            return self.nearest_edge()
        if mode == "face":
            return self.whole_face()
        return NoGeometryPick()
