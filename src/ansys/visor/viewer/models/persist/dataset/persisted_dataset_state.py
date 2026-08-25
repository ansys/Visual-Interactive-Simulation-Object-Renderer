"""Persisted state for a single dataset (cross-session)."""

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ansys.visor.viewer.models.common.part_properties import PartProperties


class PersistedDatasetState(BaseModel):
    """Persisted state for a single dataset (cross-session).

    Fields
    ------
    - `parts` is keyed by stable *part names*.
    - `serialized_dataset_path` points at the serialized dataset written under the
      user-provided save directory (so in-mem/mutated datasets can be restored).
    - `source_file_path` / `source_metadata_path` (when present) are the original
      paths the dataset/metadata came from when first loaded.

    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    parts: Dict[str, PartProperties] = Field(
        default_factory=dict,
        description="Per-part state keyed by part name (not internal ID)"
    )
    # Path to the dataset snapshot written alongside visor.json.
    serialized_dataset_path: str | None = Field(
        default=None,
        description="Relative or absolute path to the serialized dataset snapshot in the save-state directory",
    )
    # Original source references (if the dataset/metadata were loaded from disk)
    source_file_path: str | None = Field(default=None, description="Original dataset file path provided by the user")
    source_metadata_path: str | None = Field(default=None, description="Original metadata JSON path provided by the user")


    @model_validator(mode="after")
    def ensure_parts(self) -> "PersistedDatasetState":
        """Ensure that all parts are present in the dataset."""
        if isinstance(self.parts, dict):
            self.parts = {
                k: v if isinstance(v, PartProperties) else PartProperties(**v)
                for k, v in self.parts.items()
            }
        return self
