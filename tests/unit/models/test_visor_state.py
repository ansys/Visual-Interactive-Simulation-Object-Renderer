import pytest
from pydantic import ValidationError

from ansys.visor.viewer.models.common.part_properties import PartProperties
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimeDatasetState


def test_partproperties_valid_opacity():
    """Verify that PartProperties.opacity can be set correctly."""
    p = PartProperties(opacity=0.5)
    assert p.opacity == 0.5

def test_partproperties_none_opacity():
    """Verify that PartProperties.opacity can be None."""
    p = PartProperties()
    assert p.opacity is None

@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_partproperties_invalid_opacity(value):
    """Verify that PartProperties.opacity raises ValidationError for invalid values."""
    with pytest.raises(ValidationError):
        PartProperties(opacity=value)

def test_visorstate_empty_parts():
    """Verify that RuntimeDatasetState can be created with empty parts."""
    s = RuntimeDatasetState(id=1)
    assert s.part_states == {}

def test_visorstate_parts_with_partproperties():
    """Verify that RuntimeDatasetState can be created with PartProperties."""
    p = PartProperties(opacity=0.7)
    ds = RuntimeDatasetState.from_components(id=5, part_states={10: p})
    assert 10 in ds.part_states
    # The runtime representation should preserve the opacity value
    assert ds.part_states[10].opacity == 0.7
    # Ensure diffuse fields round-trip when present
    p2 = PartProperties(diffuse_rgb=[0.2, 0.3, 0.4])
    ds2 = RuntimeDatasetState.from_components(id=6, part_states={11: p2})
    assert ds2.part_states[11].diffuse_rgb == [0.2, 0.3, 0.4]
