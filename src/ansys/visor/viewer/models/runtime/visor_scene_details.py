"""Model for visor scene details, the data transfer object sent to the client."""

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import RuntimeSceneState
from ansys.visor.viewer.models.runtime.scene.runtime_ui_state import RuntimeUIState
from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import RendererAnnotation
from ansys.visor.viewer.models.runtime.vtk.runtime_vtk_info import RuntimeVTKInfo
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo

# Bumped whenever the scene-details wire shape changes incompatibly.
SCENE_DETAILS_SCHEMA_VERSION: int = 4


class VisorSceneDetails(BaseModel):
    """What a rebuilt or reconnecting client is served: the UI and scene records and the VTK info.

    Never carries the view records; the client receives the camera and the
    plane through the VTK object state instead.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    schema_version: int = Field(
        default=SCENE_DETAILS_SCHEMA_VERSION, alias="schemaVersion"
    )
    ui: RuntimeUIState
    scene: RuntimeSceneState
    vtk_info: RuntimeVTKInfo | None = Field(default=None, alias="vtkInfo")

    @classmethod
    def from_components(
            cls,
            ui: RuntimeUIState,
            scene: RuntimeSceneState,
            scene_graph_state: SceneGraphNodeInfo | None = None,
            renderer_annotation: RendererAnnotation | None = None,
    ) -> "VisorSceneDetails":
        """Assemble the details from the server's UI and scene records and the VTK info."""
        vtk_info = RuntimeVTKInfo(
            scene_graph=scene_graph_state,
            renderer_annotation=renderer_annotation,
        )
        return cls(ui=ui, scene=scene, vtk_info=vtk_info)


VisorSceneDetails.model_rebuild()
