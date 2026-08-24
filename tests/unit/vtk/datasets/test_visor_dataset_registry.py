# python
from unittest.mock import MagicMock

import pytest

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
