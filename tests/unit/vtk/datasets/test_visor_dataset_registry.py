# python
from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import (
    RuntimeDatasetState,
    RuntimePartProperties,
)
from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry


@pytest.fixture
def registry():
    """Provide an empty VisorDatasetRegistry instance."""
    return VisorDatasetRegistry()


def make_mock_dataset(name="ds", info_dict=None, parts=None, variables=None):
    """Helper function to create a mock dataset with specified attributes."""
    mock = MagicMock()
    mock.name = name
    mock.info_dict = info_dict if info_dict is not None else {"info": name}
    mock.state = MagicMock()
    mock.state.parts = parts if parts is not None else {}
    mock.list_variables.return_value = variables if variables is not None else []
    return mock


def make_part_dataset(dataset_id, part_ids, part_states=None):
    """
    Build a dataset stand-in with a real PartIndex.part_ids list and a real
    RuntimeDatasetState (not MagicMock), so the per-part write path can
    mutate and be read back through actual object identity.
    """
    dataset = MagicMock()
    dataset.part_index = MagicMock()
    dataset.part_index.part_ids = list(part_ids)
    dataset.state = RuntimeDatasetState(id=dataset_id, part_states=part_states or {})
    return dataset


def test_count_returns_number_of_datasets(registry):
    """Verify that count returns the number of registered datasets."""
    assert registry.count == 0
    registry.datasets = {1: make_mock_dataset(), 2: make_mock_dataset()}
    assert registry.count == 2


def test_list_state_info_maps_ids_to_state_info(registry):
    """Verify that dataset IDs are mapped to their state information."""
    ds1 = make_mock_dataset(info_dict={"a": 1})
    ds2 = make_mock_dataset(info_dict={"b": 2})
    registry.datasets = {10: ds1, 20: ds2}

    info = registry.list_info()
    assert info == {10: {"a": 1}, 20: {"b": 2}}


def test_add_registers_dataset_and_returns_id(monkeypatch, registry):
    """Verify that adding a dataset registers it and returns its ID."""
    # Patch VisorDataset where it is referenced by the registry
    created = {}

    class FakeDataset:
        def __init__(self, dataset_id, dataset_name, input, part_name_to_id, metadata):
            created["args"] = (dataset_id, dataset_name, input, part_name_to_id, metadata)
            self.name = dataset_name
            self.state = MagicMock()
            self.state.parts = {}
            self.info_dict = {"id": dataset_id}
            self.list_variables = MagicMock(return_value=[])
            self.update_variables = MagicMock()

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.datasets.visor_dataset_registry.VisorDataset",
        FakeDataset,
    )

    mock_input = MagicMock()
    mock_metadata = MagicMock()
    mock_metadata.unit = "mm"

    ret = registry.add(5, "test_dataset", mock_input, {}, mock_metadata)

    assert isinstance(ret, FakeDataset)
    assert 5 in registry.datasets
    assert created["args"] == (5, "test_dataset", mock_input, {}, mock_metadata)
    assert registry.unit == "mm"  # verify _update_unit was called


def test_remove_deletes_dataset_if_present(registry):
    """Verify that removing a dataset deletes it from the registry."""
    ds = make_mock_dataset()
    registry.datasets = {7: ds}
    registry.remove(7)
    assert registry.datasets == {}

    registry.remove(99)  # should be a no-op
    assert registry.datasets == {}


def test_get_sanitized_metadata_name_unique(registry):
    """Verify that unique dataset names are returned unchanged."""
    metadata = MagicMock()
    metadata.name = "unique"
    new_name = registry.get_sanitized_metadata_name(metadata)
    assert new_name == "unique"


def test_get_sanitized_metadata_name_duplicate_warns_and_renames(registry):
    """Verify that duplicate dataset names are renamed to remain unique."""
    ds_existing = make_mock_dataset(name="data")
    registry.datasets = {1: ds_existing}

    metadata = MagicMock()
    metadata.name = "data"

    new_name = registry.get_sanitized_metadata_name(metadata)

    assert new_name.startswith("data_")
    assert new_name != "data"


def test_get_sanitized_metadata_name_none_raises(registry):
    """Verify that a missing metadata object raises a ValueError."""
    with pytest.raises(ValueError):
        registry.get_sanitized_metadata_name(None)


