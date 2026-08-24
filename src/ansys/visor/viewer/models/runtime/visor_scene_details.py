"""Model for visor scene details, the data transfer object sent to the client."""

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimeDatasetState
from ansys.visor.viewer.models.runtime.scene.runtime_app_state import RuntimeAppState
from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import RendererAnnotation
from ansys.visor.viewer.models.runtime.vtk.runtime_vtk_info import RuntimeVTKInfo
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo

# Bumped whenever the scene-details wire shape changes incompatibly.
SCENE_DETAILS_SCHEMA_VERSION: int = 2


class VisorSceneDetails(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    schema_version: int = Field(
        default=SCENE_DETAILS_SCHEMA_VERSION, alias="schemaVersion"
    )
    app_state: RuntimeAppState | None = Field(default=None, alias="appState")
    vtk_info: RuntimeVTKInfo | None = Field(default=None, alias="vtkInfo")

    @classmethod
    def from_components(
            cls,
            dark_mode: bool,
            unit: str | None,
            dataset_states: Dict[int, RuntimeDatasetState],
            scene_graph_state: SceneGraphNodeInfo | None = None,
            renderer_annotation: RendererAnnotation | None = None,
    ) -> "VisorSceneDetails":
        """Construct an instance from components."""
        vtk_info = RuntimeVTKInfo(
            scene_graph=scene_graph_state,
            renderer_annotation=renderer_annotation,
        )
        app_state = RuntimeAppState.from_components(
            dark_mode=dark_mode,
            unit=unit,
            dataset_states=dataset_states,
        )
        return cls(
            app_state=app_state,
            vtk_info=vtk_info,
        )


VisorSceneDetails.model_rebuild()
