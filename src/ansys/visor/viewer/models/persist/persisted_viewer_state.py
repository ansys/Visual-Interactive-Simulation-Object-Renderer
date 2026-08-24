"""Model for persisting Visor viewer state across sessions."""


from typing import Dict, Literal

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState
from ansys.visor.viewer.models.persist.scene.persisted_scene_state import PersistedSceneState


class PersistedViewerStateV1(BaseModel):
    """
    Versioned container for persisting Visor viewer state across sessions.

    Contains only stable identifiers (dataset names, part names) without
    session-specific IDs or WASM references.

    TODO: Extend in future versions to include more state information
    such as camera position, active variables, UI settings, etc.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    version: Literal["1.0"] = Field(default="1.0")

    ui: VisorUIState = Field(default_factory=VisorUIState)
    scene: PersistedSceneState = Field(default_factory=PersistedSceneState)

    @classmethod
    def from_components(cls,
                        ui_state: VisorUIState,
                        unit: str | None,
                        orthographic_enabled: bool | None,
                        cross_section_enabled: bool | None,
                        edges_enabled: bool | None,
                        bounding_box_enabled: bool | None,
                        datasets: Dict[str, PersistedDatasetState],
                        camera: VisorCameraState | None = None,
                        cross_section: VisorCrossSectionState | None = None,
                        variable_states: Dict[str, "VisorVariableState"] | None = None,
                        ) -> "PersistedViewerStateV1":
        """
        Create a PersistedViewerStateV1 instance from UI settings and dataset states.

        Args:
            ui_state (VisorUIState): UI settings object.
            unit (str | None): Scene unit (or None).
            datasets (Dict[str, PersistedDatasetState]): Dataset states keyed by dataset name.
            camera (VisorCameraState | None): Camera state (or None).
            variable_states (Dict[str, VisorVariableState] | None): Variable states keyed by variable identifier (or None).
        Returns:
            PersistedViewerStateV1: The constructed viewer state.
        """
        scene_state = PersistedSceneState(
            unit=unit,
            camera=camera,
            cross_section=cross_section,
            orthographic_enabled=orthographic_enabled,
            cross_section_enabled=cross_section_enabled,
            edges_enabled=edges_enabled,
            bounding_box_enabled=bounding_box_enabled,
            dataset_states=datasets,
            variable_states=variable_states or {},
        )
        return cls(ui=ui_state, scene=scene_state)
