"""Unit tests for the persisted-scene-state identity backfill.

Two things are under test:

* :func:`derive_variable_fields_from_identifier`, exercised directly against
  hand-written literal identifiers, and
* the ``variable_states`` before-validator, exercised through
  ``PersistedViewerStateV1.model_validate_json`` on literal 1.0-shaped
  documents.

Neither the parser's own separator constant nor any client-shaped helper is
imported or reused here: every identifier below is typed out by hand, so a test
cannot agree with the parser by construction.
"""

import json

import pytest
from pydantic import ValidationError

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.models.persist.scene.persisted_scene_state import (
    PersistedSceneState,
    derive_variable_fields_from_identifier,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _document(variable_states: dict, version: str = "1.0") -> str:
    """A save-file document in the 1.0 shape, as JSON text.

    Only the envelope is assembled here; every identifier and every entry is
    written out by hand at the call site.
    """
    return json.dumps({"version": version, "scene": {"variable_states": variable_states}})


def _entry(identifier: str) -> dict:
    """A variable-state entry as saved before the identity fields existed.

    ``id``, ``magnitudeRange`` and ``ranges`` are all a 1.0 entry ever carried.
    """
    return {
        "id": identifier,
        "magnitudeRange": [0.0, 1.0],
        "ranges": [[0.0, 1.0]],
    }


def _load(document: str) -> PersistedViewerStateV1:
    return PersistedViewerStateV1.model_validate_json(document)


def _load_one(identifier: str, entry: dict | None = None):
    """Load a one-entry 1.0 document keyed by *identifier* and return the parsed entry."""
    entry = _entry(identifier) if entry is None else entry
    return _load(_document({identifier: entry})).scene.variable_states[identifier]


# ------------------------------------------------------------------
# The derivation, tested directly against hand-written literals
# ------------------------------------------------------------------

def test_derives_the_three_fields_from_a_plain_identifier():
    """A plain identifier yields type, array name and component count."""
    assert derive_variable_fields_from_identifier("POINT::pressure::1") == {
        "type": "POINT",
        "array_name": "pressure",
        "num_components": 1,
    }


def test_derives_when_the_array_name_contains_the_separator():
    """Array names are user data and may contain the separator character.

    A left-to-right split on the separator would truncate ``stress::yy`` to
    ``stress``; splitting from the right by field count does not.
    """
    assert derive_variable_fields_from_identifier("POINT::stress::yy::3") == {
        "type": "POINT",
        "array_name": "stress::yy",
        "num_components": 3,
    }


def test_derives_when_the_array_name_contains_several_separators():
    """More than one embedded separator is still kept verbatim."""
    derived = derive_variable_fields_from_identifier("CELL::a::b::c::2")

    assert derived["array_name"] == "a::b::c"
    assert derived["type"] == "CELL"
    assert derived["num_components"] == 2


def test_same_array_name_different_component_counts_stay_distinct():
    """Two variables sharing an array name are told apart by component count."""
    scalar = derive_variable_fields_from_identifier("POINT::velocity::1")
    vector = derive_variable_fields_from_identifier("POINT::velocity::3")

    assert scalar["array_name"] == vector["array_name"] == "velocity"
    assert scalar["num_components"] == 1
    assert vector["num_components"] == 3
    assert scalar != vector


def test_cell_association_is_derived():
    """The type field is read from the identifier, not assumed to be POINT."""
    assert derive_variable_fields_from_identifier("CELL::volume::1")["type"] == "CELL"


@pytest.mark.parametrize("identifier", ["pressure", "POINT::pressure"])
def test_returns_none_when_the_identifier_has_too_few_parts(identifier):
    """Fewer than three fields cannot be derived, and are not guessed at."""
    assert derive_variable_fields_from_identifier(identifier) is None


def test_returns_none_when_the_component_count_is_not_an_integer():
    """A non-integer trailing field is refused rather than coerced."""
    assert derive_variable_fields_from_identifier("POINT::pressure::many") is None


@pytest.mark.parametrize("identifier", ["POINT::::1", "::pressure::1"])
def test_returns_none_when_a_field_is_structurally_present_but_empty(identifier):
    """Structural success is not semantic success.

    ``POINT::::1`` has three structural parts but an empty array name, and
    ``::pressure::1`` an empty type.  Filling either would produce a variable
    state naming something that cannot exist, which then fails silently
    downstream as an unresolvable-array no-op.  Both are refused so that the
    failure is a loud missing-field error instead.
    """
    assert derive_variable_fields_from_identifier(identifier) is None


# ------------------------------------------------------------------
# The fill, through literal 1.0-shaped documents
# ------------------------------------------------------------------

def test_v1_0_document_omitting_the_three_fields_parses_and_derives():
    """An old save file loads, and the absent fields are derived on ingest."""
    entry = _load_one("POINT::pressure::1")

    assert entry.array_name == "pressure"
    assert entry.type is VisorVtkVariableType.POINT
    assert entry.num_components == 1
    # The rest of the entry survives untouched.
    assert entry.magnitude_range == (0.0, 1.0)
    assert entry.ranges == [(0.0, 1.0)]


def test_v1_0_document_with_an_array_name_containing_the_separator_parses():
    """The embedded-separator case survives the whole ingest path, not just the split."""
    entry = _load_one("POINT::stress::yy::3")

    assert entry.array_name == "stress::yy"
    assert entry.num_components == 3


def test_v1_0_document_keeps_two_variables_sharing_an_array_name_distinct():
    """Two entries differing only in component count remain two entries."""
    document = _document(
        {
            "POINT::velocity::1": _entry("POINT::velocity::1"),
            "POINT::velocity::3": _entry("POINT::velocity::3"),
        }
    )

    variable_states = _load(document).scene.variable_states

    assert len(variable_states) == 2
    assert variable_states["POINT::velocity::1"].num_components == 1
    assert variable_states["POINT::velocity::3"].num_components == 3
    assert (
        variable_states["POINT::velocity::1"].array_name
        == variable_states["POINT::velocity::3"].array_name
        == "velocity"
    )


# ------------------------------------------------------------------
# What the fill must not do
# ------------------------------------------------------------------

def test_present_fields_are_not_overwritten_by_derivation():
    """An explicit value wins over anything the identifier would imply."""
    entry = _entry("POINT::pressure::1")
    entry["arrayName"] = "explicitly_named"
    entry["type"] = "CELL"
    entry["numComponents"] = 9

    stored = _load_one("POINT::pressure::1", entry)

    assert stored.array_name == "explicitly_named"
    assert stored.type is VisorVtkVariableType.CELL
    assert stored.num_components == 9


def test_camel_case_aliases_are_recognised_as_present():
    """A field supplied only under its wire alias is not treated as absent."""
    entry = _entry("POINT::pressure::1")
    entry["arrayName"] = "supplied_by_alias"

    stored = _load_one("POINT::pressure::1", entry)

    assert stored.array_name == "supplied_by_alias"
    # The two that really were absent are still derived.
    assert stored.type is VisorVtkVariableType.POINT
    assert stored.num_components == 1


def test_snake_case_names_are_recognised_as_present():
    """The same holds for the Python field names, since populate_by_name is set."""
    entry = _entry("POINT::pressure::1")
    entry["num_components"] = 7

    stored = _load_one("POINT::pressure::1", entry)

    assert stored.num_components == 7
    assert stored.array_name == "pressure"


# ------------------------------------------------------------------
# The write path
# ------------------------------------------------------------------

def test_already_built_instances_pass_through_untouched():
    """The write path hands the validator models, not dicts, and keeps them.

    The mapper passes the runtime dictionary through wholesale, so the values
    arriving here are the very objects the caller built.  They must not be
    rebuilt, copied, or re-derived from their identifiers.
    """
    built = VisorVariableState(
        id="POINT::pressure::1",
        array_name="pressure",
        type=VisorVtkVariableType.POINT,
        num_components=1,
    )

    scene = PersistedSceneState(variable_states={"POINT::pressure::1": built})

    assert scene.variable_states["POINT::pressure::1"] is built


def test_instances_are_not_re_derived_from_a_disagreeing_identifier():
    """A model whose fields disagree with its id keeps its fields."""
    built = VisorVariableState(
        id="POINT::pressure::1",
        array_name="something_else",
        type=VisorVtkVariableType.CELL,
        num_components=4,
    )

    scene = PersistedSceneState(variable_states={"POINT::pressure::1": built})

    stored = scene.variable_states["POINT::pressure::1"]
    assert stored.array_name == "something_else"
    assert stored.type is VisorVtkVariableType.CELL
    assert stored.num_components == 4


# ------------------------------------------------------------------
# Failures stay loud
# ------------------------------------------------------------------

def test_unparseable_identifier_raises_validation_error():
    """An identifier that cannot be derived from fails, rather than filling a guess."""
    document = _document({"POINT::pressure": _entry("POINT::pressure")})

    with pytest.raises(ValidationError) as excinfo:
        _load(document)

    # Pydantic reports missing fields under the spelling it validated by, which
    # for a document read off the wire is the alias.
    reported = {error["loc"][-1] for error in excinfo.value.errors()}
    assert {"arrayName", "type", "numComponents"} <= reported


def test_empty_array_name_in_the_identifier_raises_validation_error():
    """``POINT::::1`` reaches validation unfilled, and fails there."""
    document = _document({"POINT::::1": _entry("POINT::::1")})

    with pytest.raises(ValidationError) as excinfo:
        _load(document)

    reported = {error["loc"][-1] for error in excinfo.value.errors()}
    assert {"arrayName", "type", "numComponents"} <= reported


def test_explicit_null_still_fails_rather_than_being_backfilled():
    """A present-but-null field is present, and an invalid value, not an absent one."""
    entry = _entry("POINT::pressure::1")
    entry["arrayName"] = None

    with pytest.raises(ValidationError):
        _load(_document({"POINT::pressure::1": entry}))


def test_non_mapping_entry_raises_validation_error():
    """A malformed entry produces a ValidationError, never a TypeError."""
    document = json.dumps(
        {"version": "1.0", "scene": {"variable_states": {"POINT::pressure::1": "not-a-mapping"}}}
    )

    with pytest.raises(ValidationError):
        _load(document)


def test_non_mapping_variable_states_raises_validation_error():
    """The container itself being malformed is Pydantic's to report."""
    document = json.dumps({"version": "1.0", "scene": {"variable_states": "not-a-mapping"}})

    with pytest.raises(ValidationError):
        _load(document)


# ------------------------------------------------------------------
# Which string the derivation reads
# ------------------------------------------------------------------

def test_identifier_is_taken_from_the_entry_id_when_it_disagrees_with_the_key():
    """The entry's own ``id`` is the identifier of record; the key is a copy of it.

    They agree in every file the client writes -- ``VisorSceneState`` keys the
    dictionary by ``newState.id`` and re-emits ``id`` inside ``toDict()`` -- so
    this pins the precedence rule explicitly rather than letting it go untested
    because the two happen to coincide.
    """
    entry = _entry("CELL::temperature::3")

    stored = _load_one("POINT::pressure::1", entry)

    assert stored.array_name == "temperature"
    assert stored.type is VisorVtkVariableType.CELL
    assert stored.num_components == 3


def test_key_and_id_agreeing_derive_the_values_the_identifier_spells_out():
    """The normal case: key equals id, and both spell out the same three fields."""
    stored = _load_one("POINT::stress::yy::3")

    assert stored.id == "POINT::stress::yy::3"
    assert stored.array_name == "stress::yy"
    assert stored.type is VisorVtkVariableType.POINT
    assert stored.num_components == 3


def test_key_is_used_when_the_entry_carries_no_id():
    """With no ``id`` to read, the mapping key stands in for it.

    ``id`` is itself required, so such an entry still fails -- but it must fail
    on ``id`` alone, which is what shows the three identity fields were filled
    from the key rather than left absent.
    """
    document = _document({"POINT::pressure::1": {"magnitudeRange": [0.0, 1.0], "ranges": []}})

    with pytest.raises(ValidationError) as excinfo:
        _load(document)

    reported = {error["loc"][-1] for error in excinfo.value.errors()}
    assert reported == {"id"}


# ------------------------------------------------------------------
# The version literal
# ------------------------------------------------------------------

def test_version_literal_is_1_0():
    """The persisted schema version is 1.0."""
    assert PersistedViewerStateV1().version == "1.0"


def test_a_document_declaring_version_1_1_is_rejected():
    """1.1 was never released as a schema version and must not be accepted."""
    with pytest.raises(ValidationError):
        _load(_document({}, version="1.1"))

