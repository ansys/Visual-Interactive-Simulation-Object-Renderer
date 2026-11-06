"""
PartCellHit
===========
One part cell found under a pick, and the client view a pick is made
through.
"""

from __future__ import annotations

from dataclasses import dataclass

from vtkmodules.vtkCommonDataModel import vtkDataObject

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick, NoGeometryPick
from ansys.visor.viewer.vtk.picking.cell_feature_finder import CellFeatureFinder


@dataclass(frozen=True)
class PartCellHit:
    """One cell of one registered part under a pick, and where the ray met it."""

    node_id: int
    cell_id: int
    position: tuple[float, float, float]
    dataset: vtkDataObject

    def find_feature(self, mode: str) -> GeometryPick:
        """The feature of this cell for mode; a cell id outside the dataset is not found."""
        finder = CellFeatureFinder.from_dataset(self.dataset, self.cell_id, self.position)
        return finder.find(mode) if finder is not None else NoGeometryPick()


@dataclass(frozen=True)
class PickView:
    """A client's camera record and window size, to pick through without touching this window."""

    camera_state: VisorCameraState
    width: int
    height: int
