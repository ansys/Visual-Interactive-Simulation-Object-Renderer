"""Tests for the server-owned variable record (3.5.1 increment 1, tests 1-4).

Every expected value is a hand-written literal.
"""
import pytest
from pydantic import ValidationError

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_variable_record import (
    VisorVariableRecord,
    compose_variable_identifier,
)
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.scene.persisted_scene_state import (
    derive_variable_fields_from_identifier,
)


def _record_kwargs():
    return dict(
        id="CELL::temperature::1",
        array_name="temperature",
        type=VisorVtkVariableType.CELL,
        num_components=1,
        part_ids=[3, 5],
        default_magnitude_range=(-1.0, 7.0),
        default_ranges=[(-1.0, 7.0)],
        magnitude_range=(0.5, 6.5),
        ranges=[(0.5, 6.5)],
    )


def test_record_rejects_a_missing_default_magnitude_range():
    """#1: every field is required; a record without its default range does not validate."""
    kwargs = _record_kwargs()
    del kwargs["default_magnitude_range"]

    with pytest.raises(ValidationError) as excinfo:
        VisorVariableRecord(**kwargs)

    assert {error["loc"][-1] for error in excinfo.value.errors()} == {"defaultMagnitudeRange"}


def test_record_type_dumps_as_its_wire_value():
    """#2: the enum serializes as "CELL", in both dict and JSON dumps, under every alias."""
    record = VisorVariableRecord(**_record_kwargs())

    assert record.model_dump(by_alias=True) == {
        "id": "CELL::temperature::1",
        "arrayName": "temperature",
        "type": "CELL",
        "numComponents": 1,
        "partIds": [3, 5],
        "defaultMagnitudeRange": (-1.0, 7.0),
        "defaultRanges": [(-1.0, 7.0)],
        "magnitudeRange": (0.5, 6.5),
        "ranges": [(0.5, 6.5)],
    }
    assert '"type":"CELL"' in record.model_dump_json(by_alias=True)


def test_to_variable_state_projects_identity_and_the_effective_ranges():
    """#3: the persisted projection keeps identity and custom ranges, and drops the rest."""
    projected = VisorVariableRecord(**_record_kwargs()).to_variable_state()

    assert isinstance(projected, VisorVariableState)
    assert projected.model_dump(by_alias=True) == {
        "id": "CELL::temperature::1",
        "arrayName": "temperature",
        "type": "CELL",
        "numComponents": 1,
        "magnitudeRange": (0.5, 6.5),
        "ranges": [(0.5, 6.5)],
    }


def test_compose_variable_identifier_is_the_inverse_of_derive():
    """#4: composes the hand-written literal id, which derive splits back into its fields."""
    identifier = compose_variable_identifier(VisorVtkVariableType.POINT, "pressure", 1)

    assert identifier == "POINT::pressure::1"
    assert derive_variable_fields_from_identifier("POINT::pressure::1") == {
        "type": "POINT",
        "array_name": "pressure",
        "num_components": 1,
    }

