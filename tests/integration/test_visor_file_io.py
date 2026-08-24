"""Integration tests for VisorFileIO.

These tests exercise real filesystem I/O — no mocking of ``open``, ``Path``,
or ``file_to_dataset``.  pytest's ``tmp_path`` fixture provides a clean
temporary directory for each test.

Real test files used:
    tests/files/plate.vtp                — VTK PolyData (legacy XML)
    tests/files/mesh.vtu                 — VTK UnstructuredGrid (legacy XML)
    tests/files/plate.vtkhdf             — VTK PolyData (VTKHDF)
    tests/files/mesh.vtkhdf              — VTK UnstructuredGrid (VTKHDF)
    tests/files/simple_multiblock.vtkhdf — VTK MultiBlockDataSet (VTKHDF)
"""
import json
import os

import pytest
from vtkmodules.vtkCommonDataModel import vtkMultiBlockDataSet, vtkPolyData, vtkUnstructuredGrid

from ansys.visor.viewer.core.metadata import Metadata
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.vtk.io.visor_file_io import _STATE_FILE_NAME, VisorFileIO

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _test_files_dir() -> str:
    """Return the path to the directory containing test files."""
    return os.path.join(os.path.dirname(__file__), "..", "files")

def _vtp_path() -> str:
    """Return the path to the test VTP file."""
    return os.path.join(_test_files_dir(), "plate.vtp")

def _vtu_path() -> str:
    """Return the path to the test VTU file."""
    return os.path.join(_test_files_dir(), "mesh.vtu")

def _vtkhdf_polydata_path() -> str:
    """Return the path to the test VTKHDF PolyData file."""
    return os.path.join(_test_files_dir(), "plate.vtkhdf")

def _vtkhdf_unstructured_grid_path() -> str:
    """Return the path to the test VTKHDF UnstructuredGrid file."""
    return os.path.join(_test_files_dir(), "mesh.vtkhdf")

def _vtkhdf_multiblock_path() -> str:
    """Return the path to the test VTKHDF MultiBlockDataSet file."""
    return os.path.join(_test_files_dir(), "simple_multiblock.vtkhdf")


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def file_io():
    """PyTest fixture for file io."""
    return VisorFileIO()

@pytest.fixture
def minimal_state():
    """PyTest fixture for minimal state."""
    return PersistedViewerStateV1()

@pytest.fixture
def metadata_file(tmp_path):
    """Write a valid metadata JSON file to tmp_path and return its path."""
    meta = {"name": "test_model", "unit": "m"}
    path = tmp_path / "meta.json"
    path.write_bytes(json.dumps(meta).encode())
    return str(path)


# ================================================================== #
# read_dataset
# ================================================================== #

class TestReadDatasetIntegration:
    def test_reads_vtp_file(self, file_io):
        """Test reading VTP file."""
        result = file_io.read_dataset(_vtp_path())
        assert result is not None
        assert result.GetNumberOfPoints() > 0

    def test_reads_vtu_file(self, file_io):
        """Test reading VTU file."""
        result = file_io.read_dataset(_vtu_path())
        assert result is not None
        assert result.GetNumberOfPoints() > 0

    def test_raises_for_missing_file(self, file_io):
        """Test that missing file raises RuntimeError."""
        with pytest.raises(RuntimeError, match="file does not exist"):
            file_io.read_dataset("/nonexistent/path/model.vtp")

    def test_raises_for_unsupported_extension(self, file_io, tmp_path):
        """Test that unsupported extension raises RuntimeError."""
        bad_file = tmp_path / "model.xyz"
        bad_file.write_text("dummy")
        with pytest.raises(RuntimeError, match="Unsupported file"):
            file_io.read_dataset(str(bad_file))


# ================================================================== #
# read_metadata
# ================================================================== #

class TestReadMetadataIntegration:
    def test_reads_valid_metadata_file(self, file_io, metadata_file):
        """Test that a valid metadata file is read correctly."""
        result = file_io.read_metadata(metadata_file)
        assert isinstance(result, Metadata)
        assert result.name == "test_model"
        assert result.unit == "m"

    def test_raises_for_missing_file(self, file_io):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            file_io.read_metadata("/nonexistent/meta.json")

    def test_raises_for_invalid_json(self, file_io, tmp_path):
        """Test that invalid json raises ValueError."""
        bad = tmp_path / "bad.json"
        bad.write_bytes(b"not valid json")
        with pytest.raises(json.JSONDecodeError):
            file_io.read_metadata(str(bad))


# ================================================================== #
# write_state / read_state round-trip
# ================================================================== #

