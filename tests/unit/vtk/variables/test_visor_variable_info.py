# python
import json

import pytest
from pydantic import ValidationError

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.info.visor_variable_info import VisorVariableInfo


def _valid_payload():
    return {
        "indexForType": 0,
        "type": "POINT",
        "name": "velocity",
        "numComponents": 3,
        "ranges": [(0.0, 1.0), (1.0, 2.0), (2.0, 5.0)],
        "magnitudeRange": (0.0, 5.0),
    }


def test_create_with_all_fields():
    """Verify that a VisorVariableInfo can be created with all fields."""
    m = VisorVariableInfo(**_valid_payload())
    assert (m.index_for_type, m.type, m.name, m.num_components) == (
        0, VisorVtkVariableType.POINT, "velocity", 3
    )
    assert m.ranges == [(0.0, 1.0), (1.0, 2.0), (2.0, 5.0)]
    assert m.magnitude_range == (0.0, 5.0)


def test_optional_field_defaults_to_none():
    """Verify that optional field magnitudeRange defaults to None if not provided."""
    data = _valid_payload()
    data.pop("magnitudeRange")
    m = VisorVariableInfo(**data)
    assert m.magnitude_range is None


@pytest.mark.parametrize(
    "bad_ranges",
    [
        [1.0, 2.0],              # not a list of 2-tuples
        [(1.0, 2.0, 3.0)],       # wrong tuple length
        [(None, 1.0)],           # wrong element type
    ],
)
def test_invalid_ranges_raise_validation_error(bad_ranges):
    """Verify that invalid ranges raise validation error."""
    data = _valid_payload()
    data["ranges"] = bad_ranges
    with pytest.raises(ValidationError):
        VisorVariableInfo(**data)


@pytest.mark.parametrize(
    "bad_magnitude",
    [
        (1.0,),          # wrong length
        "bad",           # wrong type
    ],
)
def test_invalid_magnitude_range_raises_validation_error(bad_magnitude):
    """Verify that invalid magnitudeRange raises validation error."""
    data = _valid_payload()
    data["magnitudeRange"] = bad_magnitude
    with pytest.raises(ValidationError):
        VisorVariableInfo(**data)


def test_model_dump_json_shape():
    """Verify that model_dump_json produces expected JSON shape."""
    m = VisorVariableInfo(**_valid_payload())
    back = json.loads(m.model_dump_json(by_alias=True))
    assert back["ranges"] == [[0.0, 1.0], [1.0, 2.0], [2.0, 5.0]]
    assert back["magnitudeRange"] == [0.0, 5.0]
