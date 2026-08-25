from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from vtkmodules.vtkCommonDataModel import vtkPolyData

from ansys.visor.viewer.app.visor_vtk import (
    VisorVTK,
    require_input_is_not_none,
    require_server_off,
    require_server_on,
    validate_input_metadata_types,
)
from ansys.visor.viewer.core.errors import ServerNotStartedError
from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1


@pytest.fixture
def iface():
    """Provide a VisorVTK instance with mocked dependencies."""
    with patch("ansys.visor.viewer.app.visor_vtk.TrameServerManager") as mock_mgr, \
         patch("ansys.visor.viewer.app.visor_vtk_local.LocalApp"), \
         patch("ansys.visor.viewer.app.visor_vtk_local.VisorLocalScene") as mock_scene:
        mock_mgr_inst = MagicMock()
        mock_mgr_inst.running = True
        mock_mgr_inst.state.model_dump.return_value = {"foo": "bar"}
        mock_mgr_inst._server = MagicMock()
        mock_mgr_inst.health = True
        mock_scene_inst = MagicMock()
        mock_scene_inst.datasets = {}
        mock_scene.return_value = mock_scene_inst
        mock_mgr.return_value = mock_mgr_inst
        return VisorVTK()

class DummyIface(VisorVTK):
    @validate_input_metadata_types
    def test_input_metadata_types(self, input=None, metadata=None):
        """Verify that metadata validation succeeds for valid inputs."""
        return "ok"

    @require_input_is_not_none
    def test_input_is_not_none(self, input=None, metadata=None):
        """Verify that non-None inputs pass validation."""
        return "ok"

    @require_server_off
    def test_require_server_off(self):
        """Verify that execution succeeds when the server is not running."""
        return "ok"

    @require_server_on
    def test_require_server_on(self):
        """Verify that execution succeeds when the server is running."""
        return "ok"

@pytest.fixture
def dummy_iface():
    """Provide a DummyIface instance with mocked dependencies."""
    with patch("ansys.visor.viewer.app.visor_vtk.TrameServerManager") as mock_mgr, \
         patch("ansys.visor.viewer.app.visor_vtk_local.LocalApp"), \
         patch("ansys.visor.viewer.app.visor_vtk_local.VisorLocalScene") as mock_scene:
        mock_mgr_inst = MagicMock()
        type(mock_mgr_inst).running = PropertyMock(return_value=True)
        mock_mgr_inst.state.model_dump.return_value = {"foo": "bar"}
        mock_mgr_inst._server = MagicMock()
        mock_scene_inst = MagicMock()
        mock_scene_inst.datasets = {}
        mock_scene.return_value = mock_scene_inst
        mock_mgr.return_value = mock_mgr_inst
        return DummyIface()


def test_running_property(iface):
    """Verify that the running property reflects the server state."""
    iface._server_manager.running = True
    assert iface.running is True
    iface._server_manager.running = False
    assert iface.running is False

def test_server_property(iface):
    """Verify that the server property returns the managed server."""
    assert iface.server is iface._server_manager.server

def test_dataset_count_property(iface):
    """Verify that the dataset count property delegates to the scene."""
    type(iface._scene).dataset_count = PropertyMock(return_value=2)
    assert iface.dataset_count == 2

def test_start_calls_prepare_and_render_and_server_manager(iface):
    """Verify that start prepares the scene and starts the server."""
    iface._server_manager.running = False
    iface._prepare_and_render_scene = MagicMock()
    iface._server_manager.start = MagicMock()
    iface.start("input", "metadata", timeout=5, blocking=True)
    iface._prepare_and_render_scene.assert_called_once()
    iface._server_manager.start.assert_called_once_with(5, True)

def test_stop_calls_server_manager(iface):
    """Verify that stop delegates to the server manager."""
    iface._server_manager.running = True
    iface._server_manager.stop = MagicMock()
    iface.stop()
    iface._server_manager.stop.assert_called_once()

def test_update_clears_and_prepares_scene(iface):
    """Verify that update clears the scene and reloads data."""
    iface._server_manager.running = True
    iface._scene.clear = MagicMock()
    iface._prepare_and_render_scene = MagicMock()
    iface.update("input", "metadata")
    iface._scene.clear.assert_called_once()
    iface._prepare_and_render_scene.assert_called_once()

