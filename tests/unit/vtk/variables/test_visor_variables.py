import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pytest

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType

# Ensure 'src' layout is importable
sys.path.insert(0, os.path.abspath("src"))

# Import the module under test
import ansys.visor.viewer.vtk.variables.visor_variables as tvmod

# ----- Fake external dependencies and VTK-like classes -----

@dataclass
class FakeVariableInfo:
    index_for_type: int
    type: str
    name: str
    num_components: int
    ranges: List[Tuple[float, float]]
    magnitude_range: Optional[Tuple[float, float]]


@dataclass
class FakeUpdate:
    name: str
    num_components: int
    type: VisorVtkVariableType


class FakeDataArray:
    def __init__(
        self,
        name: str,
        num_components: int,
        num_tuples: int,
        component_ranges: List[Tuple[float, float]],
        magnitude_range: Optional[Tuple[float, float]] = None,
    ):
        assert len(component_ranges) == num_components
        self._name = name
        self._num_components = num_components
        self._num_tuples = num_tuples
        self._component_ranges = component_ranges
        self._magnitude_range = magnitude_range if magnitude_range is not None else (0.0, 0.0)

    def GetName(self): # noqa: N802
        return self._name

    def GetNumberOfComponents(self): # noqa: N802
        return self._num_components

    def GetNumberOfTuples(self):# noqa: N802
        return self._num_tuples

    def GetRange(self, i: int): # noqa: N802
        if i < 0:
            return self._magnitude_range
        return self._component_ranges[i]


class FakeFieldData:
    def __init__(self, arrays: List[Optional[FakeDataArray]]):
        self._arrays = arrays

    def GetNumberOfArrays(self): # noqa: N802
        return len(self._arrays)

    def GetArray(self, i: int): # noqa: N802
        return self._arrays[i]


class FakeDataset:
    def __init__(self, point_arrays: List[Optional[FakeDataArray]], cell_arrays: List[Optional[FakeDataArray]]):
        self._point = FakeFieldData(point_arrays)
        self._cell = FakeFieldData(cell_arrays)

    def GetPointData(self): # noqa: N802
        return self._point

    def GetCellData(self): # noqa: N802
        return self._cell


# ----- Auto-patch module dependencies for all tests -----

@pytest.fixture(autouse=True)
def patch_module_dependencies(monkeypatch):
    """Provides fake external dependencies for the module under test."""
    # Replace external enum and info class
    monkeypatch.setattr(tvmod, "VisorVtkVariableType", VisorVtkVariableType, raising=True)
    monkeypatch.setattr(tvmod, "VisorVariableInfo", FakeVariableInfo, raising=True)
    # Note: is_composite_dataset was removed from visor_variables — VisorVariables
    # now always operates on a single leaf block (composite traversal is done at the
    # VisorDataset level before constructing per-part VisorVariables instances).


# ----- Tests for VisorVariable public API -----

def test_visor_variable_from_array_and_conversions():
    """Verify that VisorVariable.from_array and conversions to dict/info work correctly."""
    arr = FakeDataArray(
        name="Velocity",
        num_components=3,
        num_tuples=100,
        component_ranges=[(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)],
        magnitude_range=(0.0, 3.5),
    )

    var = tvmod.VisorVariable.from_array(index=2, arr=arr, variable_type=VisorVtkVariableType.POINT)

    assert var.index == 2
    assert var.type is VisorVtkVariableType.POINT
    assert var.name == "Velocity"
    assert var.num_components == 3
    assert var.num_points == 100
    assert var.ranges == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]
    assert var.magnitude_range == (0.0, 3.5)

    as_dict = var.to_dict()
    assert as_dict["index"] == 2
    assert as_dict["type"] == "POINT"
    assert as_dict["name"] == "Velocity"
    assert as_dict["num_components"] == 3
    assert as_dict["num_points"] == 100
    assert as_dict["ranges"] == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]
    assert as_dict["magnitude_range"] == (0.0, 3.5)

    info = var.to_info()
    assert isinstance(info, FakeVariableInfo)
    assert info.index_for_type == 2
    assert info.type is VisorVtkVariableType.POINT
    assert info.name == "Velocity"
    assert info.num_components == 3
    assert info.ranges == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]
    assert info.magnitude_range == (0.0, 3.5)


# ----- Tests for VisorVariables public API -----

