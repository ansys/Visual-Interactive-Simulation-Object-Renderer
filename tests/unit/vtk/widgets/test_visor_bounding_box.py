from unittest.mock import MagicMock, create_autospec

import pytest
from vtkmodules.vtkRenderingCore import vtkCamera

from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphNode
from ansys.visor.viewer.vtk.widgets.visor_bounding_box import VisorBoundingBox


@pytest.fixture
def mock_camera():
    """Provides a mock camera instance"""
    # not actually a mock, but a real vtkCamera instance
    # VisorBoundingBox needs a real vtkCamera for SetCamera calls.
    # This cannot be fully mocked without breaking internal VTK behavior.
    return vtkCamera()

@pytest.fixture
def bbox(mock_camera):
    """
    Creates a VisorBoundingBox with:
      - Real vtkCamera (needed)
      - Mocked VTK dependencies (cube, outline, mapper, actor, text, axes)

    Using MonkeyPatch to replace the VTK classes with MagicMocks.
    This prevents actual rendering, keeps tests fast and isolated.
    """
    with pytest.MonkeyPatch.context() as m:
        m.setattr("vtkmodules.vtkFiltersSources.vtkCubeSource", lambda: MagicMock())
        m.setattr("vtkmodules.vtkFiltersModeling.vtkOutlineFilter", lambda: MagicMock())
        m.setattr("vtkmodules.vtkRenderingCore.vtkPolyDataMapper", lambda: MagicMock())
        m.setattr("vtkmodules.vtkRenderingCore.vtkActor", lambda: MagicMock())
        m.setattr("vtkmodules.vtkRenderingCore.vtkTextProperty", lambda: MagicMock())
        m.setattr("vtkmodules.vtkRenderingAnnotation.vtkCubeAxesActor2D", lambda: MagicMock())
        return VisorBoundingBox(mock_camera, node_count=0)

# ---------------------------
# Tests
# ---------------------------

def test_initial_state_hidden(bbox):
    """Verify actors can be shown/hidden without errors"""
    bbox.show()
    bbox.hide()
    # No error should be raised

def test_update_node_count(bbox):
    """Updating internal node count doesn't raise errors"""
    bbox.update_node_count(5)
    # Should update internal node_count (no error)

def test_toggle_visibility(bbox):
    """Toggles visibility correctly"""
    bbox.update_node_count(1)
    bbox.show()
    bbox.toggle()
    bbox.toggle()
    # Should toggle visibility

def test_update_outline_bounds(bbox):
    """Updates outline bounds"""
    bbox.update_bounds([0, 1, 0, 1, 0, 1])

def test_update_outline_bounds_from_nodes(bbox):
    """Calculates bounds from multiple scene nodes"""
    node1 = create_autospec(VisorSceneGraphNode, instance=True)
    node1.bounds = [0, 1, 0, 1, 0, 1]
    node2 = create_autospec(VisorSceneGraphNode, instance=True)
    node2.bounds = [2, 3, 2, 3, 2, 3]
    nodes = {1: node1, 2: node2}
    bbox.update_bounds_from_nodes(nodes)
    # Should update bounds to [0, 3, 0, 3, 0, 3]

def test_update_outline_bounds_from_nodes_empty(bbox):
    """Handles empty node dict correctly (hides actors)"""
    bbox.update_bounds_from_nodes({})
    # Should hide actors

def test_attach_and_detach_renderer(bbox):
    """Attaches and detaches renderer, verifies calls"""
    renderer = MagicMock()
    bbox.attach_to_renderer(renderer)
    bbox.detach_from_renderer(renderer)
    renderer.AddActor.assert_called()
    renderer.AddViewProp.assert_called()
    renderer.RemoveActor.assert_called()
    renderer.RemoveViewProp.assert_called()

def test_wasm_id_properties_raise_before_register(bbox):
    """Accessing WASM IDs before registering raises errors"""
    with pytest.raises(RuntimeError, match="register_with_local_view"):
        _ = bbox.box_algorithm_wasm_id
    with pytest.raises(RuntimeError, match="register_with_local_view"):
        _ = bbox.outline_wasm_actor_id
    with pytest.raises(RuntimeError, match="register_with_local_view"):
        _ = bbox.axes_wasm_actor_id

def test_register_with_local_view_sets_wasm_ids(bbox):
    """Registering with a local view sets WASM IDs correctly"""
    local_view = MagicMock()
    local_view.get_wasm_id.side_effect = [101, 102, 103]
    bbox.register_with_local_view(local_view)
    assert bbox.box_algorithm_wasm_id == 101
    assert bbox.outline_wasm_actor_id == 102
    assert bbox.axes_wasm_actor_id == 103

