import pytest
from pydantic import ValidationError

from ansys.visor.viewer.api.models import Info, InitProps, RemoveDatasetProps, StartProps, UpdateProps
from ansys.visor.viewer.core.metadata import Metadata


def test_info_model_valid():
    """Verify that an Info model is created successfully with valid values."""
    info = Info(
        app_name="visor",
        host="localhost",
        port=8080,
        standalone=True,
        datasets=["file1.vtk", "file2.vtk"]
    )
    assert info.app_name == "visor"
    assert info.host == "localhost"
    assert info.port == 8080
    assert info.standalone is True
    assert info.datasets == ["file1.vtk", "file2.vtk"]

def test_info_model_missing_fields():
    """Verify that creating an Info model without required fields raises a ValidationError."""
    with pytest.raises(ValidationError):
        Info(host="localhost", port=8080, standalone=True, datasets=[])

def test_initprops_valid_host():
    """Test that initprops valid host."""
    props = InitProps(host="localhost", port=8081)
    assert props.host == "localhost"
    assert props.port == 8081

def test_initprops_port_defaults_to_zero():
    """Port must default to 0 (sentinel for server-side selection)."""
    props = InitProps(host="localhost")
    assert props.port == 0

def test_initprops_invalid_host():
    """Verify that InitProps raises a ValidationError for an invalid host."""
    with pytest.raises(ValidationError):
        InitProps(host="bad host!", port=8081)

def test_startprops_all_fields():
    """Verify that StartProps stores all provided field values."""
    meta = Metadata(name="foo", unit="m")
    props = StartProps(file_path="file.vtk", metadata=meta, timeout=10)
    assert props.file_path == "file.vtk"
    assert props.metadata == meta
    assert props.timeout == 10

def test_startprops_metadata_as_str():
    """Verify that StartProps accepts metadata as a string path."""
    props = StartProps(file_path="file.vtk", metadata="meta.json", timeout=5)
    assert props.metadata == "meta.json"

def test_startprops_defaults():
    """Verify that StartProps uses the expected default values when no arguments are provided."""
    props = StartProps()
    assert props.file_path is None
    assert props.metadata is None
    assert props.timeout == 0

def test_updateprops_valid():
    """Verify that UpdateProps is created successfully with valid values."""
    meta = Metadata(name="bar", unit="cm")
    props = UpdateProps(file_path="updated.vtk", metadata=meta)
    assert props.file_path == "updated.vtk"
    assert props.metadata == meta

def test_updateprops_metadata_as_str():
    """Verify that UpdateProps accepts metadata as a string path."""
    props = UpdateProps(file_path="updated.vtk", metadata="meta.json")
    assert props.metadata == "meta.json"

def test_updateprops_missing_file_path():
    """Verify that UpdateProps raises a ValidationError when file_path is missing."""
    with pytest.raises(ValidationError):
        UpdateProps(metadata="meta.json")

def test_removedatasetprops_valid():
    """Verify that RemoveDatasetProps accepts a valid dataset identifier."""
    props = RemoveDatasetProps(dataset_id=12345)
    assert props.dataset_id == 12345

def test_removedatasetprops_invalid_type():
    """Verify that RemoveDatasetProps raises a ValidationError for a non-integer dataset identifier."""
    with pytest.raises(ValidationError):
        RemoveDatasetProps(dataset_id="not_an_int")