def test_clear_resets_datasets_and_unit(registry):
    """Verify that clear removes all datasets and resets the unit."""
    registry.datasets = {1: make_mock_dataset()}
    registry.unit = "m"
    registry.clear()
    assert registry.datasets == {}
    assert registry.unit == ""


def test_list_variables_returns_from_dataset(registry):
    """Verify that variable names are returned from the requested dataset."""
    ds = make_mock_dataset(variables=["v1", "v2"])
    registry.datasets = {42: ds}
    vars_ = registry.list_variables(42)
    assert vars_ == ["v1", "v2"]
    ds.list_variables.assert_called_once()


def test_list_variables_missing_raises(registry):
    """Verify that requesting variables for an unknown dataset raises an error."""
    with pytest.raises(ValueError):
        registry.list_variables(999)


def test_update_variables_calls_dataset_method(registry):
    """Verify that variable updates are forwarded to the dataset."""
    ds = make_mock_dataset()
    registry.datasets = {11: ds}
    updates = [MagicMock(), MagicMock()]
    registry.update_variables(11, updates)
    ds.update_variables.assert_called_once_with(updates)


def test_update_variables_missing_raises(registry):
    """Verify that updating variables on an unknown dataset raises an error."""
    with pytest.raises(ValueError):
        registry.update_variables(123, [MagicMock()])


def test_update_unit_sets_on_first_add(registry):
    """Verify that the registry unit is initialized from the first dataset."""
    metadata = MagicMock()
    metadata.unit = "mm"
    registry._update_unit(metadata)
    assert registry.unit == "mm"


def test_update_unit_mismatch_warns_and_resets(registry):
    """Verify that a unit mismatch triggers the registry's mismatch handling."""
    registry.datasets = {1: make_mock_dataset()}
    registry.unit = "m"

    metadata = MagicMock()
    metadata.unit = "s"

    registry._update_unit(metadata)

    assert registry.unit == ""


def test_update_unit_matches_keeps_unit(registry):
    """Verify that matching dataset units leave the registry unit unchanged."""
    registry.datasets = {1: make_mock_dataset()}
    registry.unit = "m"
    metadata = MagicMock()
    metadata.unit = "m"

    registry._update_unit(metadata)
    assert registry.unit == "m"


# ================================================================== #
# Per-part write path
# ================================================================== #

def test_find_dataset_id_for_part_selects_between_multiple_datasets(registry):
    """Verify the correct dataset id is returned when several datasets are registered."""
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10, 11])
    ds_b = make_part_dataset(dataset_id=2, part_ids=[20, 21])
    registry.datasets = {1: ds_a, 2: ds_b}

    assert registry.find_dataset_id_for_part(20) == 2
    assert registry.find_dataset_id_for_part(11) == 1


def test_find_dataset_id_for_part_not_found_returns_none(registry):
    """Verify an unknown part_id resolves to no dataset."""
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10, 11])
    registry.datasets = {1: ds_a}

    assert registry.find_dataset_id_for_part(999999) is None


def test_get_part_state_returns_existing_record(registry):
    """Verify get_part_state returns the recorded state for a known part."""
    existing = RuntimePartProperties(id=10, opacity=0.7)
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10], part_states={10: existing})
    registry.datasets = {1: ds_a}

    result = registry.get_part_state(10)
    assert result is existing
    assert result.opacity == 0.7


def test_get_part_state_known_dataset_missing_part_returns_none(registry):
    """Verify get_part_state does not upsert: a part with no record returns None."""
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10])
    registry.datasets = {1: ds_a}

    assert registry.get_part_state(10) is None
    assert ds_a.state.part_states == {}


def test_get_part_state_unknown_part_id_returns_none(registry):
    """Verify get_part_state returns None, without raising, for an unknown part_id."""
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10])
    registry.datasets = {1: ds_a}

    assert registry.get_part_state(999999) is None


def test_set_part_visibility_mutates_record_and_rejects_unknown_part(registry):
    """Verify set_part_visibility writes True/False, and False + no raise for unknown part_id."""
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10], part_states={10: RuntimePartProperties(id=10)})
    registry.datasets = {1: ds_a}

    assert registry.set_part_visibility(10, False) is True
    assert registry.get_part_state(10).visible is False

    assert registry.set_part_visibility(999999, True) is False