def test_add_dataset_calls_prepare_and_render(iface):
    """Verify that adding a dataset prepares and renders the scene."""
    iface._prepare_and_render_scene = MagicMock()
    iface.add_dataset("input", "metadata")
    iface._prepare_and_render_scene.assert_called_once()

def test_remove_dataset_clears_if_no_datasets(iface):
    """Verify that removing the last dataset clears the scene."""
    # Mock that there's currently 1 dataset, which will become 0 after removal
    type(iface._scene).dataset_count = PropertyMock(return_value=1)

    iface._scene.remove_dataset = MagicMock()
    iface.clear = MagicMock()
    iface._scene.update_widgets = MagicMock()
    iface._scene.render = MagicMock()

    # Simulate that after removal, dataset_count becomes 0
    def side_effect_remove(dataset_id):
        type(iface._scene).dataset_count = PropertyMock(return_value=0)

    iface._scene.remove_dataset.side_effect = side_effect_remove

    # Remove the dataset - this should trigger clear since count will be 0 after removal
    iface.remove_dataset(1)

    # Assertions
    iface._scene.remove_dataset.assert_called_once_with(1)
    iface.clear.assert_called_once()

def test_remove_dataset_updates_widgets_and_renders(iface):
    """Verify that removing a dataset updates widgets and triggers a render."""
    iface._scene.remove_dataset = MagicMock()
    iface._scene.datasets = {1: MagicMock()}
    iface.clear = MagicMock()
    iface._scene.update_widgets = MagicMock()
    iface._scene.render = MagicMock()
    iface.remove_dataset(1)
    iface._scene.update_widgets.assert_called_once()
    iface._scene.render.assert_called_once()

def test_list_datasets_delegates_to_scene(iface):
    """Verify that dataset listing is delegated to the scene."""
    # Arrange
    expected_result = {1: {"name": "foo"}, 2: {"name": "bar"}}
    iface._scene.list_all_dataset_info = MagicMock(return_value=expected_result)

    # Act
    result = iface.list_datasets()

    # Assert
    iface._scene.list_all_dataset_info.assert_called_once()
    assert result == expected_result

def test_clear_calls_scene_methods(iface):
    """Verify that clear resets and finalizes the scene."""
    iface._scene.clear = MagicMock()
    iface._scene.finalize_scene = MagicMock()
    iface.clear()
    iface._scene.clear.assert_called_once()
    iface._scene.finalize_scene.assert_called_once()

def test_save_state_writes_json(tmp_path, iface):
    """Verify that save_state writes viewer state to JSON."""
    import json
    from unittest.mock import MagicMock

    # Arrange: fake state object returned by the (frontend-driven) get_state call
    state = MagicMock()
    state.model_dump_json.return_value = json.dumps({"foo": "bar"})

    async def _get_state(*args, **kwargs):
        return state

    iface._scene.get_state = _get_state
    iface._server_manager.running = True

    # Act
    import asyncio
    asyncio.run(iface.save_state(str(tmp_path)))

    # Assert
    state_file = tmp_path / "visor.json"
    assert state_file.exists()
    with open(state_file) as f:
        data = json.load(f)
    assert data == {"foo": "bar"}

def test_save_state_writes_dataset_snapshots(tmp_path, iface):
    """Verify that dirty datasets are written as snapshots."""
    import asyncio
    from unittest.mock import MagicMock

    # Arrange: two dirty mock datasets
    ds1 = MagicMock()
    ds1.name = "model_a"
    ds1.data = MagicMock()
    ds1.is_dirty = True
    ds2 = MagicMock()
    ds2.name = "model_b"
    ds2.data = MagicMock()
    ds2.is_dirty = True
    iface._scene.datasets = {1: ds1, 2: ds2}

    state = MagicMock()
    state.scene.dataset_states = {}

    async def _get_state(*args, **kwargs):
        return state

    iface._scene.get_state = _get_state
    iface._server_manager.running = True
    iface._file_io.write_dataset = MagicMock()
    iface._file_io.write_state = MagicMock()

    asyncio.run(iface.save_state(str(tmp_path)))

    # One write_dataset call per dirty dataset
    assert iface._file_io.write_dataset.call_count == 2
    called_datasets = {call.args[1] for call in iface._file_io.write_dataset.call_args_list}
    assert ds1.data in called_datasets
    assert ds2.data in called_datasets
    # Datasets should be marked clean after a successful write
    ds1.mark_clean.assert_called_once()
    ds2.mark_clean.assert_called_once()

