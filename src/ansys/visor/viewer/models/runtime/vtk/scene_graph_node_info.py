"""Model for scene graph node info."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.models.info.visor_variable_info import VisorVariableInfo


class SceneGraphNodeInfo(BaseModel):
    """Model for scene graph node info."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: int
    name: str
    is_actor_node: bool = Field(alias="isActorNode")
    is_group_node: bool = Field(alias="isGroupNode")
    data_arrays: list[VisorVariableInfo] = Field(default_factory=list, alias="dataArrays")
    node_type: str = Field(alias="nodeType")
    bounds: list = Field(default_factory=list)
    children: List['SceneGraphNodeInfo'] = Field(default_factory=list)
    diffuse_color: VisorColors = Field(default=VisorColors.DefaultMeshColor, alias="diffuseColor")


SceneGraphNodeInfo.model_rebuild()
