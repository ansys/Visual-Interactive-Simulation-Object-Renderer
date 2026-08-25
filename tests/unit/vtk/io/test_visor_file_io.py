import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from vtkmodules.vtkCommonDataModel import vtkPolyData

from ansys.visor.viewer.core.metadata import ExtendedMetadata, Metadata
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.vtk.io.visor_file_io import _STATE_FILE_NAME, VisorFileIO, _try_unlink

# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def file_io():
    """Provides a VisorFileIO instance for testing."""
    return VisorFileIO()


@pytest.fixture
def minimal_state():
    """Provides a valid PersistedViewerStateV1 with default fields."""
    return PersistedViewerStateV1()


# ================================================================== #
# read_dataset
# ================================================================== #

class TestReadDataset:
    def test_delegates_to_file_to_dataset(self, file_io):
        """Verify that file_to_dataset delegates to file_to_dataset."""
        mock_dataset = MagicMock()
        with patch(
            "ansys.visor.viewer.vtk.io.visor_file_io.file_to_dataset",
            return_value=mock_dataset,
        ) as mock_fn:
            result = file_io.read_dataset("/some/path/model.vtu")
            mock_fn.assert_called_once_with("/some/path/model.vtu")
            assert result is mock_dataset

    def test_propagates_exception_from_file_to_dataset(self, file_io):
        """Test that propagates exception from file to dataset."""
        with patch(
            "ansys.visor.viewer.vtk.io.visor_file_io.file_to_dataset",
            side_effect=RuntimeError("bad file"),
        ):
            with pytest.raises(RuntimeError, match="bad file"):
                file_io.read_dataset("/missing/model.vtu")


# ================================================================== #
# read_metadata
# ================================================================== #

class TestReadMetadata:
    def test_parses_json_file_into_metadata(self, file_io):
        """Verify that read_metadata parses json file into Metadata."""
        metadata_dict = {"name": "my_model", "unit": "m"}
        with patch("builtins.open", mock_open(read_data=json.dumps(metadata_dict).encode())):
            result = file_io.read_metadata("/some/meta.json")
        assert isinstance(result, Metadata)
        assert result.name == "my_model"
        assert result.unit == "m"

    def test_opens_file_in_binary_mode(self, file_io):
        """Verify that read_metadata opens file in binary mode."""
        metadata_dict = {"name": "x", "unit": ""}
        m = mock_open(read_data=json.dumps(metadata_dict).encode())
        with patch("builtins.open", m):
            file_io.read_metadata("/some/meta.json")
        m.assert_called_once_with("/some/meta.json", "rb")

    def test_propagates_file_not_found(self, file_io):
        """Verify that read_metadata propagates FileNotFoundError."""
        with patch("builtins.open", side_effect=FileNotFoundError("no file")):
            with pytest.raises(FileNotFoundError):
                file_io.read_metadata("/missing/meta.json")

    def test_propagates_invalid_json(self, file_io):
        """Verify that read_metadata propagates JSONDecodeError on invalid json."""
        with patch("builtins.open", mock_open(read_data=b"not json")):
            with pytest.raises(json.JSONDecodeError):
                file_io.read_metadata("/bad/meta.json")


# ================================================================== #
# get_state_file_path
# ================================================================== #

class TestGetStateFilePath:
    def test_returns_visor_json_under_state_dir(self, file_io):
        """Verify that get_state_file_path returns visor.json under state dir."""
        result = file_io.get_state_file_path("/some/dir")
        assert result == Path("/some/dir") / _STATE_FILE_NAME

    def test_accepts_trailing_slash(self, file_io):
        """Verify that get_state_file_path accepts trailing slash in directory path."""
        result = file_io.get_state_file_path("/some/dir/")
        assert result == Path("/some/dir") / _STATE_FILE_NAME

    def test_returns_path_object(self, file_io):
        """Verify that get_state_file_path returns a Path object."""
        result = file_io.get_state_file_path("/any/dir")
        assert isinstance(result, Path)


# ================================================================== #
# write_state
# ================================================================== #