class TestWriteReadStateIntegration:
    def test_write_creates_visor_json(self, file_io, minimal_state, tmp_path):
        """Test that write_state creates visor json file."""
        file_io.write_state(str(tmp_path), minimal_state)
        assert (tmp_path / _STATE_FILE_NAME).exists()

    def test_write_creates_directory_if_absent(self, file_io, minimal_state, tmp_path):
        """Test that write_state creates directory if absent."""
        state_dir = str(tmp_path / "nested" / "dir")
        file_io.write_state(state_dir, minimal_state)
        assert (tmp_path / "nested" / "dir" / _STATE_FILE_NAME).exists()

    def test_written_file_is_valid_json(self, file_io, minimal_state, tmp_path):
        """Test that write_state writes a valid json."""
        file_io.write_state(str(tmp_path), minimal_state)
        content = (tmp_path / _STATE_FILE_NAME).read_text()
        parsed = json.loads(content)
        assert "version" in parsed

    def test_round_trip_preserves_version(self, file_io, minimal_state, tmp_path):
        """Test that round trip preserves version."""
        file_io.write_state(str(tmp_path), minimal_state)
        result = file_io.read_state(str(tmp_path))
        assert result.version == minimal_state.version

    def test_round_trip_preserves_ui_state(self, file_io, tmp_path):
        """Test that round trip preserves ui state."""
        from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
        state = PersistedViewerStateV1(ui=VisorUIState(dark_theme=True))
        file_io.write_state(str(tmp_path), state)
        result = file_io.read_state(str(tmp_path))
        assert result.ui.dark_theme is True

    def test_write_returns_path_to_file(self, file_io, minimal_state, tmp_path):
        """Test that write_state returns path to file."""
        result = file_io.write_state(str(tmp_path), minimal_state)
        assert result == tmp_path / _STATE_FILE_NAME
        assert result.exists()

    def test_read_raises_file_not_found_when_missing(self, file_io, tmp_path):
        """Test that read_state raises FileNotFoundError when missing."""
        with pytest.raises(FileNotFoundError, match="State file not found"):
            file_io.read_state(str(tmp_path))

    def test_read_raises_for_corrupt_json(self, file_io, tmp_path):
        """Test that read_state raises for corrupt json."""
        (tmp_path / _STATE_FILE_NAME).write_text("not valid json")
        with pytest.raises(Exception):
            file_io.read_state(str(tmp_path))

    def test_write_overwrites_existing_state_file(self, file_io, tmp_path):
        """Test that write_state overwrites existing state file."""
        from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
        state_a = PersistedViewerStateV1(ui=VisorUIState(dark_theme=False))
        state_b = PersistedViewerStateV1(ui=VisorUIState(dark_theme=True))
        file_io.write_state(str(tmp_path), state_a)
        file_io.write_state(str(tmp_path), state_b)
        result = file_io.read_state(str(tmp_path))
        assert result.ui.dark_theme is True


# ================================================================== #
# vtkhdf read support — read_dataset (VisorFileIO wrapper)
# ================================================================== #

class TestReadDatasetVtkhdfIntegration:
    """read_dataset must handle all three supported vtkhdf dataset types
    without requiring callers to know which reader is used internally."""

    def test_reads_vtkhdf_polydata_file(self, file_io):
        """Test that read_dataset reads vtkhdf polydata file."""
        result = file_io.read_dataset(_vtkhdf_polydata_path())
        assert isinstance(result, vtkPolyData)
        assert result.GetNumberOfPoints() > 0

    def test_reads_vtkhdf_unstructured_grid_file(self, file_io):
        """Test that read_dataset reads vtkhdf unstructured grid file."""
        result = file_io.read_dataset(_vtkhdf_unstructured_grid_path())
        assert isinstance(result, vtkUnstructuredGrid)
        assert result.GetNumberOfPoints() > 0

    def test_reads_vtkhdf_multiblock_file(self, file_io):
        """Test that read_dataset reads vtkhdf multiblock file."""
        result = file_io.read_dataset(_vtkhdf_multiblock_path())
        assert isinstance(result, vtkMultiBlockDataSet)
        assert result.GetNumberOfBlocks() > 0

    def test_vtkhdf_polydata_point_count_matches_vtp(self, file_io):
        """VTKHDF and VTP versions of the same file must have equal geometry."""
        vtp = file_io.read_dataset(_vtp_path())
        vtkhdf = file_io.read_dataset(_vtkhdf_polydata_path())
        assert vtkhdf.GetNumberOfPoints() == vtp.GetNumberOfPoints()
        assert vtkhdf.GetNumberOfCells() == vtp.GetNumberOfCells()

    def test_vtkhdf_unstructured_grid_point_count_matches_vtu(self, file_io):
        """VTKHDF and VTU versions of the same file must have equal geometry."""
        vtu = file_io.read_dataset(_vtu_path())
        vtkhdf = file_io.read_dataset(_vtkhdf_unstructured_grid_path())
        assert vtkhdf.GetNumberOfPoints() == vtu.GetNumberOfPoints()
        assert vtkhdf.GetNumberOfCells() == vtu.GetNumberOfCells()


# ================================================================== #
# resolve_metadata — name inferred from file path (vtkhdf paths)
# ================================================================== #

