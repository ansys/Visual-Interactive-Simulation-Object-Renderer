"""Trame VTKlocal implementation of Visor class"""

import asyncio
import traceback
from abc import abstractmethod
from functools import wraps
from pathlib import Path
from typing import Any, Awaitable, Dict, List

from trame.app.core import Server

import ansys.visor.viewer.core.errors as errors
from ansys.visor.viewer import Visor
from ansys.visor.viewer.app.trame.trame_server_manager import TrameServerManager
from ansys.visor.viewer.app.visor import Metadata
from ansys.visor.viewer.core.perf_timer import PerfTimer
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.persist.persisted_viewer_state import PersistedViewerStateV1
from ansys.visor.viewer.vtk.io.visor_file_io import VisorFileIO
from ansys.visor.viewer.vtk.scene.local_scene import VisorLocalScene
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate

logger = VisorDefaultLogger(__name__)


def validate_input_metadata_types(func):
    """Decorator to validate input and metadata types."""
    @wraps(func)
    def wrapper(self, input=None, metadata=None, *args, **kwargs):
        if input is not None and not isinstance(input, (str, VisorDatasetType)):
            raise TypeError(f"input must be a str or VisorDatasetType, got {type(input).__name__}")
        # Validate metadata type if provided
        if metadata is not None and not isinstance(metadata, (str, Metadata)):
            raise TypeError(f"metadata must be a string, an instance of {Metadata.__name__} or None; got {type(metadata).__name__}")
        return func(self, input, metadata, *args, **kwargs)
    return wrapper

def require_input_is_not_none(func):
    """Decorator to ensure that the input argument is not None."""
    @wraps(func)
    def wrapper(self, input=None, *args, **kwargs):
        if input is None:
            raise ValueError("Input cannot be None")
        return func(self, input, *args, **kwargs)
    return wrapper

def require_server_off(func):
    """Decorator to ensure that the server is off."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.running:
            raise RuntimeError("Visor server already running")
        return func(self, *args, **kwargs)
    return wrapper

def require_server_on(func):
    """Decorator to ensure that the server is on."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.running:
            logger.error("Failed to find running server, try starting the server first")
            raise errors.ServerNotStartedError(
                "Failed to find running server, try starting the server first"
            )
        return func(self, *args, **kwargs)
    return wrapper