def test_visor_variables_init_and_listing():
    """Verify that VisorVariables initializes correctly and lists variables."""
    # One point array, two cell arrays with one None to ensure it is skipped
    p_arr = FakeDataArray("PVar", 1, 10, [(0.0, 10.0)], (0.0, 10.0))
    c_arr = FakeDataArray("CVar", 2, 5, [(1.0, 2.0), (3.0, 4.0)], (1.0, 4.0))
    ds = FakeDataset(point_arrays=[p_arr], cell_arrays=[c_arr, None])

    variables = tvmod.VisorVariables(ds)

    all_vars = variables.list()
    assert len(all_vars) == 2
    names = {v.name for v in all_vars}
    assert names == {"PVar", "CVar"}

    # Ensure types and indexes
    p = next(v for v in all_vars if v.name == "PVar")
    c = next(v for v in all_vars if v.name == "CVar")
    assert p.type is VisorVtkVariableType.POINT and p.index == 0
    assert c.type is VisorVtkVariableType.CELL and c.index == 0

    # list_info returns FakeVariableInfo objects
    infos = variables.list_info()
    assert len(infos) == 2
    assert {i.name for i in infos} == {"PVar", "CVar"}
    assert {i.type for i in infos} == {VisorVtkVariableType.POINT, VisorVtkVariableType.CELL}


def test_visor_variables_reload_replaces_metadata():
    """Verify that VisorVariables.reload replaces the internal variable metadata."""
    # Initial dataset
    p1 = FakeDataArray("P1", 1, 3, [(0.0, 1.0)], (0.0, 1.0))
    c1 = FakeDataArray("C1", 1, 2, [(2.0, 3.0)], (2.0, 3.0))
    ds1 = FakeDataset(point_arrays=[p1], cell_arrays=[c1])

    variables = tvmod.VisorVariables(ds1)
    assert {v.name for v in variables.list()} == {"P1", "C1"}

    # New dataset
    p2 = FakeDataArray("P2", 2, 4, [(0.0, 5.0), (1.0, 6.0)], (0.0, 6.0))
    p3 = FakeDataArray("P3", 1, 1, [(-1.0, 1.0)], (-1.0, 1.0))
    ds2 = FakeDataset(point_arrays=[p2, p3], cell_arrays=[])

    variables.reload(ds2)
    names_after = {v.name for v in variables.list()}
    assert names_after == {"P2", "P3"}
    assert all(v.type is VisorVtkVariableType.POINT for v in variables.list())


def test_validate_new_variables_happy_path_and_edge_cases():
    """Verify that validate_new_variables returns True for valid updates and False for invalid ones."""
    # Dataset with one POINT and one CELL variable
    p = FakeDataArray("PVar", 1, 10, [(0.0, 10.0)], (0.0, 10.0))
    c = FakeDataArray("CVar", 3, 5, [(1.0, 2.0), (3.0, 5.0), (0.0, 4.0)], (0.0, 5.0))
    ds = FakeDataset(point_arrays=[p], cell_arrays=[c])

    variables = tvmod.VisorVariables(ds)

    # Valid updates
    updates_valid = [
        FakeUpdate(name="PVar", num_components=1, type=VisorVtkVariableType.POINT),
        FakeUpdate(name="CVar", num_components=3, type=VisorVtkVariableType.CELL),
    ]
    assert variables.validate_new_variables(updates_valid) is True

    # Empty list is valid
    assert variables.validate_new_variables([]) is True

    # Unknown name for POINT
    updates_bad_name = [
        FakeUpdate(name="Unknown", num_components=1, type=VisorVtkVariableType.POINT),
    ]
    assert variables.validate_new_variables(updates_bad_name) is False

    # Known name but wrong component count
    updates_bad_components = [
        FakeUpdate(name="PVar", num_components=2, type=VisorVtkVariableType.POINT),
    ]
    assert variables.validate_new_variables(updates_bad_components) is False

    # Mixed: one valid, one invalid should be False
    updates_mixed = [
        FakeUpdate(name="PVar", num_components=1, type=VisorVtkVariableType.POINT),
        FakeUpdate(name="CVar", num_components=2, type=VisorVtkVariableType.CELL),
    ]
    assert variables.validate_new_variables(updates_mixed) is False


def test_init_raises_on_none_dataset():
    """Verify that VisorVariables raises ValueError if initialized with None."""
    with pytest.raises(ValueError):
        tvmod.VisorVariables(None)


def test_init_with_composite_dataset_does_not_raise(monkeypatch):
    """VisorVariables no longer guards against composite datasets.
    Composite traversal is handled at the VisorDataset level; VisorVariables
    is always constructed with a single leaf block and just reads point/cell data."""
    p = FakeDataArray("P", 1, 1, [(0.0, 1.0)], (0.0, 1.0))
    ds = FakeDataset(point_arrays=[p], cell_arrays=[])

    # Should not raise — VisorVariables now reads whatever dataset it is given
    tv = tvmod.VisorVariables(ds)
    assert len(tv.list()) == 1
