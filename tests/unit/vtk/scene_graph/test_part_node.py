"""Unit tests for VisorSceneGraphPartNode."""

from unittest.mock import MagicMock, patch

import pytest
from vtkmodules.vtkCommonDataModel import vtkPolyData, vtkUnstructuredGrid
from vtkmodules.vtkFiltersSources import vtkSphereSource

from ansys.visor.viewer.core.visor_enums import VisorNodeType
from ansys.visor.viewer.vtk.scene_graph.part_node import VisorSceneGraphPartNode


@pytest.fixture
def mock_all_init_methods():
    """Mock non-VTK-pipeline init helpers to give stable behavior."""
    vars_container = MagicMock()
    vars_container.list_info.return_value = [{"dummy": "meta"}]

    patches = [
        patch.object(VisorSceneGraphPartNode, "_set_name"),
        patch.object(VisorSceneGraphPartNode, "_get_vtk_dataset_type", return_value="vtkPolyData"),
        patch.object(VisorSceneGraphPartNode, "_get_bounds", return_value=[0, 1, 2, 3, 4, 5]),
        patch.object(VisorSceneGraphPartNode, "_get_variable_metadata", return_value=vars_container),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Structure and identity
# ---------------------------------------------------------------------------

def test_init_populates_scene_metadata_only(mock_all_init_methods):
    dataset = MagicMock(name="dataset")
    node = VisorSceneGraphPartNode(
        parent=None,
        node_metadata=MagicMock(),
        dataset=dataset,
    )

    assert node._node_type == VisorNodeType.PART
    assert node.dataset is dataset
    assert node._vtk_dataset_type == "vtkPolyData"
    assert node._bounds == [0, 1, 2, 3, 4, 5]
    assert node.data_arrays == [{"dummy": "meta"}]


def test_part_node_holds_no_vtk_pipeline_objects(mock_all_init_methods):
    """Guard rail: pipeline objects must never appear on the part node."""
    node = VisorSceneGraphPartNode(
        parent=None,
        node_metadata=MagicMock(),
        dataset=MagicMock(),
    )
    for banned in ("_Actor", "_Mapper", "_BaseAlgorithm", "Actor", "Mapper", "BaseAlgorithm"):
        assert not hasattr(node, banned), (
            f"VisorSceneGraphPartNode must not expose {banned!r}: "
            "VTK pipeline objects belong on VtkNodePipeline."
        )


def test_is_part_node_true(mock_all_init_methods):
    node = VisorSceneGraphPartNode(
        parent=None, node_metadata=MagicMock(), dataset=MagicMock()
    )
    assert node.is_part_node is True
    assert node.is_group_node is False


# ---------------------------------------------------------------------------
# Wire-format identity: node.state must serialize the same way an actor node
# would (isActorNode=True, dataArrays populated, diffuseColor default).
# ---------------------------------------------------------------------------

def test_state_matches_wire_format_for_actor_leaf(mock_all_init_methods):
    node = VisorSceneGraphPartNode(
        parent=None, node_metadata=MagicMock(), dataset=MagicMock()
    )
    state = node.state

    assert state.is_actor_node is True
    assert state.is_group_node is False
    assert state.data_arrays == [{"dummy": "meta"}]
    assert state.bounds == [0, 1, 2, 3, 4, 5]
    assert state.node_type == "vtkPolyData"
    assert hasattr(state, "diffuse_color")


# ---------------------------------------------------------------------------
# Variable metadata refresh does not touch a pipeline
# ---------------------------------------------------------------------------

def test_refresh_variable_metadata_rereads_from_dataset(mock_all_init_methods):
    node = VisorSceneGraphPartNode(
        parent=None, node_metadata=MagicMock(), dataset=MagicMock()
    )
    with patch.object(
        VisorSceneGraphPartNode,
        "_get_variable_metadata",
        return_value=MagicMock(list_info=lambda: [{"refreshed": True}]),
    ) as m:
        node.refresh_variable_metadata()
        m.assert_called_once_with(node._dataset)
    assert node.data_arrays == [{"refreshed": True}]


# ---------------------------------------------------------------------------
# Dataset-type dispatch (real VTK types, not mocked)
# ---------------------------------------------------------------------------

def _sphere_polydata() -> vtkPolyData:
    src = vtkSphereSource()
    src.Update()
    return src.GetOutput()


def test_get_vtk_dataset_type_polydata():
    info = MagicMock()
    info.Has.return_value = False
    node = VisorSceneGraphPartNode(
        parent=None, node_metadata=info, dataset=_sphere_polydata()
    )
    assert node._vtk_dataset_type == "vtkPolyData"


def test_get_vtk_dataset_type_unstructured_grid():
    info = MagicMock()
    info.Has.return_value = False
    node = VisorSceneGraphPartNode(
        parent=None, node_metadata=info, dataset=vtkUnstructuredGrid()
    )
    assert node._vtk_dataset_type == "vtkUnstructuredGrid"


def test_get_vtk_dataset_type_unsupported_raises():
    info = MagicMock()
    info.Has.return_value = False
    with pytest.raises(RuntimeError, match="node type not yet supported"):
        VisorSceneGraphPartNode(parent=None, node_metadata=info, dataset=object())

