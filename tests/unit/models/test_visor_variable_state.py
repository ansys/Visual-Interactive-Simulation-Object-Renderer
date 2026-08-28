"""Unit tests for VisorVariableState."""

import pytest
from pydantic import ValidationError

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState

_VALID_KWARGS = {
    "id": "POINT::displacement::3",
    "array_name": "displacement",
    "type": VisorVtkVariableType.POINT,
    "num_components": 3,
}


@pytest.mark.parametrize("missing_field", ["array_name", "type", "num_components"])
def test_construction_missing_required_field_raises(missing_field):
    """Omitting any one of array_name, type, or num_components must raise,
    proving each is required on its own rather than all three being
    collectively-but-not-individually required."""
    kwargs = {k: v for k, v in _VALID_KWARGS.items() if k != missing_field}

    with pytest.raises(ValidationError):
        VisorVariableState(**kwargs)

