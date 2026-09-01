"""Model for persisted scene state (cross-session)."""

from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState

#: Separator used by the client when it mints a variable identifier.  See
#: ``VisorSpectrumManager.tryAddSpectrumInfo``, which builds the identifier as
#: ``` `${type}::${name}::${numComponents}` ```.
_IDENTIFIER_SEPARATOR = "::"

#: Number of fields the client packs into an identifier.
_IDENTIFIER_FIELD_COUNT = 3


def derive_variable_fields_from_identifier(identifier: Any) -> Dict[str, Any] | None:
    """Recover ``type``, ``array_name`` and ``num_components`` from a variable identifier.

    The client mints the identifier as ``<type>::<name>::<number-of-components>``
    (``VisorSpectrumManager.tsx``), so the three identifying properties are
    recoverable from the identifier alone.  This function is the permanent,
    named inverse of that minting, and is the *only* place the identifier is
    taken apart.

    The split is anchored at both ends and driven by the field count, **not** by
    a left-to-right split on the separator: the array name is the middle field
    and is user data, so it may itself contain ``::``.  Two cuts:

    1. one cut from the right yields the trailing component count, and
    2. one cut from the left of the remainder yields the leading type,

    leaving everything between them as the array name, verbatim and with any
    embedded separators intact.  ``"POINT::stress::yy::3"`` therefore yields the
    array name ``"stress::yy"``, where a left-to-right split would have
    truncated it to ``"stress"``.

    Args:
        identifier: The persisted variable identifier.

    Returns:
        A mapping of the three derived fields, or ``None`` when the identifier
        does not spell out three usable fields.  ``None`` means "cannot be
        derived", never "derived to a default": callers must leave the entry
        untouched so that ordinary validation reports the missing fields, rather
        than filling in a guess.  Structural success is not semantic success, so
        an empty type or array name, or a non-integer component count, is
        refused even though the separators are all present.
    """
    if not isinstance(identifier, str):
        return None

    head, separator, trailing = identifier.rpartition(_IDENTIFIER_SEPARATOR)
    if not separator:
        return None

    variable_type, separator, array_name = head.partition(_IDENTIFIER_SEPARATOR)
    if not separator:
        return None

    # Structurally there are now three fields.  Refuse the ones that are not
    # semantically usable rather than admitting a state that names an array
    # which cannot exist.
    if not variable_type or not array_name:
        return None

    try:
        num_components = int(trailing)
    except (TypeError, ValueError):
        return None

    return {
        "type": variable_type,
        "array_name": array_name,
        "num_components": num_components,
    }


class PersistedSceneState(BaseModel):
    """Persisted (cross-session) scene state.

    This model is part of the on-disk save/load format and must contain only
    stable identifiers.

    Notes:
        - ``dataset_states`` is keyed by **dataset name** (string), which is a stable identifier across sessions.
        - ``variable_states`` is keyed by **variable ID** (string), which is a stable identifier across sessions.
    """

    unit: str | None = None
    camera: VisorCameraState | None = None
    cross_section: VisorCrossSectionState | None = None
    orthographic_enabled: bool | None = None
    cross_section_enabled: bool | None = None
    edges_enabled: bool | None = None
    bounding_box_enabled: bool | None = None
    camera: VisorCameraState | None = None
    dataset_states: Dict[str, "PersistedDatasetState"] = Field(default_factory=dict)
    variable_states: Dict[str, "VisorVariableState"] = Field(default_factory=dict)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("variable_states", mode="before")
    @classmethod
    def _derive_missing_variable_identity_fields(cls, value: Any) -> Any:
        """Fill absent identity fields on *read*, from the variable identifier.

        ``VisorVariableState.array_name``, ``.type`` and ``.num_components`` are
        required and stay required: they are shared with
        ``RuntimeSceneState.spectrum_states``, so relaxing them on the model
        would also relax the save-path coercion in
        ``VisorSaveStateResponse._coerce_app_state``.  The tolerance for older
        save files therefore lives here, on the container, where it applies to
        the ingest boundary only.

        Save files written before those fields existed carry the same three
        properties inside the identifier, so they are recovered by
        :func:`derive_variable_fields_from_identifier` before coercion.  Nothing
        downstream of this validator ever sees ``None``: by the time an entry
        becomes a ``VisorVariableState`` the fields are populated or validation
        has already failed.

        Values that are already ``VisorVariableState`` instances -- which is
        every value on the *write* path, where the mapper passes the runtime
        dictionary through wholesale -- are handed back untouched.  Values that
        are not mappings are handed back untouched too, so that Pydantic raises
        a well-formed ``ValidationError`` rather than this validator raising
        ``TypeError`` while indexing.
        """
        if not isinstance(value, Mapping):
            return value

        out: Dict[Any, Any] = {}
        for key, entry in value.items():
            out[key] = cls._derive_missing_identity_fields_for_entry(key, entry)
        return out

    @staticmethod
    def _derive_missing_identity_fields_for_entry(key: Any, entry: Any) -> Any:
        """Return *entry* with any absent identity fields derived from its identifier."""
        # Already-built models (the write path) and non-mappings are not ours to touch.
        if isinstance(entry, VisorVariableState) or not isinstance(entry, Mapping):
            return entry

        # ``populate_by_name`` is set on VisorVariableState, so either spelling
        # counts as present.  A present-but-null value counts as present: only
        # genuine absence is tolerated, so an explicit null still fails.
        missing = [
            field
            for field, alias in (
                ("array_name", "arrayName"),
                ("type", "type"),
                ("num_components", "numComponents"),
            )
            if field not in entry and alias not in entry
        ]
        if not missing:
            return entry

        # The entry carries the identifier as a field of its own; the mapping key
        # is a copy of it.  Prefer the entry's own value, fall back to the key.
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier:
            identifier = key

        derived = derive_variable_fields_from_identifier(identifier)
        if derived is None:
            # Undecipherable: leave it alone and let ordinary validation report
            # the missing fields.  Never fill with a guess.
            return entry

        filled = dict(entry)
        for field in missing:
            filled[field] = derived[field]
        return filled

