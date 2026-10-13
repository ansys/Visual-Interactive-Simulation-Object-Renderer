"""Model for runtime state of the viusalizer scene."""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ansys.visor.viewer.models.common.visor_variable_record import VisorVariableRecord
from ansys.visor.viewer.models.persist.scene.persisted_scene_state import PersistedSceneState
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import (
    RuntimeDatasetState,
    RuntimePartProperties,
)

#: The scene-level fields a loaded file can set, each resolved by the overlay rule.
_OVERLAID_FIELDS = ("unit", "cross_section_enabled", "edges_enabled", "bounding_box_enabled")


class RuntimeSceneState(BaseModel):
    """Scene state the server owns: unit, the three toggles,
    orthographic_enabled, dataset and variable records.

    The dataset dictionary is keyed by internal dataset IDs.
    ``orthographic_enabled`` is derived from the camera record, which this
    record does not hold; ``None`` means no camera was ever written.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    unit: str
    orthographic_enabled: bool | None = Field(alias="orthographicEnabled")
    cross_section_enabled: bool = Field(alias="crossSectionEnabled")
    edges_enabled: bool = Field(alias="edgesEnabled")
    bounding_box_enabled: bool = Field(alias="boundingBoxEnabled")
    dataset_states: Dict[int, "RuntimeDatasetState"] = Field(default_factory=dict, alias="datasetStates")
    # The server's variable records (see VisorSceneBase._variable_records); never taken from the browser.
    variable_states: Dict[str, "VisorVariableRecord"] = Field(default_factory=dict, alias="variableStates")

    @classmethod
    def default(cls) -> "RuntimeSceneState":
        """The scene record before anything has been set: no unit, every toggle off, no camera."""
        return cls(
            unit="",
            cross_section_enabled=False,
            edges_enabled=False,
            bounding_box_enabled=False,
            orthographic_enabled=None,
        )

    def overlaid_with(self, persisted: PersistedSceneState, defaults: "RuntimeSceneState") -> "RuntimeSceneState":
        """A new record: the unit and each toggle the file names takes its value, or the default where null;
        an unnamed one keeps this record's.

        ``orthographic_enabled`` and the dataset and variable records are
        carried from this record unchanged: the first is derived from the
        camera, and the records have their own overlays.  This record is not
        modified.
        """
        resolved = {
            field: RuntimePartProperties._overlaid(getattr(self, field), persisted, field, getattr(defaults, field))
            for field in _OVERLAID_FIELDS
        }
        return self.model_copy(update=resolved)

    @field_validator("dataset_states", mode="before")
    @classmethod
    def _coerce_dataset_states(cls, v: Any) -> Any:
        """Coerce the given dataset state to an appropriate type."""
        # Accept None / missing
        if v is None:
            return {}

        # If already a dict, coerce keys to int (JSON object keys arrive as str)
        if isinstance(v, dict):
            out: Dict[int, Any] = {}
            for k, val in v.items():
                try:
                    ik = int(k)
                except (TypeError, ValueError):
                    # Leave key as-is if it cannot be coerced; Pydantic will raise later if invalid
                    ik = k  # type: ignore[assignment]
                out[ik] = val
            return out

        # Otherwise, let Pydantic try its normal parsing/validation
        return v
