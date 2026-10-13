"""Tests for the pure variable aggregate (3.5.1 increment 1, tests 5-9).

The registry is a hand-written fake; every expected value is a hand-written
literal, never recomputed the way the code computes it.
"""
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_variable_record import VisorVariableRecords
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variables import VisorVariable

POINT = VisorVtkVariableType.POINT


def _var(name, ranges, magnitude, point_type=POINT):
    return VisorVariable(
        index=0, type=point_type, name=name, num_components=len(ranges),
        num_points=4, ranges=list(ranges), magnitude_range=magnitude,
    )


class _FakeDataset:
    def __init__(self, parts):
        self._parts = parts

    def list_variables(self):
        return [
            VisorPartVariables(part_id=part_id, part_name=f"p{part_id}", variables=variables)
            for part_id, variables in self._parts.items()
        ]


class _FakeRegistry:
    def __init__(self, *datasets):
        self.datasets = {i + 1: d for i, d in enumerate(datasets)}


def _two_datasets_sharing_pressure():
    return _FakeRegistry(
        _FakeDataset({1: [_var("pressure", [(0.0, 10.0)], (0.0, 10.0))]}),
        _FakeDataset({3: [_var("pressure", [(-5.0, 4.0)], (-5.0, 4.0))]}),
    )


def test_participation_is_the_union_of_parts_across_datasets():
    """#5: one record for the shared variable, naming both parts."""
    records = VisorVariableRecords.from_registry(_two_datasets_sharing_pressure(), VisorVariableRecords()).variables

    assert list(records) == ["POINT::pressure::1"]
    assert records["POINT::pressure::1"].part_ids == [1, 3]


def test_default_ranges_widen_to_the_min_of_mins_and_max_of_maxes():
    """#6: (0.0, 10.0) and (-5.0, 4.0) widen to (-5.0, 10.0); a new id's custom equals its default."""
    record = VisorVariableRecords.from_registry(
        _two_datasets_sharing_pressure(), VisorVariableRecords()).variables["POINT::pressure::1"]

    assert record.default_magnitude_range == (-5.0, 10.0)
    assert record.default_ranges == [(-5.0, 10.0)]
    assert record.magnitude_range == (-5.0, 10.0)
    assert record.ranges == [(-5.0, 10.0)]


def test_a_width_split_produces_distinct_ids():
    """#7: same name and association at widths 3 and 1 are two records, one part each."""
    registry = _FakeRegistry(
        _FakeDataset({
            1: [_var("velocity", [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)], (0.0, 4.0))],
            2: [_var("velocity", [(5.0, 6.0)], (5.0, 6.0))],
        })
    )

    records = VisorVariableRecords.from_registry(registry, VisorVariableRecords()).variables

    assert sorted(records) == ["POINT::velocity::1", "POINT::velocity::3"]
    assert records["POINT::velocity::3"].part_ids == [1]
    assert records["POINT::velocity::3"].default_ranges == [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
    assert records["POINT::velocity::1"].part_ids == [2]


def _one_dataset_pressure():
    return _FakeRegistry(_FakeDataset({1: [_var("pressure", [(0.0, 10.0)], (0.0, 10.0))]}))


def test_an_edited_custom_range_is_kept_across_widening():
    """#8: a custom slot that differs from its previous default survives the rebuild."""
    previous = VisorVariableRecords.from_registry(_one_dataset_pressure(), VisorVariableRecords()).variables
    previous["POINT::pressure::1"] = previous["POINT::pressure::1"].model_copy(
        update={"magnitude_range": (2.0, 3.0), "ranges": [(2.0, 3.0)]}
    )

    record = VisorVariableRecords.from_registry(
        _two_datasets_sharing_pressure(), VisorVariableRecords(variables=previous)).variables["POINT::pressure::1"]

    assert record.default_magnitude_range == (-5.0, 10.0)
    assert record.magnitude_range == (2.0, 3.0)
    assert record.ranges == [(2.0, 3.0)]


def test_an_unedited_custom_range_follows_the_new_default():
    """#9: a custom slot equal to its previous default (0.0, 10.0) follows the widening to (-5.0, 10.0)."""
    previous = VisorVariableRecords.from_registry(_one_dataset_pressure(), VisorVariableRecords()).variables
    assert previous["POINT::pressure::1"].magnitude_range == (0.0, 10.0)

    record = VisorVariableRecords.from_registry(
        _two_datasets_sharing_pressure(), VisorVariableRecords(variables=previous)).variables["POINT::pressure::1"]

    assert record.magnitude_range == (-5.0, 10.0)
    assert record.ranges == [(-5.0, 10.0)]