def handle_errors(action: str = "operation"):
    """Decorator to handle server errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                tb_str = traceback.format_exc()
                logger.exception(f"Error during {action}:\n{tb_str}")
                raise RuntimeError(f"Failed to {action}\n{tb_str}") from e
        return wrapper
    return decorator


class VisorVTK(Visor):
    """
    VisorVTK is a class that provides an interface for initializing and managing a
    visualization application using the VTK rendering engine.
    It supports server-based rendering and interaction with a visualization pipeline.

    Public methods:
        start(input, metadata, timeout, blocking): Starts the server and application.
        stop(): Stops the server.
        update(input, metadata): Clears the scene and loads a new dataset.
        add_dataset(input, metadata): Adds a dataset to the current scene.
        remove_dataset(dataset_id): Removes a dataset from the current scene.
        list_datasets(): Lists all datasets currently in the scene.
        clear(): Clears the scene and resets the visualization pipeline.
        list_variables(dataset_id): Lists variables for a dataset.
        update_variables(dataset_id, variables): Updates variables for a dataset.
        save_state(state_dir): Saves the application state to disk.
        load_state(state_dir): Loads the application state from disk.

    Protected methods (for use in FastAPI endpoints):
        _start_async(input, metadata, timeout): Starts the server asynchronously.
        _stop_async(): Stops the server asynchronously.
        _health(): Returns the health status of the server.

    """

    """
    Abstract base for all VTK-backed Visor implementations.

    Do not instantiate directly — use ``Visor(rendering_engine=RenderingEngine.VTK,
    rendering_mode=<mode>)`` or the short form ``Visor(rendering_mode=<mode>)``.

    Subclasses must implement :meth:`_initialize_rendering` to wire up the
    mode-specific scene and trame app.  All public API methods, error handling,
    decorators, and performance instrumentation live here.
    """

    def __new__(
        cls,
        rendering_mode: RenderingMode = RenderingMode.LOCAL,
        **kwargs,
    ) -> "VisorVTK":
        # If we are already constructing a concrete subclass, skip dispatch.
        if cls is not VisorVTK:
            return super().__new__(cls)

        rendering_mode = RenderingMode.from_string(rendering_mode)

        from ansys.visor.viewer.app.visor_vtk_local import VisorVTKLocal

        mode_map: dict[RenderingMode, type] = {
            RenderingMode.LOCAL:    VisorVTKLocal,
        }

        subclass = mode_map.get(rendering_mode)
        if subclass is None:
            valid = list(mode_map.keys())
            raise ValueError(
                f"Unsupported rendering mode for VTK: {rendering_mode!r}. "
                f"Valid values: {valid}"
            )
        return super().__new__(subclass)


    def __init__(
            self,
            url: str | None = None,
            rendering_mode: RenderingMode = RenderingMode.LOCAL,
            standalone: bool = True,
            dark_mode: bool | None = None,
            trame_log_dir: str | None = None,
    ):
        """
        Initializes the Visor class.
        Args:
            url (Optional[str]): A URL that can be used to connect to an existing
                    server instance. Defaults to None.
            standalone (bool): A flag indicating whether to use the standalone client
                    path or the dash component in a Dash application. Defaults to False.
            dark_mode (bool): A flag indicating whether to use the Dark mode
            trame_log_dir (Optional[str]): The path to the Trame log file. Defaults to None.
                    If set to a value, Trame logging is enabled (is disabled by default).
        """
        super().__init__(url, standalone, dark_mode)

        # I/O helper — owns all filesystem interactions (e.g. reading datasets, reading/writing state)
        self._file_io = VisorFileIO()

        # Initialize the server
        self._server_manager = self._initialize_server(trame_log_dir)

        # Delegate scene + trame-app construction to the subclass so that the
        # correct rendering-mode objects are created in the right order.
        self._initialize_rendering(standalone, trame_log_dir)

    @abstractmethod
    def _initialize_rendering(self, standalone: bool, trame_log_dir: str | None) -> None:
        """
        Construct ``self._scene`` and the trame app.

        Called from ``__init__`` after ``_server_manager`` and ``_file_io`` are in place.
        """

    """ Properties """
    @property
    def running(self) -> bool:
        """Returns whether the server is running."""
        return self._server_manager.running

    @property
    def server(self) -> Server:
        """Returns the Trame server instance."""
        return self._server_manager.server

    @property
    def dataset_count(self) -> int:
        """Returns the number of datasets currently in the scene."""
        return self._scene.dataset_count

    # Public Methods (Python synchronous APIs)
    @require_server_off
    @validate_input_metadata_types
    def start(self,
              input: str | VisorDatasetType | None = None,
              metadata: Metadata | None = None,
              timeout: int = 0,
              blocking: bool = False
              ) -> int | None:
        """
        Start the server synchronously.
        Does not block unless blocking is True.
        """
        dataset_id = None

        logger.info("Starting server")

        # Clear the existing scene if new input is provided
        if input is not None:
            self._scene.clear()

        # Prepare the scene with the raw data
        dataset_id = self._prepare_and_render_scene(input, metadata)

        # Start the Trame server
        self._server_manager.start(timeout, blocking)

        return dataset_id

    @require_server_on
    def stop(self):
        self._server_manager.stop()

    @handle_errors("update model")
    @require_server_on
    @require_input_is_not_none
    @validate_input_metadata_types
    def update(self,
               input: str | VisorDatasetType,
               metadata: Metadata | None = None
               ) -> int:
        """
        Clear old datasets and update the scene with the new VTK dataset.
        This function is going to remove all existing functions and add the new actor
        based on the input model.
        """
        logger.info("Updating model")

        # Clear the existing scene
        self._scene.clear()

        # Prepare the scene with the raw data
        dataset_id = self._prepare_and_render_scene(input, metadata)

        if dataset_id is None:
            raise RuntimeError("Failed to update model: dataset_id is None")

        logger.info(f"Model updated successfully with metadata {metadata}")

        return dataset_id

    @handle_errors("add_dataset")
    @require_input_is_not_none
    @validate_input_metadata_types
    def add_dataset(self,
                    input: str | VisorDatasetType,
                    metadata: Metadata | None = None
                    ) -> int:
        """
        Add a dataset to the current scene without clearing existing actors.
        This function loads the new dataset and adds it to the existing scene.
        """
        logger.info("Adding dataset")

        timer = PerfTimer("add_dataset", logger)
        dataset_id = self._prepare_and_render_scene(input, metadata, timer=timer)
        timer.log(include_total=True)

        if dataset_id is None:
            raise RuntimeError("Failed to update model: dataset_id is None")

        logger.info(f"Dataset added successfully with metadata {metadata} to instance {self.url}")

        return dataset_id

    @handle_errors("remove_dataset")
    def remove_dataset(self, dataset_id: int) -> None:
        """
        Remove a dataset from the current scene based on its dataset ID.
        """
        self._scene.remove_dataset(dataset_id)
        if self.dataset_count == 0:
            # if we've removed the last dataset, reset widgets and camera so the blank scene is normalized
            self.clear()
        else:
            self._scene.update_widgets()
            self._scene.render()
        logger.info(f"Dataset {dataset_id} successfully removed from instance {self.url}")

    @handle_errors("list_datasets")
    def list_datasets(self) -> dict:
        """
        List all datasets currently in the scene.
        Returns a dictionary with dataset IDs as keys and metadata dictionary
        (excluding the state) as values.
        """
        return self._scene.list_all_dataset_info()

    @handle_errors("clear")
    def clear(self):
        """
        Clear the current scene and reset the visualization pipeline.
        This function removes all actors from the scene and resets the state.
        """
        logger.info("Clearing the scene")
        self._scene.clear()
        self._scene.finalize_scene()
        logger.info("Scene cleared successfully")

    @handle_errors("list_variables")
    def list_variables(self, dataset_id: int) -> List[VisorPartVariables]:
        """
        List the variables of a specific dataset in the scene, grouped by part.
        Args:
            dataset_id (int): The ID of the dataset to query.
        Returns:
            List[VisorPartVariables]: Per-part variable listings. For non-composite
            datasets this is a single-element list. The part_id in each entry is
            the value to pass to update_variables when targeting that part.
        """
        return self._scene.list_variables_for_dataset(dataset_id)

    @handle_errors("update_variables")
    def update_variables(self, dataset_id: int, variables: List[Dict[str, Any]]) -> None:
        """
        Update the variables of a specific dataset in the scene.

        Args:
            dataset_id (int): The ID of the dataset to update.
            variables (List[Dict[str, Any]]): A list of variable update dictionaries.
                Each dictionary must have:
                    - type (str or VisorVtkVariableType): "POINT" or "CELL"
                    - name (str): Variable name (non-empty)
                    - num_components (int): Number of components (>0)
                    - data (array-like): Data as a list, tuple, or np.ndarray,
                      shape (num_points, num_components) or flat list divisible by num_components

        Raises:
            RuntimeError: If the update operation fails.
        """
        timer = PerfTimer(
            "update_variables", logger,
            dataset=dataset_id,
            n_vars=len(variables),
        )
        with timer.phase("from_dict"):
            variable_updates = [VisorVariableUpdate.from_dict(var) for var in variables]
        with timer.phase("update_variables_for_dataset"):
            self._scene.update_variables_for_dataset(dataset_id, variable_updates)
        timer.log(include_total=True)
        logger.info(f"Variables for dataset {dataset_id} updated successfully")

    @require_server_on
    async def save_state(self, state_dir: str, timeout: float = 5.0) -> None:
        """
        Save the current viewer state to a directory.
        Requests the runtime state from the frontend, converts it to persisted state,
        and writes it as visor.json to state_dir.

        The canonical snapshot path is always stamped onto each dataset's persisted
        state before writing, so load_state has one unambiguous place to look
        regardless of how the dataset was originally loaded.
        """
        try:
            state = await self._scene.get_state(timeout=timeout)
        except asyncio.TimeoutError as e:
            msg = (
                "Timed out waiting for the frontend to respond to `getState`.\n"
                "This typically means the Trame client is not connected/ready, or JS calls are not being processed.\n"
                f"Waited {timeout} seconds."
            )
            raise RuntimeError(msg) from e

        # Stamp the canonical snapshot path for every registered dataset.
        # The registry is the source of truth for which datasets are loaded — not
        # the frontend state, which only knows about visual/UI properties.
        for dataset_name, dataset_state in state.scene.dataset_states.items():
            dataset_state.serialized_dataset_path = str(
                self._file_io.get_persisted_dataset_path(state_dir, dataset_name)
            )

        # Write each in-memory dataset to disk as a VTKHDF snapshot.
        # Only datasets that are dirty (new or mutated since last save) are written.
        for dataset in self._scene.datasets.values():
            if not dataset.is_dirty:
                continue
            snapshot_path = self._file_io.get_persisted_dataset_path(state_dir, dataset.name)
            self._file_io.write_dataset(snapshot_path, dataset.data)
            dataset.mark_clean()

        self._file_io.write_state(state_dir, state)
        self._file_io.delete_stale_snapshots(state_dir, state)

    @handle_errors("load state")
    def load_state(self, state_dir: str) -> None:
        """
        Load viewer state from a directory.
        Reads visor.json from state_dir and applies it to the scene.

        If the dataset registry is currently empty, each dataset whose
        ``serialized_dataset_path`` exists on disk is loaded from that snapshot
        before the UI state is applied.  The ``ExtendedMetadata`` for each dataset
        is constructed from the persisted scene state so that ``name``, ``unit``,
        original source paths, and per-part state are all restored correctly.
        Datasets loaded this way start with ``is_dirty=False`` — the snapshot on
        disk already reflects their content.
        """
        state = self._file_io.read_state(state_dir)

        if self._scene.dataset_count == 0:
            self._load_datasets_from_state(state)

        self._scene.apply_state(state)

    def _load_datasets_from_state(self, state: "PersistedViewerStateV1") -> None:
        """Load all serialized dataset snapshots described in *state* into the scene.

        Only datasets whose ``serialized_dataset_path`` is set and points at an
        existing file are loaded.  Missing snapshots are skipped with a warning so
        that a partial restore does not block loading the UI state.

        Loaded datasets are immediately marked clean — the snapshot on disk is
        already up-to-date.
        """
        unit = state.scene.unit
        for dataset_name, dataset_state in state.scene.dataset_states.items():
            snapshot_path = dataset_state.serialized_dataset_path
            if not snapshot_path:
                logger.warning(
                    f"No serialized_dataset_path for dataset '{dataset_name}' — skipping dataset restore."
                )
                continue
            if not Path(snapshot_path).exists():
                logger.warning(
                    f"Snapshot not found for dataset '{dataset_name}' at '{snapshot_path}' — skipping dataset restore."
                )
                continue

            metadata = self._file_io.build_metadata_for_load_state(dataset_name, unit, dataset_state)
            data = self._file_io.read_snapshot(snapshot_path)
            dataset_id = self._scene.add_dataset(data, metadata)

            # Mark clean: the snapshot on disk matches what was just loaded.
            dataset = self._scene.datasets.get(dataset_id)
            if dataset is not None:
                dataset.mark_clean()

        if self._scene.dataset_count > 0:
            self._scene.finalize_scene(skip_reset_camera=True)

    """ Protected Methods (async start and stop for FastAPI) """
    @require_server_off
    @validate_input_metadata_types
    async def _start_async(self,
                           input: str | VisorDatasetType | None = None,
                           metadata: Metadata | None = None,
                           timeout: int = 0,
                           ) -> tuple[int | None, Awaitable]:
        """
        Start the server asynchronously. Returns
        a coroutine that represents the Trame server Task.
        """
        logger.info("Starting server")

        # Clear the existing scene if new input is provided
        if input is not None:
            self._scene.clear()

        # Prepare the scene with the raw data
        dataset_id = self._prepare_and_render_scene(input, metadata)

        server_task = await self._server_manager.start_async(timeout)
        return dataset_id, server_task

    @require_server_on
    async def _stop_async(self):
        """Stop the server asynchronously."""
        await self._server_manager.stop_async()

    def _health(self) -> bool:
        """Return the server health"""
        logger.info("Returning server state")
        return self._server_manager.health

    # Private Methods
    def _initialize_server(self, trame_log_dir: str | None) -> TrameServerManager:
        """Initialize the Trame server manager."""
        # Start Trame listening on the configured binding host (or the instance host if unset)
        listen_host = getattr(self, "_binding_host", None) or self._host
        return TrameServerManager(
            listen_host,
            self._port,
            trame_log_dir,
        )

    def _initialize_scene(self) -> VisorLocalScene:
        return VisorLocalScene(self.server, dark_mode=self._dark_mode)

    def _prepare_and_render_scene(
            self,
            input: str | VisorDatasetType | None = None,
            metadata: Metadata | None = None,
            timer: PerfTimer = None,
    ) -> int | None:
        """
        Register a dataset (if provided) then finalize the scene.

        Parameters
        ----------
        timer : PerfTimer
            Timer passed in by the caller. ``timer.phase()`` is a no-op when
            perf logging is disabled, so no branching is needed here.

        Returns
        -------
        int | None
            The dataset_id if a dataset was added, otherwise None.
        """
        if timer is None:
            timer = PerfTimer.disabled()
        dataset_id = self._register_dataset(input, metadata, timer=timer)

        with timer.phase("finalize_scene"):
            self._scene.finalize_scene()

        return dataset_id

    def _register_dataset(
            self,
            input: str | VisorDatasetType | None = None,
            metadata: Metadata | None = None,
            timer: PerfTimer = None,
    ) -> int | None:
        """
        Resolve I/O and register the dataset with the scene.
        Does **not** populate actors, reset the camera, or render.

        Parameters
        ----------
        timer : PerfTimer
            Timer passed in by the caller. ``timer.phase()`` is a no-op when
            perf logging is disabled, so no branching is needed here.

        Returns
        -------
        int | None
            The dataset_id if a dataset was registered, otherwise None.

        Raises
        ------
        errors.VisorAddDatasetError
            If a dataset was provided but could not be added to the scene.
        """
        if timer is None:
            timer = PerfTimer.disabled()
        with timer.phase("resolve_io"):
            loaded_input, loaded_metadata = self._file_io.resolve(input, metadata)

        if loaded_input is None:
            return None

        try:
            with timer.phase("add_to_scene"):
                dataset_id = self._scene.add_dataset(loaded_input, loaded_metadata)
        except Exception as e:
            raise errors.VisorAddDatasetError(
                "Failed to add dataset to scene",
                input_path=getattr(loaded_metadata, "file_path", None),
                metadata_path=getattr(loaded_metadata, "metadata_path", None),
            ) from e

        if dataset_id is None or (isinstance(dataset_id, int) and dataset_id < 0):
            raise errors.VisorAddDatasetError(
                f"Failed to add dataset to scene: invalid dataset_id returned ({dataset_id})",
                input_path=getattr(loaded_metadata, "file_path", None),
                metadata_path=getattr(loaded_metadata, "metadata_path", None),
            )

        return dataset_id
