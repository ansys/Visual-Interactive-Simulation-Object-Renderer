"""Filesystem I/O helpers for Visor.

:class:`VisorFileIO` owns every interaction between the application and the
filesystem.  Keeping this logic here means
:class:`~ansys.visor.viewer.app.visor_vtk.VisorVTK`
never needs to know about ``Path``, ``open``, or JSON serialisation details.

Responsibilities (current scope):

General file reading (used at start / add_dataset time):
- Reading a VTK dataset from a file path on disk.
- Reading a metadata JSON file from disk into a
  :class:`~ansys.visor.viewer.core.metadata.Metadata` object.

Save/load state:
- Resolving the canonical ``visor.json`` path inside a save directory.
- Writing a :class:`~ansys.visor.viewer.models.persist.persisted_viewer_state.PersistedViewerStateV1`
  to ``visor.json``.
- Reading and parsing ``visor.json`` back into a
  :class:`~ansys.visor.viewer.models.persist.persisted_viewer_state.PersistedViewerStateV1`.
- Writing in-memory ``vtkDataObject`` instances to disk as VTKHDF snapshots.
"""

import json
from pathlib import Path

from ansys.visor.viewer.core.metadata import ExtendedMetadata, Metadata
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.persist.dataset.persisted_dataset_state import PersistedDatasetState
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.vtk.io.dataset_to_file import dataset_to_file
from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset

logger = VisorDefaultLogger(__name__)

_STATE_FILE_NAME = "visor.json"
_DATASET_SNAPSHOT_NAME_SUFFIX = "_snapshot"
_DATASET_SNAPSHOT_EXTENSION = "vtkhdf"


def _try_unlink(path: Path) -> bool:
    """Delete *path*, returning ``True`` on success.

    On Windows, ``vtkHDFReader`` registers multiblock HDF5 files in a global
    HDF5 C-library context that cannot be released from Python.  If the file
    is still locked a ``PermissionError`` is caught, a warning is logged, and
    ``False`` is returned so the caller can decide how to proceed.
    """
    try:
        path.unlink()
        return True
    except PermissionError:
        logger.warning(
            f"Could not delete stale snapshot '{path}': file is locked "
            f"(likely by VTK's HDF5 reader).  It will be removed on the next save."
        )
        return False


