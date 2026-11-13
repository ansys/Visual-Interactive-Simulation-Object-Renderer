"""
Unit tests for CellFeatureFinder.

Coverage targets
----------------
1.  find -- vertex, edge and face modes, dumped by alias as the wire carries
    them; an unknown mode is not found.
2.  from_dataset -- a negative cell id, a cell id past the last cell, and no
    dataset at all each give no finder.
"""

from __future__ import annotations

import pytest

from ansys.visor.viewer.vtk.picking.cell_feature_finder import CellFeatureFinder

# ---------------------------------------------------------------------------
# Lightweight VTK-data stubs (no real VTK objects required)
# ---------------------------------------------------------------------------

class _DummyPoints:
    def __init__(self, pts):
        self._pts = pts

    def GetPoint(self, i): # noqa: N802
        return tuple(self._pts[i])


class _DummyCell:
    def __init__(self, points):
        self._pts = _DummyPoints(points)
        self._n = len(points)

    def GetNumberOfPoints(self): # noqa: N802
        return self._n

    def GetPoints(self): # noqa: N802
        return self._pts


class _DummyDataset:
    def __init__(self, cells):
        self._cells = cells

    def GetNumberOfCells(self): # noqa: N802
        return len(self._cells)

    def GetCell(self, idx): # noqa: N802
        return self._cells[idx] if 0 <= idx < len(self._cells) else None


class TestCellFeatureFinder:

    def test_vertex_returns_nearest_point(self):
        """Vertex mode returns the cell point closest to the pick position."""
        pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])

        res = CellFeatureFinder.from_dataset(dataset, 0, (0.9, 0.1, 0.0)).find("vertex").model_dump(by_alias=True)

        assert res["found"] is True
        assert res["mode"] == "vertex"
        assert tuple(res["position"]) == (1.0, 0.0, 0.0)

    def test_edge_returns_closest_edge_endpoints_and_length(self):
        """Edge mode returns the two endpoints of the edge nearest to the pick."""
        pts = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])

        res = CellFeatureFinder.from_dataset(dataset, 0, (2.01, 1.0, 0.0)).find("edge").model_dump(by_alias=True)

        assert res["found"] is True
        assert res["mode"] == "edge"
        assert tuple(res["pointA"]) == (2.0, 0.0, 0.0)
        assert tuple(res["pointB"]) == (2.0, 2.0, 0.0)
        assert pytest.approx(res["edgeLength"]) == 2.0

    def test_face_returns_area_and_all_points(self):
        """Face mode returns the polygon area and every cell point."""
        pts = [(0, 0, 0), (1, 0, 0), (1, 2, 0), (0, 2, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])

        res = CellFeatureFinder.from_dataset(dataset, 0, (0.5, 1.0, 0.0)).find("face").model_dump(by_alias=True)

        assert res["found"] is True
        assert res["mode"] == "face"
        assert pytest.approx(res["area"]) == 2.0
        assert len(res["points"]) == 4

    def test_negative_cell_id_is_not_found(self):
        dataset = _DummyDataset([_DummyCell([(0, 0, 0), (1, 0, 0), (0, 1, 0)])])
        assert CellFeatureFinder.from_dataset(dataset, -1, (0.0, 0.0, 0.0)) is None

    def test_cell_id_out_of_range_is_not_found(self):
        """Cell index beyond dataset size gives no finder."""
        dataset = _DummyDataset([_DummyCell([(0, 0, 0), (1, 0, 0), (0, 1, 0)])])
        assert CellFeatureFinder.from_dataset(dataset, 99, (0.0, 0.0, 0.0)) is None

    def test_unknown_mode_returns_not_found(self):
        """An unrecognised mode string falls through to not-found."""
        pts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        dataset = _DummyDataset([_DummyCell(pts)])
        res = CellFeatureFinder.from_dataset(dataset, 0, (0.0, 0.0, 0.0)).find("INVALID_MODE").model_dump(by_alias=True)
        assert res == {"found": False}

    def test_none_dataset_is_not_found(self):
        """A picked actor whose mapper has no input dataset gives no finder."""
        assert CellFeatureFinder.from_dataset(None, 0, (0.0, 0.0, 0.0)) is None
