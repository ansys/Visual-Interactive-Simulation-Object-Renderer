import pydantic
import pytest

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo


def test_minimal_construction():
    """Verify that a SceneGraphNodeInfo can be constructed with minimal required fields."""
    node = SceneGraphNodeInfo(
        id=1,
        name="root",
        is_actor_node=True,
        is_group_node=False,
        node_type="actor"
    )
    assert node.id == 1
    assert node.name == "root"
    assert node.diffuse_color == VisorColors.DefaultMeshColor
    assert node.children == []

def test_defaults_and_nested_children():
    """Verify that default values are applied and children can be nested."""
    child = SceneGraphNodeInfo(
        id=2,
        name="child",
        is_actor_node=False,
        is_group_node=True,
        node_type="group"
    )
    parent = SceneGraphNodeInfo(
        id=1,
        name="parent",
        is_actor_node=True,
        is_group_node=False,
        node_type="actor",
        children=[child]
    )
    assert parent.children[0].name == "child"

def test_missing_required_fields():
    """Verify a ValidationError is raised when required fields are missing from SceneGraphNodeInfo."""
    with pytest.raises(pydantic.ValidationError):
        SceneGraphNodeInfo(id=1)  # missing required fields

def test_type_validation():
    """Verify that type validation works for SceneGraphNodeInfo."""
    with pytest.raises(ValueError):
        SceneGraphNodeInfo(
            id="not-an-int",
            name="bad",
            is_actor_node=True,
            is_group_node=False,
            node_type="actor"
        )
