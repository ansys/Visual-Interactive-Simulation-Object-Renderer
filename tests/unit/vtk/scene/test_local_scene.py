import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.models.runtime.vtk.renderer_annotation import (
    WasmRendererAnnotation,
    WasmWidgetHandles,
)
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo
from ansys.visor.viewer.vtk.scene.local_scene import VisorLocalScene


class _DummyPoints:
    """A lightweight dummy class to simulate VTK points for testing purposes."""
    def __init__(self, pts):
        self._pts = pts

    def GetPoint(self, i): # noqa: N802
        return tuple(self._pts[i])


class _DummyCell:
    """A lightweight dummy class to simulate VTK cells for testing purposes."""
    def __init__(self, points):
        self._points = points
        self._pts = _DummyPoints(points)

    def GetNumberOfPoints(self): # noqa: N802
        return len(self._points)

    def GetPoints(self): # noqa: N802
        return self._pts


class _DummyDataset:
    """A lightweight dummy class to simulate VTK datasets for testing purposes."""
    def __init__(self, cells):
        self._cells = cells

    def GetNumberOfCells(self): # noqa: N802
        return len(self._cells)

    def GetCell(self, idx): # noqa: N802
        if 0 <= idx < len(self._cells):
            return self._cells[idx]
        return None


class _DummyMapper:
    """A lightweight dummy class to simulate VTK mappers for testing purposes."""
    def __init__(self, dataset):
        self._dataset = dataset

    def GetInputDataObject(self, a, b): # noqa: N802
        return self._dataset


class _DummyActor:
    """A lightweight dummy class to simulate VTK actors for testing purposes."""
    def __init__(self, mapper):
        self._mapper = mapper

    def GetMapper(self): # noqa: N802
        return self._mapper


class _DummyActors:
    """A lightweight dummy class to simulate VTK actor collections for testing purposes."""
    def __init__(self, actors):
        self._actors = actors
        self._idx = 0

    def InitTraversal(self): # noqa: N802
        self._idx = 0

    def GetNextActor(self): # noqa: N802
        if self._idx >= len(self._actors):
            return None
        a = self._actors[self._idx]
        self._idx += 1
        return a