class TestWriteState:
    def test_creates_directory_if_absent(self, file_io, minimal_state):
        """Verify that write_state creates directory if absent."""
        m = mock_open()
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.mkdir") as mock_mkdir, \
             patch("builtins.open", m):
            file_io.write_state("/new/dir", minimal_state)
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_writes_json_to_state_file(self, file_io, minimal_state):
        """Verify that write_state writes valid JSON to state file."""
        m = mock_open()
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.mkdir"), \
             patch("builtins.open", m):
            file_io.write_state("/some/dir", minimal_state)
        handle = m()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        # Must be valid JSON and round-trip back to the same state
        parsed = PersistedViewerStateV1.model_validate_json(written)
        assert parsed.version == minimal_state.version

    def test_opens_file_in_write_mode(self, file_io, minimal_state):
        """Verify that write_state opens file in write mode."""
        m = mock_open()
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.mkdir"), \
             patch("builtins.open", m):
            file_io.write_state("/some/dir", minimal_state)
        expected_path = Path("/some/dir") / _STATE_FILE_NAME
        m.assert_called_once_with(expected_path, "w")

    def test_returns_path_to_written_file(self, file_io, minimal_state):
        """Verify that write_state returns path to written file."""
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.mkdir"), \
             patch("builtins.open", mock_open()):
            result = file_io.write_state("/some/dir", minimal_state)
        assert result == Path("/some/dir") / _STATE_FILE_NAME


# ================================================================== #
# read_state
# ================================================================== #

