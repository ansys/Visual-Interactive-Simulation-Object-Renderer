"""Aliases for Visor types."""


from typing import Sequence, TypeAlias, Union

import numpy as np
from vtkmodules.vtkCommonDataModel import (
    vtkDataObject,
    vtkMultiBlockDataSet,
    vtkMultiPieceDataSet,
    vtkPolyData,
    vtkUnstructuredGrid,
)

VisorDatasetType: TypeAlias = (
    vtkDataObject
    | vtkMultiBlockDataSet
    | vtkMultiPieceDataSet
    | vtkUnstructuredGrid
    | vtkPolyData
)

ArrayLike = Union[np.ndarray, Sequence[float]]
