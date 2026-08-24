from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.vtk.scene_graph.root_node import VisorBounds, VisorSceneGraph


def test_visor_bounds_set_and_remove():
    """Verify that VisorBounds set and remove methods work correctly."""
    bounds = VisorBounds()
    bounds.set(1, [1,2,3,4,5,6])
    assert bounds.bounds[1] == [1,2,3,4,5,6]
    bounds.remove(1)
    assert 1 not in bounds.bounds

def test_visor_bounds_compute_bounds_empty():
    """Verify that VisorBounds compute bounds correctly."""
    bounds = VisorBounds()
    result = bounds.compute_bounds()
    assert result == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

def test_visor_bounds_compute_bounds_multiple():
    """Verify that VisorBounds compute bounds correctly with multiple entries."""
    bounds = VisorBounds()
    bounds.set(1, [1,2,3,4,5,6])
    bounds.set(2, [0,3,2,5,1,7])
    result = bounds.compute_bounds()
    # min_x=0, max_x=3, min_y=2, max_y=5, min_z=1, max_z=7
    assert result == [0,3,2,5,1,7]

@pytest.fixture
def patch_scene_graph_node(monkeypatch):
    """Verify that scene graph node is set correctly."""
    dummy_node = MagicMock()
    dummy_node.id = 42
    dummy_node.bounds = [1,2,3,4,5,6]
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.VisorSceneGraphNode.get_node",
        lambda *a, **k: dummy_node
    )
    return dummy_node

@pytest.fixture
def patch_vtk_information(monkeypatch):
    """Provide a mock for vtkInformation to avoid VTK dependency in tests."""
    monkeypatch.setattr(
        "ansys.visor.viewer.vtk.scene_graph.root_node.vtkInformation",
        MagicMock
    )

def test_scene_graph_init(patch_vtk_information):
    """Verify that VisorSceneGraph initializes correctly with expected properties."""
    graph = VisorSceneGraph()
    assert graph._node_type.name == "ROOT"
    assert graph._name == "root"
    assert graph._vtk_dataset_type == "root"
    assert isinstance(graph._dataset_bounds, VisorBounds)

def test_scene_graph_bounds_property(patch_vtk_information):
    """Verify that VisorSceneGraph bounds property reflects dataset bounds correctly."""
    graph = VisorSceneGraph()
    # No bounds set yet
    assert graph.bounds == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    # Set some bounds
    graph._dataset_bounds.set(1, [1,2,3,4,5,6])
    assert graph.bounds == [1, 2, 3, 4, 5, 6]

def test_scene_graph_load_dataset(patch_scene_graph_node, patch_vtk_information):
    """Verify that scene graph load_dataset correctly with expected properties."""
    graph = VisorSceneGraph()
    dummy_dataset = MagicMock()
    node_id = graph.load_dataset(dummy_dataset, name="foo")
    # Should call get_node and add_child, and update bounds
    assert node_id == 42
    assert graph._dataset_bounds.bounds[42] == [1,2,3,4,5,6]
    assert graph.children[-1].id == 42

def test_scene_graph_remove_dataset(patch_scene_graph_node, patch_vtk_information):
    """Verify that scene graph remove_dataset correctly removes the dataset and updates bounds."""
    graph = VisorSceneGraph()
    dummy_dataset = MagicMock()
    node_id = graph.load_dataset(dummy_dataset, name="foo")
    # Add another bounds for coverage
    graph._dataset_bounds.set(99, [0,1,2,3,4,5])
    # Remove the loaded node
    graph.remove_dataset(node_id)
    assert node_id not in graph._dataset_bounds.bounds
    # Remove a non-existent node (should not raise)
    graph.remove_dataset(123)

