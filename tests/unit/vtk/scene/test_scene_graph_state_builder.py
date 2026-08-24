"""Unit tests for SceneGraphStateBuilder."""

from unittest.mock import MagicMock

from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo
from ansys.visor.viewer.vtk.scene.scene_graph_state_builder import SceneGraphStateBuilder


def _leaf_info(node_id: int, name: str = "p") -> SceneGraphNodeInfo:
    return SceneGraphNodeInfo(
        id=node_id, name=name, is_actor_node=True, is_group_node=False,
        node_type="vtkPolyData",
    )


def _root_info() -> SceneGraphNodeInfo:
    return SceneGraphNodeInfo(
        id=1, name="root", is_actor_node=False, is_group_node=True, node_type="root",
    )


# ---------------------------------------------------------------------------
# Structure only: the builder reads the scene graph and recurses; it carries
# no renderer handles.
# ---------------------------------------------------------------------------

def test_builder_recurses_through_group_nodes():
    root_info = _root_info()
    group_info = SceneGraphNodeInfo(
        id=2, name="grp", is_actor_node=False, is_group_node=True, node_type="vtkMultiBlockDataSet",
    )
    a_info = _leaf_info(101, "a")
    b_info = _leaf_info(102, "b")

    a = MagicMock()
    a.id = 101
    a.is_part_node = True
    a.is_group_node = False
    a.state = a_info
    b = MagicMock()
    b.id = 102
    b.is_part_node = True
    b.is_group_node = False
    b.state = b_info
    group = MagicMock()
    group.is_part_node = False
    group.is_group_node = True
    group.state = group_info
    group.children = [a, b]
    root = MagicMock()
    root.is_part_node = False
    root.is_group_node = True
    root.state = root_info
    root.children = [group]

    out = SceneGraphStateBuilder(root).build()

    assert out is root_info
    (nested_group,) = out.children
    assert nested_group is group_info
    assert [c.name for c in nested_group.children] == ["a", "b"]


def test_builder_handles_empty_root():
    root_info = _root_info()
    root = MagicMock()
    root.is_part_node = False
    root.is_group_node = True
    root.state = root_info
    root.children = []

    out = SceneGraphStateBuilder(root).build()

    assert out is root_info
    assert out.children == []


