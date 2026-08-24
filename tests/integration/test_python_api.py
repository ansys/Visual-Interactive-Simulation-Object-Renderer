import asyncio
from os import makedirs, path
from unittest.mock import MagicMock, patch

import pytest

from ansys.visor.viewer import Visor
from ansys.visor.viewer.app.visor_vtk import VisorVTK
from ansys.visor.viewer.core.errors import InvalidFileError, InvalidFileFormatError, InvalidServerTimeoutError
from ansys.visor.viewer.core.metadata import Metadata
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1

plate_vtp_file = path.join(path.dirname(__file__), "..", "files", "plate.vtp")
plate_scdocx_file = path.join(path.dirname(__file__), "..", "files", "plate.scdocx")
mesh_vtu_file = path.join(path.dirname(__file__), "..", "files", "mesh.vtu")
vtm_file = path.join(path.dirname(__file__), "..", "files", "many_blocks", "many_blocks.vtm")
metadata = Metadata(name="test_model", unit="m")
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet


def test_initialization():
    """Test initialization."""
    visor_instance = Visor()
    assert visor_instance.standalone
    assert visor_instance.host == "localhost"
    assert visor_instance.port == 8081


def test_initiazation_invalid_rendering_engine():
    """Test initialization with invalid rendering engine."""
    with pytest.raises(ValueError):
        Visor(rendering_engine="invalid_engine")


def test_initialization_with_standalone_flag():
    """Test initialization with standalone flag."""
    visor_instance = Visor(standalone=True)
    assert visor_instance.standalone
    assert visor_instance._server_manager._server._www.find("client_bundle") != -1


def test_initialization_with_standalone_flag_false():
    """Test initialization with standalone flag set to false."""
    visor_instance = Visor(standalone=False)
    assert not visor_instance.standalone
    assert visor_instance._server_manager._server._www is None


@pytest.mark.skip("Disabled checks due to having too many false negatives")
def test_render_input_invalid_file():
    """Test render_input with invalid file."""
    visor_instance = Visor()
    with pytest.raises(InvalidFileError):
        visor_instance._Visor__render_input("invalid_file.txt", metadata)


@pytest.mark.skip("Disabled checks due to having too many false negatives")
def test_render_input_invalid_file_format():
    """Test render_input with invalid file format."""
    visor_instance = Visor()
    with pytest.raises(InvalidFileFormatError):
        visor_instance._Visor__render_input(plate_scdocx_file, metadata)


def test_initiazation_url():
    """Test initialization URL."""
    visor_instance = Visor(url="http://localhost:8080")
    assert visor_instance.url == "http://localhost:8080"


def test_update_model_file():
    """Test update API with VTU file after starting with VTP file."""
    async def update_test():
        visor_instance = Visor()
        await visor_instance._start_async(input=plate_vtp_file, metadata=metadata)
        visor_instance.update(mesh_vtu_file, metadata)
        await visor_instance._stop_async()

    asyncio.run(update_test())


def test_update_model_data():
    """Test update API with VTU file after starting with multiblock file."""
    async def update_test():
        multiblock = vtkMultiBlockDataSet()
        visor_instance = Visor()
        await visor_instance._start_async(input=multiblock, metadata=metadata)
        visor_instance.update(mesh_vtu_file, metadata)
        await visor_instance._stop_async()

    asyncio.run(update_test())


def test_start_with_invalid_timeout():
    """Test that start with invalid timeout."""
    visor_instance = Visor()
    with pytest.raises(InvalidServerTimeoutError):
        async def start():
            await visor_instance._start_async(input=plate_vtp_file, timeout=-2)

        asyncio.run(start())

def test_save_load_state(tmp_path):
    """Test that state can be saved and loaded."""
    state_dir = path.join(tmp_path, "state")
    makedirs(state_dir, exist_ok=True)
    assert path.exists(state_dir)
    assert path.isdir(state_dir)

    visor_instance = Visor()

    # New behavior: save_state awaits a frontend-backed `scene.get_state()`.
    # Keep the persisted state minimal and aligned with PersistedViewerStateV1 schema.
    mock_state = PersistedViewerStateV1()

    async def fake_get_state(timeout: float = 5.0):
        return mock_state

    # `save_state` is async; it also requires the server to be "on" via decorator.
    # `running` is a read-only property, so we mock the underlying server manager.
    visor_instance._scene = MagicMock()
    visor_instance._scene.get_state = MagicMock(side_effect=fake_get_state)
    visor_instance._server_manager = MagicMock()
    visor_instance._server_manager.running = True

    asyncio.run(visor_instance.save_state(state_dir=state_dir))

    state_file = path.join(state_dir, "visor.json")
    assert path.exists(state_file)

    # Sanity-check that the file round-trips into the same model.
    with open(state_file, "r") as f:
        loaded = PersistedViewerStateV1.model_validate_json(f.read())
    assert loaded == mock_state

def test_start():
    """Test that start."""
    async def start_test():
        visor_instance = Visor()
        print(f'visor_instance: {visor_instance.running}')
        await visor_instance._start_async(input=vtm_file, metadata=metadata, timeout=5)
        assert visor_instance._health()
        await visor_instance._stop_async()

    asyncio.run(start_test())

def test_start_async_calls_render_input():
    """Test that start async calls render input."""
    async def run():
        visor = VisorVTK()
        with patch.object(visor._scene, "render") as mock_render:
            with patch("os.path.exists", return_value=True):
                await visor._start_async(input="dummy.vtp", metadata=Metadata(name="test", unit="m"))
                mock_render.assert_called_once()
    asyncio.run(run())