class TestReadState:
    def test_returns_persisted_state_from_valid_json(self, file_io, minimal_state):
        """Verify that read_state returns persisted state."""
        json_bytes = minimal_state.model_dump_json()
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=json_bytes)):
            result = file_io.read_state("/some/dir")
        assert isinstance(result, PersistedViewerStateV1)
        assert result.version == minimal_state.version

    def test_raises_file_not_found_when_state_file_missing(self, file_io):
        """Verify that read_state raises FileNotFoundError when state file is missing."""
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="State file not found"):
                file_io.read_state("/missing/dir")

    def test_opens_file_in_read_mode(self, file_io, minimal_state):
        """Verify that read_state opens file in read mode."""
        json_bytes = minimal_state.model_dump_json()
        m = mock_open(read_data=json_bytes)
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.exists", return_value=True), \
             patch("builtins.open", m):
            file_io.read_state("/some/dir")
        expected_path = Path("/some/dir") / _STATE_FILE_NAME
        m.assert_called_once_with(expected_path, "r")

    def test_propagates_invalid_json(self, file_io):
        """Verify that read_state propagates exception on invalid json."""
        with patch("ansys.visor.viewer.vtk.io.visor_file_io.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="not json")):
            with pytest.raises(Exception):
                file_io.read_state("/some/dir")


# ================================================================== #
# resolve_input
# ================================================================== #

class TestResolveInput:
    def test_returns_none_when_input_is_none(self, file_io):
        """Verify that resolve_input returns None when input is None."""
        assert file_io.resolve_input(None) is None

    def test_returns_dataset_unchanged_when_vtk_object(self, file_io):
        """Verify that resolve_input returns dataset unchanged when vtk object."""
        dummy = vtkPolyData()
        assert file_io.resolve_input(dummy) is dummy

    def test_reads_dataset_from_disk_when_str(self, file_io):
        """Verify that resolve_input reads dataset from disk when input is str."""
        mock_dataset = MagicMock()
        with patch.object(file_io, "read_dataset", return_value=mock_dataset) as mock_read:
            result = file_io.resolve_input("/some/model.vtu")
            mock_read.assert_called_once_with("/some/model.vtu")
            assert result is mock_dataset

    def test_raises_type_error_on_unsupported_type(self, file_io):
        """Verify that resolve_input raises TypeError on unsupported type."""
        with pytest.raises(TypeError, match="Unsupported input type"):
            file_io.resolve_input(12345)


# ================================================================== #
# write_dataset
# ================================================================== #

class TestWriteDataset:
    def test_delegates_to_dataset_to_file(self, file_io, tmp_path):
        """Verify that write_dataset delegates to dataset_to_file."""
        dest = tmp_path / "snap.vtkhdf"
        dataset = MagicMock()
        with patch(
            "ansys.visor.viewer.vtk.io.visor_file_io.dataset_to_file",
            return_value=dest,
        ) as mock_fn:
            result = file_io.write_dataset(dest, dataset)
            mock_fn.assert_called_once_with(dest, dataset)
            assert result == dest

    def test_returns_path_from_dataset_to_file(self, file_io, tmp_path):
        """Verify that write_dataset returns path from dataset_to_file."""
        dest = tmp_path / "snap.vtkhdf"
        with patch(
            "ansys.visor.viewer.vtk.io.visor_file_io.dataset_to_file",
            return_value=dest,
        ):
            assert file_io.write_dataset(dest, MagicMock()) == dest


# ================================================================== #
# resolve_metadata
# ================================================================== #


class TestResolveMetadata:
    def test_returns_default_metadata_when_none_and_no_input(self, file_io):
        """Verify that resolve_metadata returns default metadata when no input is provided."""
        result = file_io.resolve_metadata(None, None)
        assert isinstance(result, Metadata)
        assert result.name == "model"
        assert result.unit == ""

    def test_infers_name_from_file_path_when_metadata_is_none(self, file_io):
        """Verify that resolve_metadata infers name from file path when metadata is None."""
        result = file_io.resolve_metadata(None, "/some/path/my_dataset.vtp")
        assert result.name == "my_dataset"

    def test_infers_name_from_vtkhdf_file_path(self, file_io):
        """Verify that resolve_metadata infers name from vtkhdf file path."""
        result = file_io.resolve_metadata(None, "/some/path/mesh_snapshot.vtkhdf")
        assert result.name == "mesh_snapshot"

    def test_falls_back_to_model_when_input_is_not_str(self, file_io):
        """Verify that resolve_metadata falls back to 'model' when input is not str."""
        result = file_io.resolve_metadata(None, vtkPolyData())
        assert result.name == "model"

    def test_returns_metadata_instance_unchanged(self, file_io):
        """Verify that resolve_metadata returns Metadata instance unchanged."""
        dummy = Metadata(name="test", unit="m")
        assert file_io.resolve_metadata(dummy, None) is dummy

    def test_reads_metadata_from_disk_when_str(self, file_io):
        """Verify that resolve_metadata reads metadata from disk when input is str."""
        mock_metadata = Metadata(name="from_file", unit="mm")
        with patch.object(file_io, "read_metadata", return_value=mock_metadata) as mock_read:
            result = file_io.resolve_metadata("/some/meta.json", None)
            mock_read.assert_called_once_with("/some/meta.json")
            assert result is mock_metadata

    def test_raises_type_error_on_unsupported_type(self, file_io):
        """Verify that resolve_metadata raises TypeError on unsupported type."""
        with pytest.raises(TypeError, match="Unsupported metadata type"):
            file_io.resolve_metadata(42, None)


# ================================================================== #
# resolve
# ================================================================== #

class TestResolve:
    def test_returns_none_dataset_and_default_metadata_when_both_none(self, file_io):
        """Verify that resolve returns None dataset and default metadata when both inputs are None."""
        dataset, ext_meta = file_io.resolve(None, None)
        assert dataset is None
        assert isinstance(ext_meta, ExtendedMetadata)
        assert ext_meta.name == "model"
        assert ext_meta.file_path is None
        assert ext_meta.metadata_path is None

    def test_sets_file_path_when_input_is_str(self, file_io):
        """Verify that resolve() sets file_path when input is str."""
        mock_dataset = MagicMock()
        with patch.object(file_io, "resolve_input", return_value=mock_dataset), \
             patch.object(file_io, "resolve_metadata", return_value=Metadata(name="m", unit="")):
            _, ext_meta = file_io.resolve("/path/model.vtu", None)
        assert ext_meta.file_path == "/path/model.vtu"

    def test_does_not_set_file_path_when_input_is_not_str(self, file_io):
        """Verify that resolve() does not set file_path when input is not str."""
        dummy = vtkPolyData()
        with patch.object(file_io, "resolve_metadata", return_value=Metadata(name="m", unit="")):
            _, ext_meta = file_io.resolve(dummy, None)
        assert ext_meta.file_path is None

    def test_sets_metadata_path_when_metadata_is_str(self, file_io):
        """Verify that resolve() sets metadata_path when metadata is str."""
        mock_metadata = Metadata(name="m", unit="")
        with patch.object(file_io, "resolve_input", return_value=None), \
             patch.object(file_io, "resolve_metadata", return_value=mock_metadata):
            _, ext_meta = file_io.resolve(None, "/path/meta.json")
        assert ext_meta.metadata_path == "/path/meta.json"

    def test_does_not_set_metadata_path_when_metadata_is_not_str(self, file_io):
        """Verify that resolve() does not set metadata_path when metadata is not str."""
        dummy_meta = Metadata(name="m", unit="")
        with patch.object(file_io, "resolve_input", return_value=None):
            _, ext_meta = file_io.resolve(None, dummy_meta)
        assert ext_meta.metadata_path is None

    def test_returns_extended_metadata_type(self, file_io):
        """Verify that resolve() returns ExtendedMetadata type."""
        _, ext_meta = file_io.resolve(None, None)
        assert isinstance(ext_meta, ExtendedMetadata)

    def test_delegates_to_resolve_input_and_resolve_metadata(self, file_io):
        """Verify that resolve() delegates to resolve_input and resolve_metadata."""
        mock_dataset = MagicMock()
        mock_metadata = Metadata(name="x", unit="y")
        with patch.object(file_io, "resolve_input", return_value=mock_dataset) as mock_ri, \
             patch.object(file_io, "resolve_metadata", return_value=mock_metadata) as mock_rm:
            dataset, _ = file_io.resolve("input.vtu", "meta.json")
            mock_ri.assert_called_once_with("input.vtu")
            mock_rm.assert_called_once_with("meta.json", "input.vtu")
            assert dataset is mock_dataset


# ================================================================== #
# build_metadata_for_load_state
# ================================================================== #

class TestBuildMetadataForLoadState:
    def _make_state(self, **kwargs) -> PersistedDatasetState:
        return PersistedDatasetState(**kwargs)

    def test_returns_extended_metadata(self, file_io):
        """Verify that build_metadata_for_load_state returns ExtendedMetadata."""
        ds_state = self._make_state()
        result = file_io.build_metadata_for_load_state("my_model", "m", ds_state)
        assert isinstance(result, ExtendedMetadata)

    def test_name_and_unit_are_set_from_arguments(self, file_io):
        """Verify that name and unit are set from arguments."""
        ds_state = self._make_state()
        result = file_io.build_metadata_for_load_state("my_model", "mm", ds_state)
        assert result.name == "my_model"
        assert result.unit == "mm"

    def test_none_unit_becomes_empty_string(self, file_io):
        """Verify that None unit becomes empty string."""
        ds_state = self._make_state()
        result = file_io.build_metadata_for_load_state("model", None, ds_state)
        assert result.unit == ""

    def test_file_path_comes_from_source_file_path(self, file_io):
        """Verify that file path comes from source file path."""
        ds_state = self._make_state(source_file_path="/orig/mesh.vtu")
        result = file_io.build_metadata_for_load_state("mesh", "m", ds_state)
        assert result.file_path == "/orig/mesh.vtu"

    def test_metadata_path_comes_from_source_metadata_path(self, file_io):
        """Verify that metadata path comes from source metadata path."""
        ds_state = self._make_state(source_metadata_path="/orig/meta.json")
        result = file_io.build_metadata_for_load_state("mesh", "m", ds_state)
        assert result.metadata_path == "/orig/meta.json"

    def test_file_path_is_none_when_source_absent(self, file_io):
        """Verify that file path is None when source file path is absent."""
        ds_state = self._make_state()
        result = file_io.build_metadata_for_load_state("model", "m", ds_state)
        assert result.file_path is None

    def test_state_is_the_persisted_dataset_state(self, file_io):
        """Verify that state is the PersistedDatasetState."""
        ds_state = self._make_state(serialized_dataset_path="/save/snap.vtkhdf")
        result = file_io.build_metadata_for_load_state("model", "m", ds_state)
        assert result.state is ds_state
        assert result.state.serialized_dataset_path == "/save/snap.vtkhdf"

    def test_all_fields_populated_together(self, file_io):
        """Verify that all fields are populated together."""
        ds_state = self._make_state(
            source_file_path="/orig/mesh.vtu",
            source_metadata_path="/orig/meta.json",
            serialized_dataset_path="/save/mesh_snapshot.vtkhdf",
        )
        result = file_io.build_metadata_for_load_state("mesh", "mm", ds_state)
        assert result.name == "mesh"
        assert result.unit == "mm"
        assert result.file_path == "/orig/mesh.vtu"
        assert result.metadata_path == "/orig/meta.json"
        assert result.state.serialized_dataset_path == "/save/mesh_snapshot.vtkhdf"


# ================================================================== #
# _try_unlink
# ================================================================== #

class TestTryUnlink:
    def test_deletes_file_and_returns_true(self, tmp_path):
        """Verify that _try_unlink deletes file and returns True."""
        f = tmp_path / "snap.vtkhdf"
        f.touch()
        assert _try_unlink(f) is True
        assert not f.exists()

    def test_returns_false_on_permission_error(self, tmp_path):
        """Verify that _try_unlink returns False on PermissionError."""
        f = tmp_path / "snap.vtkhdf"
        f.touch()
        with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            assert _try_unlink(f) is False

    def test_logs_warning_on_permission_error(self, tmp_path):
        """Verify that _try_unlink logs warning on PermissionError."""
        f = tmp_path / "snap.vtkhdf"
        f.touch()
        with patch.object(Path, "unlink", side_effect=PermissionError("locked")), \
             patch("ansys.visor.viewer.vtk.io.visor_file_io.logger") as mock_log:
            _try_unlink(f)
            mock_log.warning.assert_called_once()

    def test_propagates_other_errors(self, tmp_path):
        """Verify that _try_unlink propagates other errors."""
        f = tmp_path / "snap.vtkhdf"
        f.touch()
        with patch.object(Path, "unlink", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                _try_unlink(f)


# ================================================================== #
# delete_stale_snapshots
# ================================================================== #

class TestDeleteStaleSnapshots:
    def _make_state(self, dataset_states: dict) -> PersistedViewerStateV1:
        from ansys.visor.viewer.models.common.visor_ui_state import VisorUIState
        return PersistedViewerStateV1.from_components(
            ui_state=VisorUIState(), unit="m", orthographic_enabled=None,
            cross_section_enabled=None, edges_enabled=None, bounding_box_enabled=None,
            datasets=dataset_states
        )

    def test_deletes_vtkhdf_not_in_state(self, file_io, tmp_path):
        """Verify that make_state deletes vtkhdf not in state."""
        stale = tmp_path / "old_snapshot.vtkhdf"
        stale.touch()
        state = self._make_state({})  # no datasets ??? no kept paths

        deleted = file_io.delete_stale_snapshots(str(tmp_path), state)

        assert not stale.exists()
        assert stale in deleted

    def test_keeps_vtkhdf_referenced_in_state(self, file_io, tmp_path):
        """Verify that make_state keeps vtkhdf referenced in state."""
        kept = tmp_path / "plate_snapshot.vtkhdf"
        kept.touch()
        ds_state = PersistedDatasetState(serialized_dataset_path=str(kept))
        state = self._make_state({"plate": ds_state})

        deleted = file_io.delete_stale_snapshots(str(tmp_path), state)

        assert kept.exists()
        assert kept not in deleted

    def test_deletes_stale_and_keeps_current_simultaneously(self, file_io, tmp_path):
        """Verify that make_state deletes stale and keeps current simultaneously."""
        stale = tmp_path / "removed_snapshot.vtkhdf"
        current = tmp_path / "plate_snapshot.vtkhdf"
        stale.touch()
        current.touch()
        ds_state = PersistedDatasetState(serialized_dataset_path=str(current))
        state = self._make_state({"plate": ds_state})

        deleted = file_io.delete_stale_snapshots(str(tmp_path), state)

        assert not stale.exists()
        assert current.exists()
        assert stale in deleted
        assert current not in deleted

    def test_does_not_delete_non_vtkhdf_files(self, file_io, tmp_path):
        """Verify that make_state does not delete non vtkhdf files."""
        other = tmp_path / "visor.json"
        other.touch()
        state = self._make_state({})

        file_io.delete_stale_snapshots(str(tmp_path), state)

        assert other.exists()

    def test_returns_empty_list_when_nothing_to_delete(self, file_io, tmp_path):
        """Verify that make_state returns empty list when nothing to delete."""
        kept = tmp_path / "plate_snapshot.vtkhdf"
        kept.touch()
        ds_state = PersistedDatasetState(serialized_dataset_path=str(kept))
        state = self._make_state({"plate": ds_state})

        deleted = file_io.delete_stale_snapshots(str(tmp_path), state)

        assert deleted == []

    def test_ignores_dataset_state_with_no_snapshot_path(self, file_io, tmp_path):
        """Verify that make_state ignores dataset state with no snapshot path."""
        stale = tmp_path / "old_snapshot.vtkhdf"
        stale.touch()
        ds_state = PersistedDatasetState(serialized_dataset_path=None)
        state = self._make_state({"plate": ds_state})

        deleted = file_io.delete_stale_snapshots(str(tmp_path), state)

        assert stale not in [p for p in [stale] if stale.exists()]
        assert stale in deleted  # None path doesn't protect anything

