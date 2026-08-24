from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.vtk.scene_graph.group_node import VisorSceneGraphGroupNode


@pytest.fixture
def patch_vtk_types(monkeypatch):
    """Provides dummy VTK types for testing."""
    # Patch the VTK types to dummy classes
    class DummyMultiBlock:
        pass

    class DummyMultiPiece:
        pass

    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.group_node.vtkMultiBlockDataSet",
        DummyMultiBlock
    )
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.group_node.vtkMultiPieceDataSet",
        DummyMultiPiece
    )
    return DummyMultiBlock, DummyMultiPiece

@pytest.fixture
def mock_node_metadata():
    """Provides a mock node metadata object."""
    meta = MagicMock()
    meta.Has.return_value = False
    meta.Get.return_value = ""
    return meta

def test_init_with_multiblock(monkeypatch, patch_vtk_types, mock_node_metadata):
    """Verify that initializing with multiblock dataset sets the correct properties."""
    dummy_multiblock_cls, _ = patch_vtk_types
    dummy_dataset = dummy_multiblock_cls()
    dummy_dataset.GetNumberOfBlocks = lambda: 2
    dummy_dataset.GetBounds = lambda arr: arr.__setitem__(slice(None), [1,2,3,4,5,6])
    dummy_dataset.GetBlock = lambda i: f"block{i}"
    dummy_dataset.GetMetaData = lambda i: f"meta{i}"
    dummy_node = MagicMock()
    monkeypatch.setattr("ansys.visor.viewer.vtk.scene_graph.VisorSceneGraphNode.get_node", lambda *a, **k: dummy_node)
    node = VisorSceneGraphGroupNode(
        parent=None,
        node_metadata=mock_node_metadata,
        dataset=dummy_dataset,
        root_node=None
    )
    assert node._node_type.name == "GROUP"
    assert node._vtk_dataset_type == "vtkMultiBlockDataSet"
    assert node._bounds == [1, 2, 3, 4, 5, 6]
    assert node.children == [dummy_node, dummy_node]

def test_init_with_multipiece(monkeypatch, patch_vtk_types, mock_node_metadata):
    """Verify that initializing with multipiece dataset sets the correct properties."""
    _, dummy_multipiece_cls = patch_vtk_types
    dummy_dataset = dummy_multipiece_cls()
    dummy_dataset.GetNumberOfPieces = lambda: 1
    dummy_dataset.GetBounds = lambda arr: arr.__setitem__(slice(None), [7,8,9,10,11,12])
    dummy_dataset.GetBlock = lambda i: f"piece{i}"
    dummy_dataset.GetMetaData = lambda i: f"meta{i}"
    dummy_node = MagicMock()
    monkeypatch.setattr("ansys.visor.viewer.vtk.scene_graph.VisorSceneGraphNode.get_node", lambda *a, **k: dummy_node)
    node = VisorSceneGraphGroupNode(
        parent=None,
        node_metadata=mock_node_metadata,
        dataset=dummy_dataset,
        root_node=None
    )
    assert node._node_type.name == "GROUP"
    assert node._vtk_dataset_type == "vtkMultiPieceDataSet"
    assert node._bounds == [7, 8, 9, 10, 11, 12]
    assert node.children == [dummy_node]

def test_add_child_sets_parent_and_clears_cache(monkeypatch, patch_vtk_types, mock_node_metadata):
    """Verify that adding child nodes sets parent and clears cache."""
    dummy_multiblock_cls, _ = patch_vtk_types
    dummy_dataset = dummy_multiblock_cls()
    dummy_dataset.GetNumberOfBlocks = lambda: 0
    dummy_dataset.GetBounds = lambda arr: arr.__setitem__(slice(None), [0]*6)
    node = VisorSceneGraphGroupNode(
        parent=None,
        node_metadata=mock_node_metadata,
        dataset=dummy_dataset,
        root_node=None
    )
    child = MagicMock()
    node._clear_cache = MagicMock()
    node.add_child(child)
    assert child.Parent is node
    assert node.children == [child]
    node._clear_cache.assert_called_once()

def test_children_property(patch_vtk_types, mock_node_metadata):
    """Verify that children property returns a list."""
    dummy_multiblock_cls, _ = patch_vtk_types
    dummy_dataset = dummy_multiblock_cls()
    dummy_dataset.GetNumberOfBlocks = lambda: 0
    dummy_dataset.GetBounds = lambda arr: arr.__setitem__(slice(None), [0]*6)
    node = VisorSceneGraphGroupNode(
        parent=None,
        node_metadata=mock_node_metadata,
        dataset=dummy_dataset,
        root_node=None
    )
    assert isinstance(node.children, list)

def test_state_property(patch_vtk_types, mock_node_metadata):
    """Verify that state property returns a list."""
    dummy_multiblock_cls, _ = patch_vtk_types
    dummy_dataset = dummy_multiblock_cls()
    dummy_dataset.GetNumberOfBlocks = lambda: 0
    dummy_dataset.GetBounds = lambda arr: arr.__setitem__(slice(None), [0]*6)
    node = VisorSceneGraphGroupNode(
        parent=None,
        node_metadata=mock_node_metadata,
        dataset=dummy_dataset,
        root_node=None
    )
    child = MagicMock()
    child.state = "child_state"
    node._children = [child]
    state = node.state
    assert hasattr(state, "children")
    assert state.children == ["child_state"]

def test_init_with_unsupported_type(mock_node_metadata):
    """Verify that initializing with an unsupported dataset type raises RuntimeError."""
    class DummyData:
        pass

    dummy = DummyData()
    with pytest.raises(RuntimeError, match="node type not yet supported"):
        VisorSceneGraphGroupNode(
            parent=None,
            node_metadata=mock_node_metadata,
            dataset=dummy,
            root_node=None
        )
