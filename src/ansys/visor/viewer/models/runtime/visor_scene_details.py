"""Model for visor scene details, the data transfer object sent to the client."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from ansys.visor.viewer.models.runtime.scene.runtime_scene_state import RuntimeSceneState
from ansys.visor.viewer.models.runtime.scene.runtime_ui_state import RuntimeUIState
from ansys.visor.viewer.models.runtime.scene.runtime_view_state import scene_dump_with_view
from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import RendererAnnotation
from ansys.visor.viewer.models.runtime.vtk.runtime_vtk_info import RuntimeVTKInfo
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo

# Bumped whenever the scene-details wire shape changes incompatibly.
SCENE_DETAILS_SCHEMA_VERSION: int = 3


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

    @model_serializer(mode="wrap")
    def _dump_in_the_app_state_shape(
            self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict:
        """Nest ui and scene under appState, beside schemaVersion and vtkInfo.

        The scene object carries null ``camera`` and ``crossSection`` keys
        after ``unit`` unless ``exclude_none`` is set, which is the shape the
        client reads.
        """
        data: dict = handler(self)
        schema_key = "schemaVersion" if info.by_alias else "schema_version"
        app_key = "appState" if info.by_alias else "app_state"
        vtk_key = "vtkInfo" if info.by_alias else "vtk_info"
        view = {} if info.exclude_none else {
            "camera": None,
            "crossSection" if info.by_alias else "cross_section": None,
        }
        out: dict = {}
        if schema_key in data:
            out[schema_key] = data[schema_key]
        out[app_key] = {"ui": data["ui"], "scene": scene_dump_with_view(data["scene"], view)}
        if vtk_key in data:
            out[vtk_key] = data[vtk_key]
        return out


VisorSceneDetails.model_rebuild()