class TestResolveMetadataVtkhdfIntegration:
    """When no metadata object or path is provided, the dataset name must be
    inferred from the file stem of the input path — including .vtkhdf paths."""

    def test_name_inferred_from_vtkhdf_polydata_path(self, file_io):
        """Test name inferred from vtkhdf polydata path."""
        _, ext_meta = file_io.resolve(None, None)
        # Call resolve_metadata directly with a vtkhdf path as the input hint
        result = file_io.resolve_metadata(None, _vtkhdf_polydata_path())
        assert result.name == "plate"

    def test_name_inferred_from_vtkhdf_unstructured_grid_path(self, file_io):
        """Test name inferred from vtkhdf unstructured grid path."""
        result = file_io.resolve_metadata(None, _vtkhdf_unstructured_grid_path())
        assert result.name == "mesh"

    def test_name_inferred_from_vtkhdf_multiblock_path(self, file_io):
        """Test name inferred from vtkhdf multiblock path."""
        result = file_io.resolve_metadata(None, _vtkhdf_multiblock_path())
        assert result.name == "simple_multiblock"

    def test_explicit_metadata_overrides_path_inference(self, file_io):
        """An explicitly supplied Metadata must take priority over path inference."""
        explicit = Metadata(name="my_custom_name", unit="mm")
        result = file_io.resolve_metadata(explicit, _vtkhdf_polydata_path())
        assert result.name == "my_custom_name"
        assert result.unit == "mm"

    def test_resolve_end_to_end_with_vtkhdf_input_sets_name_and_file_path(self, file_io):
        """Full resolve() call with a vtkhdf path and no metadata must populate
        both the inferred name and file_path on the returned ExtendedMetadata."""
        path = _vtkhdf_polydata_path()
        dataset, ext_meta = file_io.resolve(path, None)
        assert isinstance(dataset, vtkPolyData)
        assert ext_meta.name == "plate"
        assert ext_meta.file_path == path


# ================================================================== #
# File handle released after reading (Windows regression)
# ================================================================== #

class TestFileHandleReleased:
    """After file_to_dataset (or VisorFileIO.read_dataset) returns, the source
    file must no longer be locked — it must be possible to overwrite and delete
    it without error.  This is the regression test for the WinError 32 bug
    where vtkHDFReader kept the HDF5 file open as long as the dataset was alive.
    """

    def test_vtkhdf_file_can_be_overwritten_after_read(self, file_io, tmp_path):
        """Test that vtkhdf file can be overwritten after read."""
        import shutil
        src = _vtkhdf_polydata_path()
        copy = tmp_path / "plate_copy.vtkhdf"
        shutil.copy2(src, copy)

        dataset = file_io.read_dataset(str(copy))
        assert dataset.GetNumberOfPoints() > 0

        # Must not raise WinError 32 on Windows
        copy.write_bytes(b"overwritten")
        assert copy.read_bytes() == b"overwritten"

    def test_vtkhdf_file_can_be_deleted_after_read(self, file_io, tmp_path):
        """Test that vtkhdf file can be deleted after read."""
        import shutil
        src = _vtkhdf_polydata_path()
        copy = tmp_path / "plate_copy.vtkhdf"
        shutil.copy2(src, copy)

        dataset = file_io.read_dataset(str(copy))
        assert dataset.GetNumberOfPoints() > 0

        # Must not raise WinError 32 on Windows
        copy.unlink()
        assert not copy.exists()

    def test_vtkhdf_unstructured_grid_file_can_be_deleted_after_read(self, file_io, tmp_path):
        """Test that vtkhdf unstructured grid file can be deleted after read."""
        import shutil
        src = _vtkhdf_unstructured_grid_path()
        copy = tmp_path / "mesh_copy.vtkhdf"
        shutil.copy2(src, copy)

        dataset = file_io.read_dataset(str(copy))
        assert dataset.GetNumberOfPoints() > 0

        copy.unlink()
        assert not copy.exists()

    def test_vtkhdf_multiblock_snapshot_can_be_deleted_after_load(self, file_io, tmp_path):
        """read_snapshot (used by load_state) must leave the original file unlocked
        so that save_state can delete it as a stale snapshot."""
        import shutil

        from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
        from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1

        src = _vtkhdf_multiblock_path()
        copy = tmp_path / "mb_copy.vtkhdf"
        shutil.copy2(src, copy)

        # Use read_snapshot — the load_state path — not read_dataset
        dataset = file_io.read_snapshot(str(copy))
        assert dataset.GetNumberOfBlocks() > 0

        state = PersistedViewerStateV1.from_components(
            ui_state=VisorUIState(), unit="m", orthographic_enabled=None,
            cross_section_enabled=None, edges_enabled=None, bounding_box_enabled=None,
            datasets={}
        )
        deleted = file_io.delete_stale_snapshots(str(tmp_path), state)

        assert not copy.exists()
        assert copy in deleted

    def test_dataset_data_is_intact_after_file_deleted(self, file_io, tmp_path):
        """The deep-copied dataset must retain all geometry even after the source
        file has been removed from disk."""
        import shutil
        src = _vtkhdf_polydata_path()
        original = file_io.read_dataset(src)
        expected_points = original.GetNumberOfPoints()
        expected_cells  = original.GetNumberOfCells()

        copy = tmp_path / "plate_copy.vtkhdf"
        shutil.copy2(src, copy)
        dataset = file_io.read_dataset(str(copy))
        copy.unlink()

        assert dataset.GetNumberOfPoints() == expected_points
        assert dataset.GetNumberOfCells()  == expected_cells