@pytest.fixture
def pipeline_instance():
    """Return a fully mocked VisorLocalScene instance with no VTK or Trame dependencies.

    All VTK infrastructure lives inside VisorLocalRenderer; we inject a plain
    MagicMock so the coordinator logic is exercised in isolation.
    """
    mock_server = MagicMock()
    mock_server.state = {}

    mock_renderer = MagicMock()  # stands in for IRenderer / VisorLocalRenderer
    # Real empty dict so SceneGraphStateBuilder's ``pipelines.get(node.id)``
    # returns None
    mock_renderer.pipelines = {}
    # build_renderer_annotation() must return a real
    # RendererAnnotation instance, not a MagicMock, since it is validated by
    # RuntimeVTKInfo.renderer_annotation.
    mock_renderer.build_renderer_annotation.return_value = WasmRendererAnnotation(
        nodes={},
        widgets=WasmWidgetHandles(
            orientation_widget_id=10,
            cross_section_plane_id=20,
            cross_section_plane_widget_id=21,
            cross_section_plane_representation_id=22,
            bounding_box_algorithm_id=30,
            bounding_box_outline_actor_id=31,
            bounding_box_axes_actor_id=32,
        ),
    )
    # frontend_ref_name must be a real str, since it is passed to
    # VisorFrontendBridge's constructor.
    mock_renderer.frontend_ref_name = "test-ref-name"

    with patch("ansys.visor.viewer.renderer.local_renderer.VisorLocalRenderer",
               return_value=mock_renderer), \
         patch("ansys.visor.viewer.vtk.scene.base.VisorSceneBase._initialize_dataset_registry",
               return_value=MagicMock()), \
         patch("ansys.visor.viewer.vtk.scene.base.VisorSceneBase._initialize_scene_graph",
               lambda self: setattr(self, "_scene_graph", MagicMock())), \
         patch("ansys.visor.viewer.vtk.scene.base.VisorStateMapper"), \
         patch("ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorFrontendBridge") as mock_bridge_cls:
        instance = VisorLocalScene(mock_server)
        # Exposed so tests can assert on how VisorFrontendBridge was constructed.
        instance._test_frontend_bridge_cls_mock = mock_bridge_cls

        # Mock dataset registry API
        instance._dataset_registry = MagicMock()
        instance._dataset_registry.datasets = {}
        instance._dataset_registry.unit = ""
        instance._dataset_registry._update_unit = MagicMock()
        instance._dataset_registry.get_sanitized_metadata_name = MagicMock(
            side_effect=lambda m: getattr(m, "name", "dataset")
        )
        instance._dataset_registry.add = MagicMock()
        instance._dataset_registry.remove = MagicMock()
        instance._dataset_registry.clear = MagicMock()
        instance._dataset_registry.list_info = MagicMock(return_value={})
        instance._dataset_registry.list_variables = MagicMock(return_value=[])
        instance._dataset_registry.update_variables = MagicMock()
        instance._dataset_registry.count = 0
        instance._dataset_registry.runtime_state_dict = {}

        # Mock scene graph with required APIs
        instance._scene_graph.load_dataset.return_value = 123
        instance._scene_graph.remove_dataset = MagicMock()
        instance._scene_graph.get_part_name_to_id_map = MagicMock(return_value={})
        instance._scene_graph.get_descendant_part_nodes.return_value = []
        instance._scene_graph.descendant_part_count.return_value = 0
        dataset_node = MagicMock()
        # Default: no leaves. Tests that exercise pipeline lifecycle override
        # this and configure ``instance._renderer.pipelines`` / assert on
        # ``instance._renderer.register_node`` / ``deregister_node``.
        dataset_node.get_descendant_part_nodes.return_value = []
        # Accept include_self kwarg (used by add_dataset's per-leaf register loop).
        instance._scene_graph.get_descendant_node.side_effect = (
            lambda dataset_id, include_self=False: dataset_node if dataset_id == 123 else None
        )
        instance._scene_graph.state = SceneGraphNodeInfo(
            id=1, name="root", isActorNode=False, isGroupNode=True, nodeType="group",
        )
        instance._scene_graph.is_part_node = False
        instance._scene_graph.is_group_node = True
        instance._scene_graph.children = []
        instance._scene_graph.Bounds = [0, 1, 0, 1, 0, 1]


        yield instance

        # Teardown: clear state to avoid leaks between tests
        try:
            instance._dataset_registry.clear()
        except Exception:
            pass
        instance._scene_graph = None


def dummy_dataset():
    """Return a dummy dataset for testing purposes."""
    return MagicMock()

def test_initialization(pipeline_instance):
    """Test pipeline initialization."""
    assert pipeline_instance is not None
    assert pipeline_instance._dataset_registry.datasets == {}
    assert pipeline_instance._dataset_registry.unit == ""
    assert pipeline_instance._renderer is not None
    assert pipeline_instance._renderer._render_window is not None
    assert pipeline_instance._renderer._render_window_interactor is not None
    assert pipeline_instance._server is not None
    assert pipeline_instance._scene_graph is not None

def test_init_passes_frontend_ref_name_to_bridge(pipeline_instance):
    """VisorFrontendBridge is constructed with the renderer's frontend_ref_name
    string, not the renderer or a view object."""
    mock_bridge_cls = pipeline_instance._test_frontend_bridge_cls_mock
    mock_bridge_cls.assert_called_once_with(
        pipeline_instance._server, "test-ref-name"
    )
    args, _ = mock_bridge_cls.call_args
    assert isinstance(args[1], str)


