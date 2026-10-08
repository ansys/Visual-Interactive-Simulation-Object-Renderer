from unittest.mock import patch

from ansys.visor.viewer.models.common.part_properties import PartProperties
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import (
    RuntimeDatasetState,
    RuntimePartProperties,
    VariableReference,
)


def _record(part_id, **overrides):
    """A complete record for *part_id* with *overrides* applied."""
    return RuntimePartProperties.default_for(part_id).model_copy(update=overrides)


def test_parts_accepts_partproperties_instances():
    """Validate that RuntimeDatasetState.part_states accepts RuntimePartProperties instances."""
    p = _record(123, opacity=0.75)
    ds = RuntimeDatasetState(id=345, part_states={10: p})
    assert 10 in ds.part_states
    assert isinstance(ds.part_states[10], RuntimePartProperties)
    assert ds.part_states[10].opacity == 0.75

def test_parts_key_types_preserved():
    """Validate that RuntimeDatasetState.part_states preserves key types."""
    # ensure that integer keys remain integers (pydantic won't coerce dict keys automatically)
    ds = RuntimeDatasetState(id=345, part_states={1: _record(123, opacity=1.0)})
    keys = list(ds.part_states.keys())
    assert all(isinstance(k, int) for k in keys)


# --- Serialization: undefined-vs-null contract ---

def test_variable_id_null_always_serialized():
    """variable_id=None must appear in the output as null (not be omitted).

    Frontend distinguishes null ("remove variable") from absent ("pass-through").
    The wire format uses the camelCase alias ``variableId``.
    """
    p = _record(1, color_variable=None)
    data = p.model_dump(by_alias=True)
    assert "variableId" in data
    assert data["variableId"] is None


def test_variable_id_value_serialized():
    """variable_id with a real value must be present."""
    p = _record(1, color_variable=VariableReference(variable_id="pressure", variable_component=0))
    data = p.model_dump(by_alias=True)
    assert data["variableId"] == "pressure"


def test_optional_fields_present_when_set():
    """Optional fields must appear when they carry an actual value."""
    p = _record(
        1, opacity=0.5, visible=True, selected=False,
        color_variable=VariableReference(variable_id="pressure", variable_component=2),
        diffuse_rgb=[0.1, 0.2, 0.3],
    )
    data = p.model_dump(by_alias=True)
    assert data["opacity"] == 0.5
    assert data["visible"] is True
    assert data["selected"] is False
    assert data["variableComponent"] == 2
    assert data["diffuseRgb"] == [0.1, 0.2, 0.3]


def test_clear_variable_round_trip():
    """A part with variable_id=None serializes correctly and round-trips through PartProperties."""
    from ansys.visor.viewer.models.common.part_properties import PartProperties

    props = PartProperties(color_by=None)
    p = RuntimePartProperties.from_part_properties(id=42, props=props)
    data = p.model_dump(by_alias=True)

    # variableId must be present and null so the frontend removes the variable
    assert "variableId" in data
    assert data["variableId"] is None

    # Round-trip back to PartProperties
    back = p.to_part_properties()
    assert back.color_by is None


def test_diffuse_rgb_round_trip():
    """A part with diffuse RGB values should serialize and round-trip through PartProperties."""
    from ansys.visor.viewer.models.common.part_properties import PartProperties

    orig = [0.4, 0.5, 0.6]
    props = PartProperties(diffuse_rgb=orig)
    p = RuntimePartProperties.from_part_properties(id=99, props=props)
    data = p.model_dump(by_alias=True)

    # diffuseRgb must be present when set
    assert "diffuseRgb" in data
    assert data["diffuseRgb"] == orig

    # Round-trip back to PartProperties
    back = p.to_part_properties()
    assert back.diffuse_rgb == orig


# --- Resolution: a record never holds None ---

def test_default_for_yields_a_record_with_every_field_set():
    """The default record carries the part's id and the four literals, and no variable."""
    p = RuntimePartProperties.default_for(7)

    assert p.id == 7
    assert p.visible is True
    assert p.opacity == 1.0
    assert p.selected is False
    assert p.diffuse_rgb == [0.8, 0.8, 0.8]
    assert p.color_variable is None


def test_from_part_properties_resolves_each_null_to_its_literal():
    """A persisted entry with every field null resolves to the literals."""
    p = RuntimePartProperties.from_part_properties(id=5, props=PartProperties())

    assert p.visible is True
    assert p.opacity == 1.0
    assert p.selected is False
    assert p.diffuse_rgb == [0.8, 0.8, 0.8]


def test_from_part_properties_resolves_a_short_colour_to_the_default():
    """A persisted colour that is not three elements resolves as a null does, with one WARNING."""
    with patch(
        "ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state.logger"
    ) as mock_logger:
        p = RuntimePartProperties.from_part_properties(id=5, props=PartProperties(diffuse_rgb=[1.0, 0.0]))

    assert mock_logger.warning.call_count == 1
    assert p.diffuse_rgb == [0.8, 0.8, 0.8]


def test_color_variable_round_trips_through_color_by():
    """color_by / color_by_component map to the reference, and the reference maps back."""
    props = PartProperties(color_by="POINT::pressure::1", color_by_component=2)

    p = RuntimePartProperties.from_part_properties(id=5, props=props)
    assert p.color_variable == VariableReference(variable_id="POINT::pressure::1", variable_component=2)

    back = p.to_part_properties()
    assert back.color_by == "POINT::pressure::1"
    assert back.color_by_component == 2

