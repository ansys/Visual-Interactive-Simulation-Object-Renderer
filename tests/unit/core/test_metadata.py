import pytest
from pydantic import ValidationError

from ansys.visor.viewer.core.metadata import ExtendedMetadata, Metadata
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState


class DummyVisorState(PersistedDatasetState):
    pass

def test_metadata_valid_construction():
    """Verify that Metadata stores the provided values."""
    state = DummyVisorState(parts={})
    m = Metadata(name="foo", unit="m", state=state)
    assert m.name == "foo"
    assert m.unit == "m"
    assert m.state == state

def test_metadata_state_dict_conversion():
    """Verify that a state dictionary is converted to PersistedDatasetState."""
    state_dict = {"parts": {}}
    m = Metadata(name="foo", unit="m", state=state_dict)
    assert isinstance(m.state, PersistedDatasetState)

def test_metadata_state_invalid_raises():
    """Verify that invalid state data raises a ValidationError."""
    # 'parts' is required and should be a dict, so passing a wrong type should fail
    with pytest.raises(ValidationError):
        Metadata(name="foo", unit="m", state={"parts": 123})

def test_metadata_defaults():
    """Verify that Metadata creates a default state when one is not provided."""
    m = Metadata(name="bar", unit="cm")
    assert isinstance(m.state, PersistedDatasetState)

def test_metadata_repr_and_eq():
    """Verify that Metadata supports repr generation and equality comparison."""
    state = DummyVisorState(parts={})
    m1 = Metadata(name="foo", unit="m", state=state)
    m2 = Metadata(name="foo", unit="m", state=state)
    assert repr(m1)
    assert m1 == m2

def test_extended_metadata_valid_construction():
    """Verify that ExtendedMetadata stores all provided values."""
    state = DummyVisorState(parts={})
    ext = ExtendedMetadata(
        name="foo",
        unit="m",
        state=state,
        file_path="file.txt",
        metadata_path="meta.json"
    )
    assert ext.name == "foo"
    assert ext.unit == "m"
    assert ext.state == state
    assert ext.file_path == "file.txt"
    assert ext.metadata_path == "meta.json"

def test_extended_metadata_defaults():
    """Verify that ExtendedMetadata applies the expected default values."""
    ext = ExtendedMetadata(name="bar", unit="cm")
    assert ext.file_path is None
    assert ext.metadata_path is None
    assert isinstance(ext.state, PersistedDatasetState)

def test_extended_metadata_state_dict_conversion():
    """Verify that a state dictionary is converted to PersistedDatasetState."""
    state_dict = {"parts": {}}
    ext = ExtendedMetadata(name="foo", unit="m", state=state_dict)
    assert isinstance(ext.state, PersistedDatasetState)

def test_extended_metadata_state_invalid_raises():
    """Verify that invalid state data raises a ValidationError."""
    with pytest.raises(ValidationError):
        ExtendedMetadata(name="foo", unit="m", state={"parts": 123})

def test_extended_metadata_repr_and_eq():
    """Verify that ExtendedMetadata supports repr generation and equality comparison."""
    state = DummyVisorState(parts={})
    ext1 = ExtendedMetadata(name="foo", unit="m", state=state, file_path="a", metadata_path="b")
    ext2 = ExtendedMetadata(name="foo", unit="m", state=state, file_path="a", metadata_path="b")
    assert repr(ext1)
    assert ext1 == ext2