def test_set_part_opacity_mutates_record_and_rejects_unknown_part(registry):
    """Verify set_part_opacity writes the value, and False + no raise for unknown part_id."""
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10], part_states={10: RuntimePartProperties(id=10)})
    registry.datasets = {1: ds_a}

    assert registry.set_part_opacity(10, 0.4) is True
    assert registry.get_part_state(10).opacity == 0.4

    assert registry.set_part_opacity(999999, 0.4) is False


def test_set_part_diffuse_color_mutates_and_clears(registry):
    """Verify set_part_diffuse_color writes an RGB list, clears with None, and rejects unknown parts."""
    ds_a = make_part_dataset(
        dataset_id=1, part_ids=[10],
        part_states={10: RuntimePartProperties(id=10, diffuse_rgb=[1.0, 0.0, 0.0])},
    )
    registry.datasets = {1: ds_a}

    assert registry.set_part_diffuse_color(10, [0.0, 1.0, 0.0]) is True
    assert registry.get_part_state(10).diffuse_rgb == [0.0, 1.0, 0.0]

    assert registry.set_part_diffuse_color(10, None) is True
    assert registry.get_part_state(10).diffuse_rgb is None

    assert registry.set_part_diffuse_color(999999, [1.0, 1.0, 1.0]) is False


def test_set_part_selected_mutates_record_and_rejects_unknown_part(registry):
    """Verify set_part_selected writes the value, and False + no raise for unknown part_id."""
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10], part_states={10: RuntimePartProperties(id=10)})
    registry.datasets = {1: ds_a}

    assert registry.set_part_selected(10, True) is True
    assert registry.get_part_state(10).selected is True

    assert registry.set_part_selected(999999, True) is False


def test_set_part_color_variable_sets_id_and_component_together(registry):
    """Verify set_part_color_variable sets spectrum_id and spectrum_component in one call."""
    seed = RuntimePartProperties(id=10)
    assert seed.spectrum_id is None
    assert seed.spectrum_component is None
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10], part_states={10: seed})
    registry.datasets = {1: ds_a}

    assert registry.set_part_color_variable(10, "POINT::pressure::1", 2) is True

    result = registry.get_part_state(10)
    assert result.spectrum_id == "POINT::pressure::1"
    assert result.spectrum_component == 2

    assert registry.set_part_color_variable(999999, "POINT::x::1", 0) is False


def test_clear_part_color_variable_clears_id_and_component_together(registry):
    """Verify clear_part_color_variable clears spectrum_id and spectrum_component in one call."""
    seed = RuntimePartProperties(id=10, spectrum_id="POINT::pressure::1", spectrum_component=2)
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10], part_states={10: seed})
    registry.datasets = {1: ds_a}

    assert registry.clear_part_color_variable(10) is True

    result = registry.get_part_state(10)
    assert result.spectrum_id is None
    assert result.spectrum_component is None

    assert registry.clear_part_color_variable(999999) is False


def test_setter_upserts_part_state_when_part_id_known_but_absent_from_part_states(registry):
    """
    Verify the upsert path: a part_id present in PartIndex.part_ids but absent
    from part_states gets a RuntimePartProperties(id=part_id) created on first
    write, rather than silently no-op-ing.
    """
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10], part_states={})
    registry.datasets = {1: ds_a}
    assert ds_a.state.part_states == {}

    assert registry.set_part_opacity(10, 0.6) is True

    created = ds_a.state.part_states.get(10)
    assert created is not None
    assert isinstance(created, RuntimePartProperties)
    assert created.id == 10
    assert created.opacity == 0.6


def test_replace_part_states_replaces_known_and_skips_unknown_without_aborting(registry):
    """
    Verify replace_part_states replaces the state of a known dataset id and
    silently skips an unknown dataset id in the same call, without aborting
    partway (the known replacement still lands).
    """
    ds_a = make_part_dataset(dataset_id=1, part_ids=[10])
    original_state = ds_a.state
    registry.datasets = {1: ds_a}

    new_state_for_known = RuntimeDatasetState(id=1, part_states={10: RuntimePartProperties(id=10, opacity=0.9)})
    new_state_for_unknown = RuntimeDatasetState(id=999, part_states={})

    registry.replace_part_states({1: new_state_for_known, 999: new_state_for_unknown})

    assert ds_a.state is new_state_for_known
    assert ds_a.state is not original_state
    assert 999 not in registry.datasets


