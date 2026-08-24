"""Model for runtime state of the viusalizer scene."""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimeDatasetState


class RuntimeSceneState(BaseModel):
    """
    Represents the runtime, in-memory state of a Visor visualization scene,
    including properties for individual datasets.
    The dataset dictionary is keyed by internal dataset IDs.
    This class is for serialization of the runtime state that is sent
    to the frontend viewer (not to be confused with persisted state, which is stable between viewer sessions).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    unit: str | None = None
    camera: VisorCameraState | None = None
    cross_section: VisorCrossSectionState | None = Field(default=None, alias="crossSection")
    orthographic_enabled: bool | None = Field(default=None, alias="orthographicEnabled")
    cross_section_enabled: bool | None = Field(default=None, alias="crossSectionEnabled")
    edges_enabled: bool | None = Field(default=None, alias="edgesEnabled")
    bounding_box_enabled: bool | None = Field(default=None, alias="boundingBoxEnabled")
    dataset_states: Dict[int, "RuntimeDatasetState"] = Field(default_factory=dict, alias="datasetStates")
    spectrum_states: Dict[str, "VisorVariableState"] = Field(default_factory=dict, alias="spectrumStates")

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
