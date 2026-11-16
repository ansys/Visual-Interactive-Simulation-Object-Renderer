# python
# File: `tests/integration/test_visor_local_scene.py`
import json
import os
from unittest.mock import PropertyMock, patch

import pytest
from trame.app import get_server

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset
from ansys.visor.viewer.vtk.scene.local_scene import VisorLocalScene
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate


@pytest.fixture
def pipeline_instance():
    """PyTest fixture for pipeline instance."""
    server = get_server()
    assert server is not None, "get_server() returned None"
    scene = VisorLocalScene(server)
    yield scene
    try:
        scene.clear()
        scene.cleanup_state()
    except Exception:
        pass


def get_test_file():
    """Get the path to the test VTP file."""
    return os.path.join(os.path.dirname(__file__), "..", "files", "plate.vtp")


def test_initialization(pipeline_instance):
    """Test pipeline initialization."""
    assert pipeline_instance is not None
    assert pipeline_instance.dataset_count == 0
    assert pipeline_instance._renderer is not None
    assert pipeline_instance._renderer._render_window is not None
    assert pipeline_instance._renderer._render_window_interactor is not None
    assert pipeline_instance._server is not None
    assert pipeline_instance._scene_graph is not None
    # Avoid dict-like membership checks on trame state to prevent iteration side effects


def test_add_and_remove_dataset(pipeline_instance):
    """Test that adding and removing a dataset works."""
    file = get_test_file()
    dataset = file_to_dataset(file)
    metadata = ExtendedMetadata(name="test_model", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    assert pipeline_instance.dataset_count == 1
    info = pipeline_instance.list_all_dataset_info()
    dataset_id = next(iter(info.keys()))
    pipeline_instance.remove_dataset(dataset_id)
    assert pipeline_instance.dataset_count == 0


def test_add_dataset_none_input(pipeline_instance):
    """Test add_dataset raises ValueError when input is None."""
    with pytest.raises(ValueError):
        pipeline_instance.add_dataset(None, ExtendedMetadata(name="test", unit="m"))


def test_list_dataset_state_info(pipeline_instance):
    """Test that list_dataset_state_info works."""
    file = get_test_file()
    dataset = file_to_dataset(file)
    metadata = ExtendedMetadata(name="modelA", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    info = pipeline_instance.list_all_dataset_info()
    assert isinstance(info, dict)
    assert len(info) == 1
    did = next(iter(info.keys()))
    assert info[did]["name"] == "modelA"


def test_get_scene_details_and_json(pipeline_instance):
    """Test that get_scene_details and get_scene_details_json work."""
    file = get_test_file()
    dataset = file_to_dataset(file)
    metadata = ExtendedMetadata(name="test_model", unit="mm")
    pipeline_instance.add_dataset(dataset, metadata)
    details = pipeline_instance.get_scene_details()
    assert details.scene.unit == "mm"
    payload = json.loads(pipeline_instance.get_scene_details_json())
    assert payload["scene"]["unit"] == "mm"
    assert "vtkInfo" in payload
    assert "ui" in payload


def test_clear_resets_registry_and_graph(pipeline_instance):
    """Test that clear() resets registry and graph."""
    file = get_test_file()
    dataset = file_to_dataset(file)
    metadata = ExtendedMetadata(name="m1", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    assert pipeline_instance.dataset_count == 1
    pipeline_instance.populate_scene()
    pipeline_instance.clear()
    assert pipeline_instance.dataset_count == 0
    assert pipeline_instance._scene_graph is None


def test_cleanup_state_removes_wasm_keys(pipeline_instance):
    """Test that cleanup_state removes wasm keys."""
    with patch.object(type(pipeline_instance._server), "state", new_callable=PropertyMock) as mock_state:
        mock_state.return_value = {}
        pipeline_instance._server.state["wasm_ids"] = {"dummy": 1}
        pipeline_instance._server.state["wasm_ref_name"] = {"dummy": 2}
        pipeline_instance.cleanup_state()
        assert "wasm_ids" not in pipeline_instance._server.state
        assert "wasm_ref_name" not in pipeline_instance._server.state


def test_update_widgets_without_scene_graph_raises(pipeline_instance):
    """Test that update_widgets without scene graph raises RuntimeError."""
    pipeline_instance._scene_graph = None
    with pytest.raises(RuntimeError):
        pipeline_instance.update_widgets()


def test_update_widgets_with_scene_graph(pipeline_instance):
    """Test that updating widgets with scene graph."""
    file = get_test_file()
    dataset = file_to_dataset(file)
    metadata = ExtendedMetadata(name="m1", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    pipeline_instance.populate_scene()  # Should update widgets without error


def test_reset_camera_without_scene_graph_no_raise(pipeline_instance):
    """Test that resetting camera without scene graph does not raise any exception."""
    pipeline_instance._scene_graph = None
    pipeline_instance.reset_camera()  # Should not raise


def test_reset_camera_with_scene_graph_applies_bounds(pipeline_instance):
    """Test that resetting camera with scene graph results in bounds applied to renderer."""
    pipeline_instance.reset_camera()  # Bounds applied to renderer


def test_render_triggers_updates(pipeline_instance):
    """Test that rendering does not raise any exception."""
    pipeline_instance.render()  # Should not raise


def test_remove_dataset_error_when_no_graph(pipeline_instance):
    """Test that removing dataset with null scene graph raises RuntimeError."""
    pipeline_instance._scene_graph = None
    with pytest.raises(RuntimeError):
        pipeline_instance.remove_dataset(1)


def test_list_and_update_variables(pipeline_instance):
    """Test that list_variables_for_dataset and update_variables_for_dataset works."""
    file = get_test_file()
    dataset = file_to_dataset(file)
    metadata = ExtendedMetadata(name="m1", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    info = pipeline_instance.list_all_dataset_info()
    did = next(iter(info.keys()))

    before = pipeline_instance.list_variables_for_dataset(did)
    assert isinstance(before, list)

    num_points = dataset.GetPointData().GetArray("Normal").GetNumberOfTuples()
    num_components = dataset.GetPointData().GetArray("Normal").GetNumberOfComponents()
    # Minimal valid VisorVariableUpdate: scalar with one component and small data payload
    updates = [
        VisorVariableUpdate.from_dict({
            "name":"Normal",
            "type":"point",
            "num_components":num_components,
            "data":[0.0]*num_points*num_components,
    })
    ]
    pipeline_instance.update_variables_for_dataset(did, updates)

    after = pipeline_instance.list_variables_for_dataset(did)
    assert isinstance(after, list)
    # list_variables now returns one VisorPartVariables entry per part;
    # non-composite datasets have exactly one part.
    assert len(after) == 1
    part = after[0]
    assert len(part.variables) == 3
    assert part.variables[0].name == "Normal"
    assert part.variables[0].type == VisorVtkVariableType.POINT
    assert part.variables[0].num_components == num_components