def test_save_state_skips_clean_datasets(tmp_path, iface):
    """Verify that clean datasets are not written to disk."""
    import asyncio
    from unittest.mock import MagicMock

    # Arrange: one dirty, one clean
    ds_dirty = MagicMock()
    ds_dirty.name = "model_a"
    ds_dirty.data = MagicMock()
    ds_dirty.is_dirty = True
    ds_clean = MagicMock()
    ds_clean.name = "model_b"
    ds_clean.data = MagicMock()
    ds_clean.is_dirty = False
    iface._scene.datasets = {1: ds_dirty, 2: ds_clean}

    state = MagicMock()
    state.scene.dataset_states = {}

    async def _get_state(*args, **kwargs):
        return state

    iface._scene.get_state = _get_state
    iface._server_manager.running = True
    iface._file_io.write_dataset = MagicMock()
    iface._file_io.write_state = MagicMock()

    asyncio.run(iface.save_state(str(tmp_path)))

    # Only the dirty dataset should be written
    assert iface._file_io.write_dataset.call_count == 1
    assert iface._file_io.write_dataset.call_args.args[1] is ds_dirty.data
    ds_dirty.mark_clean.assert_called_once()
    ds_clean.mark_clean.assert_not_called()

@pytest.mark.asyncio
async def test__start_async_calls_prepare_and_server_manager(iface):
    """Verify that asynchronous start prepares the scene and starts the server."""
    iface._server_manager.running = False
    iface._prepare_and_render_scene = MagicMock(return_value="dataset_id")
    iface._server_manager.start_async = AsyncMock(return_value="task")
    result = await iface._start_async("input", "metadata", timeout=1)
    iface._prepare_and_render_scene.assert_called_once()
    iface._server_manager.start_async.assert_awaited_once_with(1)
    assert result == ("dataset_id", "task")

@pytest.mark.asyncio
async def test__stop_async_calls_server_manager(iface):
    """Verify that asynchronous stop delegates to the server manager."""
    iface._server_manager.running = True
    iface._server_manager.stop_async = AsyncMock()
    await iface._stop_async()
    iface._server_manager.stop_async.assert_awaited_once()

def test__health_returns_health(iface):
    """Verify that health status is returned from the server manager."""
    iface._server_manager.health = True
    assert iface._health() is True

def test__prepare_and_render_scene_calls_scene_methods(iface):
    """Verify that scene preparation adds data and finalizes the scene."""
    valid_metadata = ExtendedMetadata(name="test", unit="m", file_path="/path/to/file.vtp", metadata_path=None)
    dummy_dataset = vtkPolyData()

    # Mock dataset_count to return a valid integer
    type(iface._scene).dataset_count = PropertyMock(return_value=1)

    with patch.object(iface._file_io, "resolve", return_value=(dummy_dataset, valid_metadata)):
        iface._scene.add_dataset = MagicMock()
        iface._scene.finalize_scene = MagicMock()
        iface._prepare_and_render_scene("input", "metadata")
        iface._scene.add_dataset.assert_called_once()
        iface._scene.finalize_scene.assert_called_once()


def test__prepare_and_render_scene_with_none_input(iface):
    """Verify that scene finalization occurs even when no input is provided."""
    # Mock dataset_count to return 0 (no datasets)
    type(iface._scene).dataset_count = PropertyMock(return_value=0)

    iface._scene.add_dataset = MagicMock()
    iface._scene.finalize_scene = MagicMock()
    iface._prepare_and_render_scene(None, None)
    iface._scene.add_dataset.assert_not_called()
    iface._scene.finalize_scene.assert_called_once()

def test_validate_input_metadata_types_raises_on_bad_input_type(dummy_iface):
    """Verify that invalid input types raise a TypeError."""
    with pytest.raises(TypeError, match="input must be a str or VisorDatasetType"):
        dummy_iface.test_input_metadata_types(input=123)

def test_validate_input_metadata_types_raises_on_bad_metadata_type(dummy_iface):
    """Verify that invalid metadata types raise a TypeError."""
    with pytest.raises(TypeError, match="metadata must be a string, an instance of Metadata or None"):
        dummy_iface.test_input_metadata_types(input="valid", metadata=[])

