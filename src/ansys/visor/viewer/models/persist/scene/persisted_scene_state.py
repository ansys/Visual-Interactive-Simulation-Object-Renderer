"""Model for persisted scene state (cross-session)."""

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState


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
