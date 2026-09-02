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

def derive_variable_fields_from_identifier(identifier: Any) -> Dict[str, Any] | None:
    """Recover ``type``, ``array_name`` and ``num_components`` from a variable identifier.

    This is the inverse of the client's creation of the variable ID, and the only place the
    identifier is parsed.  The array name is in the middle field and is user data, so it may
    contain the separator: the split is anchored at both ends rather than left to right, and
    ``"POINT::stress::yy::3"`` yields the array name ``"stress::yy"``.

    Returns ``None`` when the identifier does not spell out three usable fields, meaning
    "cannot be derived" rather than "derived to a default".  Callers leave such an
    entry untouched so ordinary validation reports the missing fields.
    """
    if not isinstance(identifier, str):
        return None

    # Strip out the last field, which is the number of components.
    # e.g. "POINT::stress::yy::3".rpartition("::") -> ("POINT::stress::yy", "::", "3")
    head, separator, num_components_str = identifier.rpartition(_IDENTIFIER_SEPARATOR)
    if not separator:
        return None

    try:
        num_components = int(num_components_str)
    except (TypeError, ValueError):
        return None

    # Strip out the first field, which is the variable type.  The remainder is the array name,
    # which may contain the separator.
    # e.g. "POINT::stress::yy".partition("::") -> ("POINT", "::", "stress::yy")
    variable_type, separator, array_name = head.partition(_IDENTIFIER_SEPARATOR)
    if not separator:
        return None

    if not variable_type or not array_name:
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
        """Fill absent identity fields on read, from the variable identifier.

        ``array_name``, ``type``, and ``num_components`` are required and stay
        required: the model is shared with ``RuntimeSceneState.spectrum_states``,
        so relaxing them would also relax the save-path coercion in
        ``VisorSaveStateResponse._coerce_app_state``.  Tolerance for older save
        files lives here, on the container, and applies to the ingest boundary only.
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
        if isinstance(entry, VisorVariableState) or not isinstance(entry, Mapping):
            return entry

        # A value that is present but null counts as present and is left
        # to fail validation.
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

        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier:
            identifier = key

        derived = derive_variable_fields_from_identifier(identifier)
        if derived is None:
            return entry

        filled = dict(entry)
        for field in missing:
            filled[field] = derived[field]
        return filled