def test_require_input_is_not_none_raises_on_none_input(dummy_iface):
    """Verify that a None input raises a ValueError."""
    with pytest.raises(ValueError, match="Input cannot be None"):
        dummy_iface.test_input_is_not_none(input=None)

def test_require_server_off_raises_when_running(dummy_iface):
    """Verify that execution is blocked when the server is already running."""
    with pytest.raises(RuntimeError, match="Visor server already running"):
        dummy_iface.test_require_server_off()

def test_require_server_on_raises_when_not_running(dummy_iface):
    """Verify that execution is blocked when the server is not running."""
    type(dummy_iface._server_manager).running = PropertyMock(return_value=False)
    print(f'dummy_iface._server_manager.running: {dummy_iface._server_manager.running}')
    with pytest.raises(ServerNotStartedError, match="Failed to find running server"):
        dummy_iface.test_require_server_on()

def test_start_calls_scene_clear(iface):
    """Verify that start clears the scene before loading new data."""
    iface._server_manager.running = False
    iface._prepare_and_render_scene = MagicMock()
    iface._server_manager.start = MagicMock()
    iface._scene.clear = MagicMock()
    iface.start("input", "metadata", timeout=5, blocking=True)
    iface._scene.clear.assert_called_once()

@pytest.mark.asyncio
async def test__start_async_calls_scene_clear(iface):
    """Verify that asynchronous start clears the scene before loading new data."""
    iface._server_manager.running = False
    iface._prepare_and_render_scene = MagicMock()
    iface._server_manager.start_async = AsyncMock(return_value="task")
    iface._scene.clear = MagicMock()
    await iface._start_async("input", "metadata", timeout=1)
    iface._scene.clear.assert_called_once()

def test_start_does_not_clear_scene_if_input_none(iface):
    """Verify that start does not clear the scene when no input is provided."""
    iface._server_manager.running = False  # Ensure server is not running
    iface._scene.clear = MagicMock()
    iface._prepare_and_render_scene = MagicMock()
    iface._server_manager.start = MagicMock()
    iface.start(None, None, timeout=5, blocking=True)
    iface._scene.clear.assert_not_called()

@pytest.mark.asyncio
async def test__start_async_does_not_clear_scene_if_input_none(iface):
    """Verify that asynchronous start does not clear the scene when no input is provided."""
    iface._server_manager.running = False  # Ensure server is not running
    iface._scene.clear = MagicMock()
    iface._prepare_and_render_scene = MagicMock()
    iface._server_manager.start_async = AsyncMock(return_value="task")
    await iface._start_async(None, None, timeout=1)
    iface._scene.clear.assert_not_called()

def test_update_calls_scene_clear(iface):
    """Verify that update clears the scene before reloading data."""
    iface._server_manager.running = True
    iface._scene.clear = MagicMock()
    iface._prepare_and_render_scene = MagicMock()
    iface.update("input", "metadata")


# ================================================================== #
# load_state
# ================================================================== #

def _make_state_with_datasets(snapshot_path: str | None, name="model", unit="m") -> PersistedViewerStateV1:
    """Helper function to create a PersistedViewerStateV1 with a dataset state."""
    ds_state = PersistedDatasetState(serialized_dataset_path=snapshot_path)
    return PersistedViewerStateV1.from_components(
        ui_state=VisorUIState(), unit=unit, orthographic_enabled=None,
        cross_section_enabled=None, edges_enabled=None, bounding_box_enabled=None,
        datasets={name: ds_state}
    )


def test_load_state_restores_datasets_when_registry_empty(tmp_path, iface):
    """Verify that datasets are restored when no datasets are currently loaded."""
    snapshot = tmp_path / "model_snapshot.vtkhdf"
    snapshot.touch()
    state = _make_state_with_datasets(str(snapshot), name="model")

    mock_data = MagicMock()
    iface._file_io.read_state = MagicMock(return_value=state)
    iface._file_io.read_snapshot = MagicMock(return_value=mock_data)
    iface._file_io.build_metadata_for_load_state = MagicMock(return_value=MagicMock(spec=ExtendedMetadata))
    type(iface._scene).dataset_count = PropertyMock(side_effect=[0, 1])
    loaded_ds = MagicMock()
    iface._scene.add_dataset = MagicMock(return_value=42)
    iface._scene.datasets = {42: loaded_ds}
    iface._scene.apply_state = MagicMock()
    iface._scene.finalize_scene = MagicMock()

    iface.load_state(str(tmp_path))

    iface._file_io.read_snapshot.assert_called_once_with(str(snapshot))
    iface._scene.add_dataset.assert_called_once_with(mock_data, iface._file_io.build_metadata_for_load_state.return_value)
    loaded_ds.mark_clean.assert_called_once()
    iface._scene.finalize_scene.assert_called_once()
    iface._scene.apply_state.assert_called_once_with(state)


