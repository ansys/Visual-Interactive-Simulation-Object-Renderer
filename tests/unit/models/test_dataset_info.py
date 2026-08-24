import pytest

from ansys.visor.viewer.models.info.visor_dataset_info import VisorDatasetInfo


def test_basic_construction_and_fields():
    """Validate basic construction and fields."""
    ds = VisorDatasetInfo(id=1, name="Dataset 1", unit="mm")
    assert ds.id == 1
    assert ds.name == "Dataset 1"
    assert ds.unit == "mm"
    assert ds.file_path is None
    assert ds.metadata_path is None

def test_missing_required_fields_raises():
    """Validate that missing required fields raises Exception."""
    # missing required fields should raise a validation error
    with pytest.raises(Exception):
        VisorDatasetInfo(name="no id", unit="mm")
    with pytest.raises(Exception):
        VisorDatasetInfo(id=10, unit="mm")
    with pytest.raises(Exception):
        VisorDatasetInfo(id=11, name="no unit")

def test_optional_file_paths_can_be_set():
    """Validate that optional file paths can be set."""
    ds = VisorDatasetInfo(id=5, name="WithPaths", unit="mm", file_path="/tmp/data.vtm", metadata_path="/tmp/data.json")
    assert ds.file_path == "/tmp/data.vtm"
    assert ds.metadata_path == "/tmp/data.json"

