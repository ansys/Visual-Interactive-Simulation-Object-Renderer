"""Model for the runtime VTK info."""

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny

from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import RendererAnnotation
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo


class RuntimeVTKInfo(BaseModel):
    """
    Represents the runtime, in-memory VTK-specific state of a Visor visualization scene.
    This class is for serialization of the runtime VTK state that is sent
    to the frontend viewer.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    scene_graph: SceneGraphNodeInfo | None = Field(default=None, alias="sceneGraph")
    # Must be SerializeAsAny so pydantic v2 serializes the concrete subclass's
    # extra fields (`nodes`, `widgets`) rather than only the base's `rendererKind`.
    renderer_annotation: SerializeAsAny[RendererAnnotation] | None = Field(
        default=None, alias="rendererAnnotation"
    )


RuntimeVTKInfo.model_rebuild()