def test_load_state_skips_dataset_restore_when_registry_not_empty(tmp_path, iface):
    """Verify that dataset restoration is skipped when datasets already exist."""
    snapshot = tmp_path / "model_snapshot.vtkhdf"
    snapshot.touch()
    state = _make_state_with_datasets(str(snapshot), name="model")

    iface._file_io.read_state = MagicMock(return_value=state)
    iface._file_io.read_snapshot = MagicMock()
    type(iface._scene).dataset_count = PropertyMock(return_value=1)
    iface._scene.apply_state = MagicMock()
    iface._scene.finalize_scene = MagicMock()

    iface.load_state(str(tmp_path))

    iface._file_io.read_snapshot.assert_not_called()
    iface._scene.apply_state.assert_called_once_with(state)


def test_load_state_skips_missing_snapshot(tmp_path, iface):
    """Verify that missing dataset snapshots are ignored during state loading."""
    state = _make_state_with_datasets("/nonexistent/snap.vtkhdf", name="model")

    iface._file_io.read_state = MagicMock(return_value=state)
    iface._file_io.read_snapshot = MagicMock()
    type(iface._scene).dataset_count = PropertyMock(return_value=0)
    iface._scene.apply_state = MagicMock()
    iface._scene.finalize_scene = MagicMock()

    iface.load_state(str(tmp_path))

    iface._file_io.read_snapshot.assert_not_called()
    iface._scene.finalize_scene.assert_not_called()
    iface._scene.apply_state.assert_called_once_with(state)


def test_load_state_skips_dataset_with_no_snapshot_path(tmp_path, iface):
    """Verify that datasets without snapshot paths are ignored during state loading."""
    state = _make_state_with_datasets(None, name="model")

    iface._file_io.read_state = MagicMock(return_value=state)
    iface._file_io.read_snapshot = MagicMock()
    type(iface._scene).dataset_count = PropertyMock(return_value=0)
    iface._scene.apply_state = MagicMock()
    iface._scene.finalize_scene = MagicMock()

    iface.load_state(str(tmp_path))

    iface._file_io.read_snapshot.assert_not_called()
    iface._scene.apply_state.assert_called_once_with(state)


def test_load_state_passes_correct_metadata_to_add_dataset(tmp_path, iface):
    """Verify that restored datasets receive the expected metadata."""
    snapshot = tmp_path / "mesh_snapshot.vtkhdf"
    snapshot.touch()
    ds_state = PersistedDatasetState(
        serialized_dataset_path=str(snapshot), source_file_path="/orig/mesh.vtu"
    )
    state = PersistedViewerStateV1.from_components(
        ui_state=VisorUIState(), unit="mm", orthographic_enabled=None,
        cross_section_enabled=None, edges_enabled=None, bounding_box_enabled=None,
        datasets={"mesh": ds_state}
    )

    built_meta = MagicMock(spec=ExtendedMetadata)
    mock_data = MagicMock()
    iface._file_io.read_state = MagicMock(return_value=state)
    iface._file_io.read_snapshot = MagicMock(return_value=mock_data)
    iface._file_io.build_metadata_for_load_state = MagicMock(return_value=built_meta)
    iface._scene.add_dataset = MagicMock(return_value=1)
    type(iface._scene).dataset_count = PropertyMock(side_effect=[0, 1])
    iface._scene.datasets = {1: MagicMock()}
    iface._scene.apply_state = MagicMock()
    iface._scene.finalize_scene = MagicMock()

    iface.load_state(str(tmp_path))

    iface._file_io.build_metadata_for_load_state.assert_called_once_with("mesh", "mm", ds_state)
    iface._file_io.read_snapshot.assert_called_once_with(str(snapshot))
    iface._scene.add_dataset.assert_called_once_with(mock_data, built_meta)
