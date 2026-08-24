"""Model for the runtime application state for a Visor visualizer instance."""

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.common.visor_cross_section_state import VisorCrossSectionState
from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimeDatasetState
from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import RuntimeSceneState


class RuntimeAppState(BaseModel):
    """
    Represents the runtime, in-memory state of a Visor visualization,
    including properties for individual parts.

    The part dictionary is keyed by internal dataset IDs.

    This class is for serialization of the runtime state that is sent
    to the frontend viewer.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    ui: VisorUIState = Field(default_factory=VisorUIState)
    scene: RuntimeSceneState = Field(default_factory=RuntimeSceneState)

    @classmethod
    def from_components(
            cls,
            dark_mode: bool,
            unit: str | None,
            dataset_states: Dict[int, RuntimeDatasetState],
            orthographic_enabled: bool | None = None,
            cross_section_enabled: bool | None = None,
            edges_enabled: bool | None = None,
            bounding_box_enabled: bool | None = None,
            cross_section: VisorCrossSectionState | None = None,
            camera: VisorCameraState | None = None,
            variable_states: Dict[str, VisorVariableState] | None = None,
    ) -> "RuntimeAppState":
        """Construct a RuntimeAppState from the given components."""
        ui_state = VisorUIState(dark_theme=dark_mode)
        runtime_scene_state = RuntimeSceneState(
            unit=unit,
            camera=camera,
            cross_section=cross_section,
            orthographic_enabled=orthographic_enabled,
            cross_section_enabled=cross_section_enabled,
            edges_enabled=edges_enabled,
            bounding_box_enabled=bounding_box_enabled,
            dataset_states=dataset_states,
            spectrum_states=variable_states or {},
        )
        return cls(
            ui=ui_state,
            scene=runtime_scene_state,
        )