class VisorFileIO:
    """Handles all filesystem I/O for Visor.

    This class is stateless — all methods are independent of one another and
    require only their explicit arguments.  There is no need to instantiate it
    with any configuration; a single instance can be shared or a new one
    created per operation.
    """

    # ------------------------------------------------------------------
    # General file reading  (used at start / add_dataset time)
    # ------------------------------------------------------------------

    def read_dataset(self, path: str) -> VisorDatasetType:
        """Load a VTK dataset from *path* and return the ``vtkDataObject``.

        Args:
            path: Absolute or relative path to a ``.vtu``, ``.vtp``, ``.vtm``,
                or ``.vtkhdf`` file.

        Returns:
            The loaded VTK dataset object.
        """
        return file_to_dataset(path)

    def read_snapshot(self, path: str) -> VisorDatasetType:
        """Load a VTKHDF snapshot from *path*, keeping the original file unlocked.

        Identical to :meth:`read_dataset` except that VTKHDF files are read via
        a temporary copy so the HDF5 global lock (which cannot be released from
        Python) lands on the disposable copy rather than the original.  Use this
        when reading from ``save_dir`` so that ``save_state`` can later overwrite
        or delete the file without hitting a Windows file-lock error.

        Args:
            path: Absolute or relative path to a ``.vtkhdf`` snapshot file.

        Returns:
            The loaded VTK dataset object.
        """
        return file_to_dataset(path)

    def read_metadata(self, path: str) -> Metadata:
        """Parse a metadata JSON file at *path* and return a :class:`Metadata` object.

        Args:
            path: Absolute or relative path to a JSON file whose contents
                match the :class:`~ansys.visor.viewer.core.metadata.Metadata` schema.

        Returns:
            The deserialised :class:`Metadata` instance.
        """
        with open(path, "rb") as fh:
            metadata_dict = json.load(fh)
        return Metadata(**metadata_dict)

    def resolve(
            self,
            input: str | VisorDatasetType | None,
            metadata: str | Metadata | None,
    ) -> tuple[VisorDatasetType | None, ExtendedMetadata]:
        """Resolve a raw user-supplied *input* and *metadata* into concrete typed values.

        Accepts any combination the public API allows — file paths, VTK objects,
        ``Metadata`` instances, or ``None`` — and returns a normalised pair ready
        for :meth:`~ansys.visor.viewer.vtk.scene.base.VisorSceneBase.add_dataset`.

        Args:
            input: A file path string, a ``vtkDataObject``, or ``None``.
            metadata: A file path string, a :class:`Metadata` instance, or ``None``.

        Returns:
            A ``(dataset, extended_metadata)`` tuple.  *dataset* is ``None`` when
            *input* is ``None``.
        """
        loaded_input = self.resolve_input(input)
        loaded_metadata = self.resolve_metadata(metadata, input)

        extended_metadata = ExtendedMetadata(**loaded_metadata.model_dump())
        if isinstance(input, str):
            extended_metadata.file_path = input
        if isinstance(metadata, str):
            extended_metadata.metadata_path = metadata

        return loaded_input, extended_metadata

    def resolve_input(self, input: str | VisorDatasetType | None) -> VisorDatasetType | None:
        """Resolve *input* to a ``vtkDataObject``, reading from disk if it is a path.

        Args:
            input: A file path string, a ``vtkDataObject``, or ``None``.

        Returns:
            The resolved dataset, or ``None`` if *input* is ``None``.
        """
        if input is None:
            return None

        if isinstance(input, VisorDatasetType):
            return input

        if not isinstance(input, str):
            raise TypeError(f"Unsupported input type: {type(input).__name__}")

        return self.read_dataset(input)

    def resolve_metadata(
            self,
            metadata: str | Metadata | None,
            input: str | VisorDatasetType | None
    ) -> Metadata:
        """Resolve *metadata* to a :class:`Metadata` instance, reading from disk if it is a path.

        Returns a default ``Metadata(name="model", unit="")`` when *metadata* is ``None``.

        Args:
            metadata: A file path string, a :class:`Metadata` instance, or ``None``.
            input: A file path string, a ``vtkDataObject``, or ``None``.  Used to infer a default name for the metadata
                   when *metadata* is None.
        Returns:
            The resolved :class:`Metadata` instance.
        """
        if metadata is None:
            # If there is no metadata provided, set the asset name to the file name (without extension)
            # if input is not a string, default to "model" to avoid issues with unnamed datasets.
            name = Path(input).stem if isinstance(input, str) else "model"
            return Metadata(name=name, unit="")

        if isinstance(metadata, Metadata):
            return metadata

        if not isinstance(metadata, str):
            raise TypeError(f"Unsupported metadata type: {type(metadata).__name__}")

        return self.read_metadata(metadata)

    # ------------------------------------------------------------------
    # Save / load state
    # ------------------------------------------------------------------

    def get_state_file_path(self, state_dir: str) -> Path:
        """Return the canonical path to ``visor.json`` inside *state_dir*.

        Args:
            state_dir: Directory that contains (or will contain) the state file.

        Returns:
            :class:`pathlib.Path` pointing at ``<state_dir>/visor.json``.
        """
        return Path(state_dir) / _STATE_FILE_NAME

    def get_persisted_dataset_path(self, state_dir: str, dataset_name: str) -> Path:
        """Return the canonical path to a persisted dataset snapshot inside *state_dir*.

        Args:
            state_dir: Directory that contains (or will contain) the persisted dataset snapshot.
            dataset_name: Name of the dataset (used to generate a unique file name).

        Returns:
            :class:`pathlib.Path` pointing at the expected location of the persisted dataset snapshot.
        """
        filename = f"{dataset_name}{_DATASET_SNAPSHOT_NAME_SUFFIX}"
        return (Path(state_dir) / filename).with_suffix(f".{_DATASET_SNAPSHOT_EXTENSION}")

    def write_dataset(self, path: str | Path, dataset: VisorDatasetType) -> Path:
        """Write *dataset* to disk as a VTKHDF file at *path*.

        Delegates to :func:`~ansys.visor.viewer.vtk.io.dataset_to_file.dataset_to_file`.

        Args:
            path: Destination file path (should end with ``.vtkhdf``).
            dataset: The VTK data object to serialise.

        Returns:
            The :class:`pathlib.Path` of the file that was written.
        """
        dest = dataset_to_file(path, dataset)
        logger.info(f"Dataset snapshot written to {dest}")
        return dest

    def build_metadata_for_load_state(
            self,
            dataset_name: str,
            unit: str | None,
            dataset_state: "PersistedDatasetState",
    ) -> ExtendedMetadata:
        """Build an :class:`ExtendedMetadata` for a dataset being restored from a save-state directory.

        The returned object carries:

        * ``name`` / ``unit`` — taken from the persisted scene (stable across sessions).
        * ``file_path`` — set to ``source_file_path`` when available, so the registry
          records where the data originally came from.
        * ``metadata_path`` — set to ``source_metadata_path`` when available.
        * ``state`` — the full :class:`PersistedDatasetState` (parts + paths) so that
          part visibility and the serialized snapshot path are preserved.

        Args:
            dataset_name: The stable dataset name stored in ``visor.json``.
            unit: The scene unit stored in ``visor.json`` (may be ``None``).
            dataset_state: The :class:`PersistedDatasetState` for this dataset.

        Returns:
            A fully populated :class:`ExtendedMetadata` ready to pass to
            :meth:`~ansys.visor.viewer.vtk.scene.base.VisorSceneBase.add_dataset`.
        """
        return ExtendedMetadata(
            name=dataset_name,
            unit=unit or "",
            state=dataset_state,
            file_path=dataset_state.source_file_path,
            metadata_path=dataset_state.source_metadata_path,
        )

    def delete_stale_snapshots(self, state_dir: str, state: PersistedViewerStateV1) -> list[Path]:
        """Delete VTKHDF snapshot files in *state_dir* that are no longer referenced by *state*.

        Any ``*.vtkhdf`` file found in *state_dir* whose path does not appear in
        ``state.scene.dataset_states`` is removed.  This prevents snapshots from
        previous saves accumulating on disk after a dataset has been removed.

        Args:
            state_dir: Directory that was just written by :meth:`write_state`.
            state: The state that was just persisted — only snapshots referenced
                   here are kept.

        Returns:
            A list of :class:`pathlib.Path` objects for the files that were deleted.
        """
        kept_paths = {
            Path(ds.serialized_dataset_path)
            for ds in state.scene.dataset_states.values()
            if ds.serialized_dataset_path
        }
        deleted: list[Path] = []
        for candidate in Path(state_dir).glob(f"*.{_DATASET_SNAPSHOT_EXTENSION}"):
            if candidate not in kept_paths:
                if _try_unlink(candidate):
                    deleted.append(candidate)
                    logger.info(f"Deleted stale snapshot: {candidate}")
        return deleted

    def write_state(self, state_dir: str, state: PersistedViewerStateV1) -> Path:
        """Serialise *state* to ``visor.json`` inside *state_dir*.

        The directory is created if it does not already exist.

        Args:
            state_dir: Target directory.  Created (including parents) if absent.
            state: The persisted viewer state to write.

        Returns:
            The :class:`pathlib.Path` of the file that was written.
        """
        state_file = self.get_state_file_path(state_dir)
        Path(state_dir).mkdir(parents=True, exist_ok=True)

        json_string = state.model_dump_json(indent=4, by_alias=True)
        with open(state_file, "w") as fh:
            fh.write(json_string)

        logger.info(f"State saved to {state_file}")
        return state_file

    def read_state(self, state_dir: str) -> PersistedViewerStateV1:
        """Read and parse ``visor.json`` from *state_dir*.

        Args:
            state_dir: Directory that contains ``visor.json``.

        Returns:
            The deserialised :class:`PersistedViewerStateV1`.

        Raises:
            FileNotFoundError: If ``visor.json`` does not exist in *state_dir*.
        """
        state_file = self.get_state_file_path(state_dir)
        if not state_file.exists():
            msg = f"State file not found: {state_file}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        with open(state_file, "r") as fh:
            json_string = fh.read()

        state = PersistedViewerStateV1.model_validate_json(json_string)
        logger.info(f"State loaded from {state_file}")
        return state
