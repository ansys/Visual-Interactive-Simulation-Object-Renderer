"""Integration tests for dataset snapshot save/load via VisorFileIO and VisorVTK.

These tests use real VTK files and real filesystem I/O — no mocking of readers,
writers, or the VTK pipeline.  Only the Trame server manager and Trame app are
patched out so no network/process resources are allocated.

Scenarios covered
-----------------
write_dataset / read_dataset round-trip:
    - PolyData, UnstructuredGrid, and MultiBlockDataSet snapshots survive a
      write → read cycle with equal geometry.

build_metadata_for_load_state:
    - The ExtendedMetadata constructed for a load-state restore carries the
      correct name, unit, file_path, metadata_path, and state.

_load_datasets_from_state / load_state (VisorVTK):
    - After write_dataset writes snapshots, a fresh interface with zero datasets
      correctly loads each snapshot and ends up with the right datasets.
    - Datasets are marked clean after restore.
    - Missing / absent snapshot paths are skipped gracefully.
    - Partial restores load only the available snapshots.
    - Unit from state is preserved in the registry.
    - load_state skips the restore when the scene already has datasets.

Real test files used:
    tests/files/plate.vtp                — VTK PolyData
    tests/files/mesh.vtu                 — VTK UnstructuredGrid
    tests/files/simple_multiblock.vtkhdf — VTK MultiBlockDataSet
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from vtkmodules.vtkCommonDataModel import (
    vtkMultiBlockDataSet,
    vtkPolyData,
    vtkUnstructuredGrid,
)

from ansys.visor.viewer.app.visor_vtk import VisorVTK
from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset
from ansys.visor.viewer.vtk.io.visor_file_io import VisorFileIO

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _files_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "files")

def _vtp_path() -> str:
    return os.path.join(_files_dir(), "plate.vtp")

def _vtu_path() -> str:
    return os.path.join(_files_dir(), "mesh.vtu")

def _vtkhdf_multiblock_path() -> str:
    return os.path.join(_files_dir(), "simple_multiblock.vtkhdf")


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def file_io():
    """PyTest fixture for file io."""
    return VisorFileIO()


@pytest.fixture
def iface():
    """A VisorVTK with a real VTK scene but Trame server/app patched
    out so no network or process resources are allocated."""
    with patch("ansys.visor.viewer.app.visor_vtk.TrameServerManager") as mock_sm, \
         patch("ansys.visor.viewer.app.visor_vtk_local.LocalApp"):
        from trame.app import get_server
        real_server = get_server()
        mock_sm.return_value.server = real_server
        instance = VisorVTK()
    yield instance
    try:
        instance._scene.clear()
        instance._scene.cleanup_state()
    except Exception:
        pass


# ================================================================== #
# write_dataset / read_dataset round-trips
# ================================================================== #

class TestWriteDatasetRoundTrip:
    """write_dataset must produce a VTKHDF file that read_dataset can reload
    with geometry identical to the original in-memory object."""

    def test_polydata_round_trip_preserves_point_count(self, file_io, tmp_path):
        """Test that polydata round trip preserves point count."""
        original = file_to_dataset(_vtp_path())
        dest = tmp_path / "plate_snapshot.vtkhdf"

        file_io.write_dataset(dest, original)
        assert dest.exists()

        restored = file_io.read_dataset(str(dest))
        assert isinstance(restored, vtkPolyData)
        assert restored.GetNumberOfPoints() == original.GetNumberOfPoints()
        assert restored.GetNumberOfCells() == original.GetNumberOfCells()

    def test_unstructured_grid_round_trip_preserves_point_count(self, file_io, tmp_path):
        """Test that unstructured grid round trip preserves point count."""
        original = file_to_dataset(_vtu_path())
        dest = tmp_path / "mesh_snapshot.vtkhdf"

        file_io.write_dataset(dest, original)
        assert dest.exists()

        restored = file_io.read_dataset(str(dest))
        assert isinstance(restored, vtkUnstructuredGrid)
        assert restored.GetNumberOfPoints() == original.GetNumberOfPoints()
        assert restored.GetNumberOfCells() == original.GetNumberOfCells()

    def test_multiblock_round_trip_preserves_block_count(self, file_io, tmp_path):
        """Test that multiblock round trip preserves block count."""
        original = file_to_dataset(_vtkhdf_multiblock_path())
        dest = tmp_path / "multiblock_snapshot.vtkhdf"

        file_io.write_dataset(dest, original)
        assert dest.exists()

        restored = file_io.read_dataset(str(dest))
        assert isinstance(restored, vtkMultiBlockDataSet)
        assert restored.GetNumberOfBlocks() == original.GetNumberOfBlocks()

    def test_snapshot_file_is_created_in_nested_directory(self, file_io, tmp_path):
        """Test that snapshot file is created in nested directory."""
        original = file_to_dataset(_vtp_path())
        dest = tmp_path / "save" / "datasets" / "plate_snapshot.vtkhdf"

        file_io.write_dataset(dest, original)

        assert dest.exists()

    def test_get_persisted_dataset_path_matches_written_file(self, file_io, tmp_path):
        """The path returned by get_persisted_dataset_path must be exactly
        where write_dataset puts the file."""
        original = file_to_dataset(_vtp_path())
        expected_path = file_io.get_persisted_dataset_path(str(tmp_path), "plate")

        file_io.write_dataset(expected_path, original)

        assert expected_path.exists()
        restored = file_io.read_dataset(str(expected_path))
        assert restored.GetNumberOfPoints() == original.GetNumberOfPoints()


# ================================================================== #
# build_metadata_for_load_state
# ================================================================== #

class TestBuildMetadataForLoadStateIntegration:
    """build_metadata_for_load_state must produce ExtendedMetadata that wires
    all fields correctly from real PersistedDatasetState values."""

    def test_name_and_unit_are_preserved(self, file_io, tmp_path):
        """Test that name and unit are preserved."""
        ds_state = PersistedDatasetState(
            serialized_dataset_path=str(tmp_path / "snap.vtkhdf")
        )
        meta = file_io.build_metadata_for_load_state("plate", "mm", ds_state)
        assert meta.name == "plate"
        assert meta.unit == "mm"

    def test_source_file_path_is_propagated(self, file_io, tmp_path):
        """Test that source file path is propagated."""
        ds_state = PersistedDatasetState(
            serialized_dataset_path=str(tmp_path / "snap.vtkhdf"),
            source_file_path=_vtp_path(),
        )
        meta = file_io.build_metadata_for_load_state("plate", "m", ds_state)
        assert meta.file_path == _vtp_path()

    def test_source_metadata_path_is_propagated(self, file_io, tmp_path):
        """Test that source metadata path is propagated."""
        ds_state = PersistedDatasetState(
            serialized_dataset_path=str(tmp_path / "snap.vtkhdf"),
            source_metadata_path="/some/meta.json",
        )
        meta = file_io.build_metadata_for_load_state("plate", "m", ds_state)
        assert meta.metadata_path == "/some/meta.json"

    def test_state_field_carries_serialized_path(self, file_io, tmp_path):
        """Test that state field carries serialized path."""
        snap = str(tmp_path / "snap.vtkhdf")
        ds_state = PersistedDatasetState(serialized_dataset_path=snap)
        meta = file_io.build_metadata_for_load_state("model", "m", ds_state)
        assert meta.state.serialized_dataset_path == snap

    def test_none_unit_becomes_empty_string(self, file_io):
        """Test that when unit=None is passed, unit becomes empty string."""
        ds_state = PersistedDatasetState()
        meta = file_io.build_metadata_for_load_state("model", None, ds_state)
        assert meta.unit == ""


# ================================================================== #
# _load_datasets_from_state — VisorScene
# ================================================================== #

class TestLoadDatasetsFromState:
    """End-to-end: write real snapshots then verify _load_datasets_from_state
    populates the scene correctly, and that load_state skips the restore when
    datasets are already present."""

    def _make_state(self, dataset_states: dict, unit: str = "m") -> PersistedViewerStateV1:
        return PersistedViewerStateV1.from_components(
            ui_state=VisorUIState(),
            unit=unit,
            orthographic_enabled=None,
            cross_section_enabled=None,
            edges_enabled=None,
            bounding_box_enabled=None,
            datasets=dataset_states,
        )

    def test_single_dataset_is_restored_into_empty_scene(self, file_io, iface, tmp_path):
        """Test that single dataset is restored into empty scene."""
        original = file_to_dataset(_vtp_path())
        snap = file_io.get_persisted_dataset_path(str(tmp_path), "plate")
        file_io.write_dataset(snap, original)

        state = self._make_state({"plate": PersistedDatasetState(serialized_dataset_path=str(snap))})

        assert iface._scene.dataset_count == 0
        iface._load_datasets_from_state(state)

        assert iface._scene.dataset_count == 1
        assert next(iter(iface._scene.datasets.values())).name == "plate"

    def test_restored_dataset_geometry_matches_original(self, file_io, iface, tmp_path):
        """Test that restored dataset geometry matches original."""
        original = file_to_dataset(_vtp_path())
        snap = file_io.get_persisted_dataset_path(str(tmp_path), "plate")
        file_io.write_dataset(snap, original)

        state = self._make_state({"plate": PersistedDatasetState(serialized_dataset_path=str(snap))})
        iface._load_datasets_from_state(state)

        restored_data = next(iter(iface._scene.datasets.values())).data
        assert restored_data.GetNumberOfPoints() == original.GetNumberOfPoints()
        assert restored_data.GetNumberOfCells() == original.GetNumberOfCells()

    def test_multiple_datasets_are_all_restored(self, file_io, iface, tmp_path):
        """Test that multiple datasets are all restored."""
        vtp = file_to_dataset(_vtp_path())
        vtu = file_to_dataset(_vtu_path())
        snap_vtp = file_io.get_persisted_dataset_path(str(tmp_path), "plate")
        snap_vtu = file_io.get_persisted_dataset_path(str(tmp_path), "mesh")
        file_io.write_dataset(snap_vtp, vtp)
        file_io.write_dataset(snap_vtu, vtu)

        state = self._make_state({
            "plate": PersistedDatasetState(serialized_dataset_path=str(snap_vtp)),
            "mesh":  PersistedDatasetState(serialized_dataset_path=str(snap_vtu)),
        })
        iface._load_datasets_from_state(state)

        assert iface._scene.dataset_count == 2
        names = {ds.name for ds in iface._scene.datasets.values()}
        assert names == {"plate", "mesh"}

    def test_restored_dataset_is_marked_clean(self, file_io, iface, tmp_path):
        """Test that restored dataset is marked clean."""
        original = file_to_dataset(_vtp_path())
        snap = file_io.get_persisted_dataset_path(str(tmp_path), "plate")
        file_io.write_dataset(snap, original)

        state = self._make_state({"plate": PersistedDatasetState(serialized_dataset_path=str(snap))})
        iface._load_datasets_from_state(state)

        dataset = next(iter(iface._scene.datasets.values()))
        assert dataset.is_dirty is False

    def test_missing_snapshot_is_skipped_gracefully(self, iface, tmp_path):
        """Test that missing snapshot is skipped gracefully."""
        state = self._make_state({
            "plate": PersistedDatasetState(
                serialized_dataset_path=str(tmp_path / "nonexistent_snapshot.vtkhdf")
            )
        })
        iface._load_datasets_from_state(state)
        assert iface._scene.dataset_count == 0

    def test_dataset_with_no_snapshot_path_is_skipped(self, iface):
        """Test that dataset with no snapshot path is skipped."""
        state = self._make_state({"plate": PersistedDatasetState(serialized_dataset_path=None)})
        iface._load_datasets_from_state(state)
        assert iface._scene.dataset_count == 0

    def test_partial_restore_loads_available_snapshots(self, file_io, iface, tmp_path):
        """When one snapshot exists and one is missing, only the present one is loaded."""
        original = file_to_dataset(_vtp_path())
        snap = file_io.get_persisted_dataset_path(str(tmp_path), "plate")
        file_io.write_dataset(snap, original)

        state = self._make_state({
            "plate": PersistedDatasetState(serialized_dataset_path=str(snap)),
            "mesh":  PersistedDatasetState(serialized_dataset_path=str(tmp_path / "nonexistent.vtkhdf")),
        })
        iface._load_datasets_from_state(state)

        assert iface._scene.dataset_count == 1
        assert next(iter(iface._scene.datasets.values())).name == "plate"

    def test_restore_preserves_unit_from_state(self, file_io, iface, tmp_path):
        """Test that restoring preserves unit from state."""
        original = file_to_dataset(_vtp_path())
        snap = file_io.get_persisted_dataset_path(str(tmp_path), "plate")
        file_io.write_dataset(snap, original)

        state = self._make_state({"plate": PersistedDatasetState(serialized_dataset_path=str(snap))}, unit="mm")
        iface._load_datasets_from_state(state)

        assert iface._scene._dataset_registry.unit == "mm"

    def test_load_state_skips_restore_when_scene_already_has_datasets(self, file_io, iface, tmp_path):
        """load_state must skip _load_datasets_from_state when dataset_count > 0."""
        # Pre-populate with one real dataset
        existing = file_to_dataset(_vtp_path())
        iface._scene.add_dataset(existing, ExtendedMetadata(name="existing", unit="m"))
        assert iface._scene.dataset_count == 1

        # Write a second snapshot + visor.json that load_state should NOT load
        original = file_to_dataset(_vtu_path())
        snap = file_io.get_persisted_dataset_path(str(tmp_path), "mesh")
        file_io.write_dataset(snap, original)
        state = self._make_state({"mesh": PersistedDatasetState(serialized_dataset_path=str(snap))})
        file_io.write_state(str(tmp_path), state)

        # Stub apply_state so the frontend bridge isn't called
        iface._scene.apply_state = MagicMock()
        iface.load_state(str(tmp_path))

        # Only the pre-existing dataset should be present
        assert iface._scene.dataset_count == 1
        assert next(iter(iface._scene.datasets.values())).name == "existing"

    def test_stale_snapshot_deleted_after_dataset_removed(self, file_io, tmp_path):
        """A snapshot written during a previous save_state must be deleted when
        the corresponding dataset is no longer in the new state."""
        # Simulate a previous save: two snapshots + visor.json on disk
        plate_snap = file_io.get_persisted_dataset_path(str(tmp_path), "plate")
        mesh_snap  = file_io.get_persisted_dataset_path(str(tmp_path), "mesh")
        plate_snap.touch()
        mesh_snap.touch()

        # New state only references "plate" — "mesh" has been removed
        new_state = self._make_state({
            "plate": PersistedDatasetState(serialized_dataset_path=str(plate_snap)),
        })
        file_io.write_state(str(tmp_path), new_state)
        file_io.delete_stale_snapshots(str(tmp_path), new_state)

        assert plate_snap.exists()
        assert not mesh_snap.exists()