def test_cleanup_state(pipeline_instance):
    """Test that cleanup_state removes wasm_ids and wasm_ref_name from server state."""
    pipeline_instance._server.state["wasm_ids"] = {"dummy": 1}
    pipeline_instance._server.state["wasm_ref_name"] = {"dummy": 2}
    pipeline_instance.cleanup_state()
    assert "wasm_ids" not in pipeline_instance._server.state
    assert "wasm_ref_name" not in pipeline_instance._server.state

def test_update_widgets_without_scene_graph(pipeline_instance):
    """Test that update_widgets without scene graph raises RuntimeError."""
    pipeline_instance._scene_graph = None
    with pytest.raises(RuntimeError):
        pipeline_instance.update_widgets()

def test_reset_camera_no_scene_graph(pipeline_instance):
    """Test that resetting camera with no scene graph does not."""
    pipeline_instance._scene_graph = None
    pipeline_instance.reset_camera()  # Should not raise

def test_render(pipeline_instance):
    """Test render() does not raise."""
    dataset = dummy_dataset()
    metadata = ExtendedMetadata(name="test_model", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    pipeline_instance.render()  # Should not raise

def test_remove_dataset_error(pipeline_instance):
    """Test that remove_dataset raises RuntimeError."""
    pipeline_instance._scene_graph = None
    with pytest.raises(RuntimeError):
        pipeline_instance.remove_dataset(1)

def test_add_dataset_none_input(pipeline_instance):
    """Test that add_dataset with None input raises RuntimeError."""
    with pytest.raises(ValueError):
        pipeline_instance.add_dataset(None, ExtendedMetadata(name="test", unit="m"))

def test_visorscene_constructor_runtimeerror():
    """Test that VisorLocalScene constructor raises RuntimeError when encountering an error during initialization."""
    mock_server = MagicMock()
    mock_server.state = {}

    with patch("ansys.visor.viewer.renderer.local_renderer.VisorLocalRenderer",
               side_effect=RuntimeError("Init error")):
        with pytest.raises(RuntimeError, match="Failed to initialize VTK pipeline: Init error"):
            VisorLocalScene(mock_server)

def test_get_scene_details_none_scene_graph(pipeline_instance):
    """Test that get_scene_details raises RuntimeError when scene graph is None."""
    pipeline_instance._scene_graph = None
    with patch.object(pipeline_instance, "_initialize_scene_graph", side_effect=RuntimeError("Scene graph is not initialized.")):
        with pytest.raises(RuntimeError, match="Scene graph is not initialized."):
            pipeline_instance.get_scene_details()

def test_clear_hits_remove_actor(pipeline_instance):
    """clear() delegates to the renderer's deregister_all()."""
    pipeline_instance.clear()
    pipeline_instance._renderer.deregister_all.assert_called_once()

def test_populate_scene_happy_case(pipeline_instance):
    """populate_scene delegates the widget refresh via update_widgets."""
    # After I5, actor attach happens per-leaf at add_dataset time; populate_scene
    # is only responsible for refreshing widget bounds/count via update_widgets.
    pipeline_instance.update_widgets = MagicMock()
    pipeline_instance.populate_scene()
    pipeline_instance.update_widgets.assert_called_once()

def test_populate_scene_triggers_initialize_scene_graph(pipeline_instance):
    """Test that populate_scene triggers _initialize_scene_graph."""
    pipeline_instance._scene_graph = None
    with patch.object(pipeline_instance, "_initialize_scene_graph") as mock_init_scene_graph:
        # Patch update_widgets to avoid side effects
        pipeline_instance.update_widgets = MagicMock()
        pipeline_instance.populate_scene()
        mock_init_scene_graph.assert_called_once()

def test_add_dataset_triggers_initialize_scene_graph(pipeline_instance):
    """Test that add_dataset triggers _initialize_scene_graph."""
    pipeline_instance._scene_graph = None
    dataset = dummy_dataset()
    metadata = ExtendedMetadata(name="test_model", unit="m")
    with patch.object(pipeline_instance, "_initialize_scene_graph") as mock_init_scene_graph:
        def init_scene_graph_side_effect():
            pipeline_instance._scene_graph = MagicMock()
        mock_init_scene_graph.side_effect = init_scene_graph_side_effect
        pipeline_instance.add_dataset(dataset, metadata)
        mock_init_scene_graph.assert_called_once()

def test_render_happy_case(pipeline_instance):
    """Test render() delegates to the renderer backend."""
    dataset = dummy_dataset()
    metadata = ExtendedMetadata(name="test_model", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    pipeline_instance.render()
    pipeline_instance._renderer.render.assert_called_once()

def test_reset_camera_happy_case(pipeline_instance):
    """Test reset_camera() delegates to the renderer with scene-graph bounds."""
    dataset = dummy_dataset()
    metadata = ExtendedMetadata(name="test_model", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)
    pipeline_instance.reset_camera()
    pipeline_instance._renderer.reset_camera.assert_called_once_with(
        pipeline_instance._scene_graph.bounds
    )

import contextlib


def make_fully_mocked_visorscene():
    """Helper function to create a fully mocked VisorLocalScene instance for testing purposes."""
    mock_server = MagicMock()
    mock_server.state = {}

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch("ansys.visor.viewer.renderer.local_renderer.VisorLocalRenderer",
                  return_value=MagicMock())
        )
        # _initialize_dataset_registry is NOT patched: the real VisorDatasetRegistry
        # is used so that registry.remove() actually mutates .datasets (asserted below).
        stack.enter_context(
            patch("ansys.visor.viewer.vtk.scene.base.VisorSceneBase._initialize_scene_graph",
                  lambda self: setattr(self, "_scene_graph", MagicMock()))
        )
        stack.enter_context(
            patch("ansys.visor.viewer.vtk.scene.base.VisorStateMapper")
        )
        stack.enter_context(
            patch("ansys.visor.viewer.vtk.scene.visor_frontend_bridge.VisorFrontendBridge")
        )
        instance = VisorLocalScene(mock_server)
        instance._scene_graph = MagicMock()
        return instance


def test_add_dataset_registers_single_leaf_with_renderer(pipeline_instance):
    """add_dataset delegates each leaf pipeline to renderer.register_node.

    After I5, per-leaf pipeline construction and actor-attach are owned by
    the renderer's register_node; the coordinator invokes it once per leaf
    at add_dataset time.
    """
    leaf = MagicMock()
    leaf.id = 1
    leaf.dataset = MagicMock(name="leaf.dataset")
    dataset_node = pipeline_instance._scene_graph.get_descendant_node(123)
    dataset_node.get_descendant_part_nodes.return_value = [leaf]

    dataset = dummy_dataset()
    metadata = ExtendedMetadata(name="test_model", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)

    pipeline_instance._renderer.register_node.assert_called_once_with(leaf, leaf.dataset)


def test_add_dataset_registers_multiple_leaves_with_renderer(pipeline_instance):
    """add_dataset calls renderer.register_node for every leaf in the subtree."""
    leaf1 = MagicMock()
    leaf1.id = 1
    leaf1.dataset = MagicMock(name="leaf1.dataset")
    leaf2 = MagicMock()
    leaf2.id = 2
    leaf2.dataset = MagicMock(name="leaf2.dataset")
    dataset_node = pipeline_instance._scene_graph.get_descendant_node(123)
    dataset_node.get_descendant_part_nodes.return_value = [leaf1, leaf2]

    dataset = dummy_dataset()
    metadata = ExtendedMetadata(name="test_model", unit="m")
    pipeline_instance.add_dataset(dataset, metadata)

    assert pipeline_instance._renderer.register_node.call_count == 2
    registered = [c[0] for c in pipeline_instance._renderer.register_node.call_args_list]
    assert (leaf1, leaf1.dataset) in registered
    assert (leaf2, leaf2.dataset) in registered


def test_populate_scene_raises_when_scene_graph_not_initialized(pipeline_instance):
    """populate_scene raises via update_widgets when the scene graph is uninitialized.

    After I5, populate_scene no longer attaches actors (that happens per-leaf
    at add_dataset time); it only refreshes widgets.  The scene-graph guard
    now lives inside update_widgets.
    """
    # Arrange: ensure scene graph is None and patch initialize to a no-op so it does not set it
    pipeline_instance._scene_graph = None

    with patch.object(pipeline_instance, "_initialize_scene_graph", return_value=None):
        # Act / Assert: calling the public method should propagate the RuntimeError from the internal path
        with pytest.raises(RuntimeError, match="Scene graph has not been initialized, cannot reset widgets and camera."):
            pipeline_instance.populate_scene()


def test_build_scene_graph_state_does_not_stamp_wasm_ids(pipeline_instance):
    """
    _build_scene_graph_state no longer stamps renderer handles; it returns
    pure scene-graph structure. Stamping now happens separately, in
    get_scene_details, from the renderer's annotation.
    """
    from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo

    # A real leaf-info object; the builder must leave it unstamped.
    leaf_info = SceneGraphNodeInfo(
        id=555, name="p", isActorNode=True, isGroupNode=False, nodeType="vtkPolyData",
    )
    root_info = SceneGraphNodeInfo(
        id=1, name="root", isActorNode=False, isGroupNode=True, nodeType="root",
    )

    leaf_node = MagicMock()
    leaf_node.id = 555
    leaf_node.is_part_node = True
    leaf_node.is_group_node = False
    leaf_node.state = leaf_info
    pipeline_instance._scene_graph.is_part_node = False
    pipeline_instance._scene_graph.is_group_node = True
    pipeline_instance._scene_graph.state = root_info
    pipeline_instance._scene_graph.children = [leaf_node]

    out = pipeline_instance._build_scene_graph_state()

    assert out is root_info
    assert len(out.children) == 1
    stamped = out.children[0]
    assert stamped is leaf_info

def _extract_name_from_dataset_value(val):
    """Helper function to extract the name from a dataset value, which may be an object with
    a .name attribute or a dict with a "name" key.
    Returns the name if found, otherwise returns None.
    """
    # The pipeline stores dataset metadata either as an object with .name or as a dict
    if hasattr(val, "name"):
        return val.name
    if isinstance(val, dict):
        return val.get("name")
    return None

def test_remove_dataset_not_found_logs_and_raises(pipeline_instance):
    """
    When the scene graph does not contain the dataset id, remove_dataset()
    should log an error and raise a ValueError with the expected message.
    Only the public method is called and we mock the module logger.
    """
    missing_id = 999
    # Ensure scene graph will report the node as missing
    pipeline_instance._scene_graph.get_descendant_node.return_value = None
    pipeline_instance._scene_graph.remove_dataset = MagicMock()

    with patch("ansys.visor.viewer.vtk.scene.base.logger") as mock_logger:
        with pytest.raises(ValueError, match=f"Dataset with id {missing_id} not found in scene graph."):
            pipeline_instance.remove_dataset(missing_id)

        mock_logger.error.assert_called_once_with(f"Dataset with id {missing_id} not found in scene graph.")
        pipeline_instance._scene_graph.remove_dataset.assert_not_called()

def test_remove_dataset_calls_renderer_remove_actor():
    """remove_dataset deregisters each subtree leaf via the renderer."""
    instance = make_fully_mocked_visorscene()
    dataset_id = 42
    leaf_node = MagicMock(name="leaf_node")
    leaf_node.id = 555
    subtree = MagicMock(name="scene_subtree")
    subtree.get_descendant_part_nodes.return_value = [leaf_node]

    instance._scene_graph.get_descendant_node.return_value = subtree
    instance._scene_graph.remove_dataset = MagicMock()
    instance._dataset_registry.datasets = {dataset_id: MagicMock()}

    instance.remove_dataset(dataset_id)

    # remove_dataset iterates the subtree's leaves and delegates each to
    # renderer.deregister_node.  The renderer owns the pipeline registry;
    # coordinator no longer holds a copy.
    instance._renderer.deregister_node.assert_called_once_with(leaf_node.id)
    instance._scene_graph.remove_dataset.assert_called_once_with(dataset_id)
    assert dataset_id not in instance._dataset_registry.datasets



def test_dataset_count_delegates(pipeline_instance):
    """Test that dataset_count delegates."""
    pipeline_instance._dataset_registry.count = 5
    assert pipeline_instance.dataset_count == 5


def test_list_dataset_state_info_delegates(pipeline_instance):
    """Test that list_all_dataset_info delegates."""
    expected = {123: {"name": "foo"}}
    pipeline_instance._dataset_registry.list_info.return_value = expected
    assert pipeline_instance.list_all_dataset_info() == expected
    pipeline_instance._dataset_registry.list_info.assert_called_once()


def test_get_scene_details_returns_model(pipeline_instance):
    """Test that get_scene_details returns model."""
    pipeline_instance._dataset_registry.unit = "m"
    pipeline_instance._dataset_registry.dictionaries = {}
    pipeline_instance._dataset_registry.runtime_state_dict = {}

    details = pipeline_instance.get_scene_details()

    assert details.app_state.ui.dark_theme == pipeline_instance.dark_mode
    assert details.app_state.scene.unit == "m"
    assert details.app_state.scene.dataset_states == {}
    assert details.vtk_info.renderer_annotation.widgets.orientation_widget_id == 10
    assert details.vtk_info.renderer_annotation.widgets.cross_section_plane_id == 20
    assert details.vtk_info.renderer_annotation.widgets.cross_section_plane_widget_id == 21
    assert (
        details.vtk_info.renderer_annotation.widgets.cross_section_plane_representation_id == 22
    )
    assert details.vtk_info.renderer_annotation.widgets.bounding_box_algorithm_id == 30
    assert details.vtk_info.renderer_annotation.widgets.bounding_box_outline_actor_id == 31
    assert details.vtk_info.renderer_annotation.widgets.bounding_box_axes_actor_id == 32


def test_get_scene_details_json_is_valid(pipeline_instance):
    """Test that get_scene_details_json is valid."""
    # Ensure unit and state are simple, serializable values
    pipeline_instance._dataset_registry.unit = "m"
    pipeline_instance._dataset_registry.dictionaries = {}
    pipeline_instance._dataset_registry.runtime_state_dict = {}


    payload = json.loads(pipeline_instance.get_scene_details_json())

    # Top-level fields
    assert payload["appState"]["scene"]["unit"] == "m"
    assert payload["appState"]["ui"]["darkTheme"] == pipeline_instance.dark_mode

    # Widget IDs are ints, now under rendererAnnotation.widgets
    widgets = payload["vtkInfo"]["rendererAnnotation"]["widgets"]
    assert widgets["orientationWidgetId"] == 10
    assert widgets["crossSectionPlaneId"] == 20
    assert widgets["crossSectionPlaneWidgetId"] == 21
    assert widgets["crossSectionPlaneRepresentationId"] == 22
    assert widgets["boundingBoxAlgorithmId"] == 30
    assert widgets["boundingBoxOutlineActorId"] == 31
    assert widgets["boundingBoxAxesActorId"] == 32

    # Scene graph and state presence
    assert "sceneGraph" in payload["vtkInfo"]
    dataset_dictionaries = payload["appState"]["scene"]["datasetStates"]
    assert dataset_dictionaries == {}


def test_cleanup_state_removes_keys(pipeline_instance):
    """Test that cleanup_state removes keys."""
    pipeline_instance._server.state["wasm_ids"] = {"x": 1}
    pipeline_instance._server.state["wasm_ref_name"] = {"y": 2}

    pipeline_instance.cleanup_state()

    assert "wasm_ids" not in pipeline_instance._server.state
    assert "wasm_ref_name" not in pipeline_instance._server.state


def test_clear_resets_scene_and_delegates_to_registry(pipeline_instance):
    """clear() delegates to the renderer's deregister_all() and resets scene."""
    pipeline_instance.clear()

    assert pipeline_instance._dataset_registry.clear.call_count == 1
    pipeline_instance._renderer.deregister_all.assert_called_once()
    assert pipeline_instance._scene_graph is None



def test_populate_scene_calls_update_widgets(pipeline_instance):
    """Test that populate_scene() calls update_widgets."""
    # No part nodes in graph, just ensure update_widgets is called.
    pipeline_instance._scene_graph.get_descendant_part_nodes.return_value = []
    spy = MagicMock()
    pipeline_instance.update_widgets = spy

    pipeline_instance.populate_scene()

    spy.assert_called_once()


def test_update_widgets_calls_internal_helpers(pipeline_instance):
    """Test that update_widgets calls internal helpers."""
    pipeline_instance._update_widget_bounds = MagicMock()
    pipeline_instance._update_actor_count = MagicMock()

    pipeline_instance.update_widgets()

    pipeline_instance._update_widget_bounds.assert_called_once()
    pipeline_instance._update_actor_count.assert_called_once()


def test_update_widgets_raises_without_scene_graph(pipeline_instance):
    """Test that update_widgets raises without scene graph."""
    pipeline_instance._scene_graph = None
    with pytest.raises(RuntimeError):
        pipeline_instance.update_widgets()


def test_add_dataset_delegates_and_builds_state(pipeline_instance):
    """Test that add_dataset delegates and builds state."""
    dataset = dummy_dataset()
    metadata = SimpleNamespace(
        name="test_model",
        unit="m",
        file_path=None,
        metadata_path=None,
        state=SimpleNamespace(partProperties={}),
    )

    pipeline_instance.add_dataset(dataset, metadata)

    # Assert on public behavior: add() was called with correct arguments
    pipeline_instance._dataset_registry.add.assert_called_once()
    args, _ = pipeline_instance._dataset_registry.add.call_args
    ds_id, ds_name, ds_input, ds_part_name_to_id, ds_metadata = args

    assert ds_id == 123  # from scene_graph.load_dataset mock
    assert ds_name == "test_model"
    assert ds_input is dataset
    assert ds_part_name_to_id == {}  # from scene_graph.get_part_name_to_id_map mock
    assert ds_metadata is metadata


def test_remove_dataset_success_path(pipeline_instance):
    """remove_dataset deregisters each subtree leaf via the renderer."""
    # Configure the dataset-node subtree to expose two leaves.  The renderer
    # owns the pipeline registry post-I5, so the coordinator does not seed it.
    leaf1 = MagicMock()
    leaf1.id = 501
    leaf2 = MagicMock()
    leaf2.id = 502
    dataset_node = pipeline_instance._scene_graph.get_descendant_node(123)
    dataset_node.get_descendant_part_nodes.return_value = [leaf1, leaf2]

    pipeline_instance.remove_dataset(123)

    assert pipeline_instance._renderer.deregister_node.call_count == 2
    pipeline_instance._renderer.deregister_node.assert_any_call(leaf1.id)
    pipeline_instance._renderer.deregister_node.assert_any_call(leaf2.id)

    pipeline_instance._scene_graph.remove_dataset.assert_called_once_with(123)
    pipeline_instance._dataset_registry.remove.assert_called_once_with(123)


def test_remove_dataset_raises_when_not_found(pipeline_instance):
    """Test that remove_dataset raises when not found."""
    with pytest.raises(ValueError):
        pipeline_instance.remove_dataset(999)
    pipeline_instance._dataset_registry.remove.assert_not_called()


def test_list_variables_for_dataset_delegates(pipeline_instance):
    """Test that list_variables_for_dataset delegates."""
    expected = [MagicMock()]
    pipeline_instance._dataset_registry.list_variables.return_value = expected
    result = pipeline_instance.list_variables_for_dataset(123)
    assert result == expected
    pipeline_instance._dataset_registry.list_variables.assert_called_once_with(123)


def test_update_variables_for_dataset_triggers_updates_and_render(pipeline_instance):
    """Test that update_variables_for_dataset triggers updates and render."""
    vars_payload = ["dummy"]
    render_spy = MagicMock()
    pipeline_instance.render = render_spy

    pipeline_instance.update_variables_for_dataset(123, vars_payload)

    pipeline_instance._dataset_registry.update_variables.assert_called_once_with(123, vars_payload)
    dataset_node = pipeline_instance._scene_graph.get_descendant_node(123)
    dataset_node.refresh_descendant_variable_metadata.assert_called_once_with(include_self=True)
    render_spy.assert_called_once()


def test_render_triggers_window_and_view(pipeline_instance):
    """Test that render() delegates to the renderer backend."""
    pipeline_instance.render()
    pipeline_instance._renderer.render.assert_called_once()


def test_reset_camera_with_scene_graph(pipeline_instance):
    """Test reset_camera() delegates to the renderer with scene-graph bounds."""
    pipeline_instance.reset_camera()
    pipeline_instance._renderer.reset_camera.assert_called_once_with(pipeline_instance._scene_graph.bounds)


def test_reset_camera_no_scene_graph_noop(pipeline_instance):
    """Test that reset_camera when no scene graph results in no-op."""
    pipeline_instance._renderer.reset_camera.reset_mock()
    pipeline_instance._scene_graph = None

    pipeline_instance.reset_camera()

    pipeline_instance._renderer.reset_camera.assert_not_called()


# ---------------------------------------------------------------------------
# Tests moved from tests/unit/app/test_finalize_scene.py
# ---------------------------------------------------------------------------


from ansys.visor.viewer.vtk.scene.base import VisorSceneBase


class DummyScene(VisorSceneBase):
    """A minimal subclass of VisorSceneBase that avoids full VTK initialization.

    We override heavy initialization and supply only the attributes used by
    `finalize_scene` so tests can run without VTK/trame.
    """

    def __init__(self):
        # do not call super().__init__ to avoid VTK setup
        # set only the attributes used by finalize_scene
        self._dataset_registry = SimpleNamespace(count=0)
        self._populate_called = False
        self._reset_called = False
        self._render_called = False

    # Implement the two abstract hooks with no-op stubs so the class is
    # instantiable.  These stubs are never called by finalize_scene tests.
    async def _get_runtime_state_async(self, timeout: float):
        return None

    def _apply_runtime_state_to_render(self, runtime_app_state) -> None:
        pass

    def populate_scene(self):
        self._populate_called = True

    def reset_camera(self):
        self._reset_called = True

    def render(self):
        self._render_called = True


def test_finalize_scene_resets_camera_when_one_dataset():
    """Test that finalize_scene resets camera when one dataset is loaded in scene."""
    s = DummyScene()
    s._dataset_registry.count = 1

    s.finalize_scene()

    assert s._populate_called is True
    assert s._reset_called is True
    assert s._render_called is True


def test_finalize_scene_skips_reset_when_flag_true():
    """Test that finalize_scene skips reset() when flag is true."""
    s = DummyScene()
    s._dataset_registry.count = 1

    s.finalize_scene(skip_reset_camera=True)

    assert s._populate_called is True
    assert s._reset_called is False
    assert s._render_called is True


def test_finalize_scene_no_reset_when_multiple_datasets():
    """Test that finalize_scene does not reset camera when multiple datasets."""
    s = DummyScene()
    s._dataset_registry.count = 2

    s.finalize_scene()

    assert s._populate_called is True
    # with more than one dataset, camera should not be reset
    assert s._reset_called is False
    assert s._render_called is True

