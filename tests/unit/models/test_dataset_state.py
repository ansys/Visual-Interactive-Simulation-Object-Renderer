from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimeDatasetState, RuntimePartProperties


def test_parts_accepts_partproperties_instances():
    """Validate that RuntimeDatasetState.part_states accepts RuntimePartProperties instances."""
    p = RuntimePartProperties(id=123, opacity=0.75)
    ds = RuntimeDatasetState(id=345, part_states={10: p})
    assert 10 in ds.part_states
    assert isinstance(ds.part_states[10], RuntimePartProperties)
    assert ds.part_states[10].opacity == 0.75

def test_parts_key_types_preserved():
    """Validate that RuntimeDatasetState.part_states preserves key types."""
    # ensure that integer keys remain integers (pydantic won't coerce dict keys automatically)
    ds = RuntimeDatasetState(id=345, part_states={1: RuntimePartProperties(id=123, opacity=1.0)})
    keys = list(ds.part_states.keys())
    assert all(isinstance(k, int) for k in keys)


# --- Serialization: undefined-vs-null contract ---

def test_variable_id_null_always_serialized():
    """variable_id=None must appear in the output as null (not be omitted).

    Frontend distinguishes null ("remove variable") from absent ("pass-through").
    The wire format uses the camelCase alias ``variableId``.
    """
    p = RuntimePartProperties(id=1, variable_id=None)
    data = p.model_dump(by_alias=True)
    assert "variableId" in data
    assert data["variableId"] is None


def test_variable_id_value_serialized():
    """variable_id with a real value must be present."""
    p = RuntimePartProperties(id=1, variable_id="pressure")
    data = p.model_dump(by_alias=True)
    assert data["variableId"] == "pressure"


def test_optional_fields_omitted_when_none():
    """opacity, visible, selected, variableComponent, diffuseRgb must be omitted when None.

    The frontend interprets an absent key as undefined / pass-through.
    """
    p = RuntimePartProperties(id=1)  # all optional fields default to None
    data = p.model_dump(by_alias=True)
    for field in ("opacity", "visible", "selected", "variableComponent", "diffuseRgb"):
        assert field not in data, f"Expected '{field}' to be omitted when None, but it was present"


def test_optional_fields_present_when_set():
    """Optional fields must appear when they carry an actual value."""
    p = RuntimePartProperties(id=1, opacity=0.5, visible=True, selected=False, variable_component=2,
                              diffuse_rgb=[0.1, 0.2, 0.3])
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
