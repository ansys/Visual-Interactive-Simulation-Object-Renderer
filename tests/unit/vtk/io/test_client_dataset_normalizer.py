"""Unit tests for ClientDatasetNormalizer.

Inputs are hand-built ``vtkLongArray`` / ``vtkUnsignedLongArray`` datasets, so
these run on any OS: a ``vtkLongArray``-backed ``vtkCellArray`` uses generic
storage everywhere, which is what ``vtkHDFReader`` produces on LP64 hosts.
"""

from vtkmodules.vtkCommonCore import (
    vtkFloatArray,
    vtkLongArray,
    vtkPoints,
    vtkTypeInt64Array,
    vtkUnsignedCharArray,
    vtkUnsignedLongArray,
)
from vtkmodules.vtkCommonDataModel import (
    VTK_TRIANGLE,
    vtkCellArray,
    vtkMultiBlockDataSet,
    vtkPolyData,
    vtkUnstructuredGrid,
)

from ansys.visor.viewer.vtk.io.client_dataset_normalizer import ClientDatasetNormalizer


def _array(cls, name, values):
    array = cls()
    array.SetName(name)
    for value in values:
        array.InsertNextValue(value)
    return array


def _triangle_points() -> vtkPoints:
    points = vtkPoints()
    for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        points.InsertNextPoint(p)
    return points


def _cells(cls) -> vtkCellArray:
    cells = vtkCellArray()
    cells.SetData(_array(cls, None, (0, 3)), _array(cls, None, (0, 1, 2)))
    return cells


def _triangle_polydata(cell_array_class: type = vtkLongArray) -> vtkPolyData:
    poly = vtkPolyData()
    poly.SetPoints(_triangle_points())
    poly.SetPolys(_cells(cell_array_class))
    return poly


def _triangle_grid() -> vtkUnstructuredGrid:
    grid = vtkUnstructuredGrid()
    grid.SetPoints(_triangle_points())
    types = vtkUnsignedCharArray()
    types.InsertNextValue(VTK_TRIANGLE)
    grid.SetCells(types, _cells(vtkLongArray))
    return grid


def _values(array) -> list:
    return [array.GetValue(i) for i in range(array.GetNumberOfValues())]


def test_generic_polydata_cells_become_int64_storage():
    """Generic-storage cells are re-seated as vtkTypeInt64Array with the same values."""
    poly = _triangle_polydata()

    ClientDatasetNormalizer.normalize_dataset_for_client(poly)

    cells = poly.GetPolys()
    assert cells.IsStorageGeneric() is False
    assert cells.GetConnectivityArray().GetClassName() == "vtkTypeInt64Array"
    assert cells.GetOffsetsArray().GetClassName() == "vtkTypeInt64Array"
    assert _values(cells.GetConnectivityArray()) == [0, 1, 2]
    assert _values(cells.GetOffsetsArray()) == [0, 3]


def test_long_point_cell_and_field_arrays_become_fixed_width():
    """Long point, cell and field arrays become fixed-width with name and values kept."""
    poly = _triangle_polydata()
    poly.GetPointData().AddArray(_array(vtkLongArray, "pid", (7, 8, 9)))
    poly.GetCellData().AddArray(_array(vtkUnsignedLongArray, "cid", (5,)))
    poly.GetFieldData().AddArray(_array(vtkLongArray, "fid", (11, 12)))

    ClientDatasetNormalizer.normalize_dataset_for_client(poly)

    pid = poly.GetPointData().GetArray("pid")
    cid = poly.GetCellData().GetArray("cid")
    fid = poly.GetFieldData().GetArray("fid")
    assert (pid.GetClassName(), _values(pid)) == ("vtkTypeInt64Array", [7, 8, 9])
    assert (cid.GetClassName(), _values(cid)) == ("vtkTypeUInt64Array", [5])
    assert (fid.GetClassName(), _values(fid)) == ("vtkTypeInt64Array", [11, 12])


def test_array_order_and_active_scalars_are_kept():
    """Replacing a middle array keeps array order and its active-scalars role."""
    poly = _triangle_polydata()
    point_data = poly.GetPointData()
    point_data.AddArray(_array(vtkFloatArray, "a", (1.0, 2.0, 3.0)))
    point_data.AddArray(_array(vtkLongArray, "b", (4, 5, 6)))
    point_data.AddArray(_array(vtkFloatArray, "c", (7.0, 8.0, 9.0)))
    point_data.SetActiveScalars("b")

    ClientDatasetNormalizer.normalize_dataset_for_client(poly)

    names = [point_data.GetArrayName(i) for i in range(point_data.GetNumberOfArrays())]
    assert names == ["a", "b", "c"]
    assert point_data.GetScalars().GetName() == "b"
    assert point_data.GetScalars().GetClassName() == "vtkTypeInt64Array"


def test_composite_leaves_are_normalized():
    """Leaves of a nested multiblock (polydata and unstructured grid) are both normalized."""
    inner = vtkMultiBlockDataSet()
    inner.SetNumberOfBlocks(1)
    inner.SetBlock(0, _triangle_polydata())
    outer = vtkMultiBlockDataSet()
    outer.SetNumberOfBlocks(2)
    outer.SetBlock(0, inner)
    outer.SetBlock(1, _triangle_grid())

    replaced = ClientDatasetNormalizer.normalize_dataset_for_client(outer)

    poly = outer.GetBlock(0).GetBlock(0)
    grid = outer.GetBlock(1)
    assert poly.GetPolys().GetConnectivityArray().GetClassName() == "vtkTypeInt64Array"
    assert grid.GetCells().GetConnectivityArray().GetClassName() == "vtkTypeInt64Array"
    assert replaced == 2


def test_fixed_width_dataset_is_left_untouched():
    """A dataset with nothing to convert is a no-op: count 0, same array objects."""
    poly = _triangle_polydata(cell_array_class=vtkTypeInt64Array)
    poly.GetPointData().AddArray(_array(vtkFloatArray, "a", (1.0, 2.0, 3.0)))
    connectivity = poly.GetPolys().GetConnectivityArray()
    scalars = poly.GetPointData().GetArray("a")

    replaced = ClientDatasetNormalizer.normalize_dataset_for_client(poly)

    assert replaced == 0
    assert poly.GetPolys().GetConnectivityArray() is connectivity
    assert poly.GetPointData().GetArray("a") is scalars

