import urllib
from asyncio import Task
from typing import Any, Awaitable, Dict, List, Type

import ansys.visor.viewer.core.errors as errors
from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.metadata import Metadata
from ansys.visor.viewer.core.visor_enums import RenderingEngine, RenderingMode
from ansys.visor.viewer.core.visor_helpers import validate_url
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables

logger = VisorDefaultLogger(__name__)



class Visor:
    """
    Base class that provides an interface for initializing and managing a
    visualization app.

    This class supports server-based rendering and interaction with a visualization pipeline.

    Parameters
    ----------
    rendering_engine : RenderingEngine, default: RenderingEngine.VTK
       Rendering engine to use for visualization.
    url : str, default: None
       URL to connect to an existing server instance or to create a new one.
    standalone : bool, default: True
       Whether to use the standalone client path or
       the Dash component in a Dash app.
    dark_mode : bool, Default: None
       Whether to use dark mode for the app. If ``None``,
       the default dark mode setting from the configuration is used.
    """
    def __new__(cls,
                rendering_engine: RenderingEngine = RenderingEngine.VTK,
                rendering_mode: RenderingMode = RenderingMode.LOCAL,
                url: str | None = None,
                standalone: bool = True,
                dark_mode: bool | None = None,
                **kwargs,
                ) -> "Visor":
        """
        Validates the rendering engine and returns a Visor instance.

        This is a factory method to return an instance of a subclass
        that is determined by the ``rendering_engine`` enum value provided as input.
        """
        if cls is not Visor:
            return super().__new__(cls)

        rendering_engine = RenderingEngine.from_string(rendering_engine)
        rendering_mode = RenderingMode.from_string(rendering_mode)

        from ansys.visor.viewer.app.visor_vtk import VisorVTK

        engine_map: dict[RenderingEngine, Type[Visor]] = {
            RenderingEngine.VTK: VisorVTK,
        }

        engine_class = engine_map.get(rendering_engine, None)

        if not engine_class:
            raise ValueError((
                    f"Unsupported rendering engine: {rendering_engine}.  "
                    f"Valid values: {list(engine_map.keys())}."
                ))
        # Delegate to the engine class's __new__, passing rendering_mode through.
        return engine_class.__new__(engine_class, rendering_mode=rendering_mode, **kwargs)

    def __init__(
            self,
            url: str | None = None,
            standalone: bool = True,
            dark_mode: bool | None = None,
    ):
        """
        Initializes the Visor instance with the provided parameters.
        """
        self._set_default_url(url)
        self._standalone: bool = standalone
        self._dark_mode: bool = dark_mode if dark_mode is not None else settings.default_dark_mode
        logger.debug(f"Dash flag: {self._standalone}")

    """ Properties """
    @property
    def url(self):
        """URL of the server."""
        return self._url

    @property
    def host(self):
        """Host of the server."""
        return self._host

    @property
    def port(self):
        """Port of the server."""
        return self._port

    @property
    def standalone(self):
        """Dash flag of the server"""
        return self._standalone

    @property
    def dark_mode(self):
        """Dark mode flag of the server"""
        return self._dark_mode

    """ Public Methods """
    def info(self) -> dict:
        """Return a dictionary with information about the VISOR instance."""
        return {
            "app_name": settings.app_name,
            "host": self.host,
            "port": self.port,
            "standalone": self.standalone,
            "datasets": [dataset.get("name") for dataset in self.list_datasets().values()],
            "metadata": getattr(self, "_metadata", None),
        }

    """ Synchronous Abstract Methods """
    def start(self,
              input: str | VisorDatasetType | None = None,
              metadata: Metadata | None = None,
              timeout: int = 0,
              blocking: bool = False,
              ) -> int | None:
        """ Start the server and app synchronously. """
        raise NotImplementedError()

    def stop(self) -> None:
        """Stop the server. """
        raise NotImplementedError()

    def update(self,
               input: str | VisorDatasetType,
               metadata: Metadata | None = None
               ) -> int:
        """Updates the model with a new input file and metadata. """
        raise NotImplementedError()

    def save_state(self, state_dir: str) -> None:
        """Save the app state to a JSON file. """
        raise NotImplementedError()

    def load_state(self, state_dir: str) -> None:
        """Load the app state from a JSON file. """
        raise NotImplementedError()

    def _health(self) -> None:
        """Return the health status of the server. """
        raise NotImplementedError()


    """ Protected Async Abstract Methods (for use in the FastAPI endpoints) """
    async def _start_async(
            self, input: str | VisorDatasetType | None = None,
            metadata: Metadata | None = None,
            timeout: int = 0) -> tuple[int | None, Awaitable]:
        """Start the server and app asynchronously. """
        raise NotImplementedError()

    async def _stop_async(self) -> Task:
        """Stop the server asynchronously. """
        raise NotImplementedError()

    def add_dataset(self,
                    input: str | VisorDatasetType,
                    metadata: Metadata | None = None
                    ) -> int:
        """Add a dataset to the scene and return its dataset ID."""
        raise NotImplementedError

    def remove_dataset(self, dataset_id: int) -> None:
        """Remove a dataset from the scene."""
        raise NotImplementedError

    def list_datasets(self) -> dict:
        """List the available datasets in the scene."""
        raise NotImplementedError

    def list_variables(self, dataset_id: int) -> List[VisorPartVariables]:
        """
        List the variables for a dataset.

        Parameters
        ----------
        dataset_id : int
            ID of the dataset to query.

        Returns
        -------
        List[VisorVariable]
           List of variables available for the specified dataset.

        Raises
        ------
        RuntimeError
            If the variables cannot be listed.
        """
        raise NotImplementedError

    def update_variables(self, dataset_id: int, variables: List[Dict[str, Any]]) -> None:
        """
        Update variables for a dataset.

        Parameters
        ----------
        dataset_id : int
            ID of the dataset to update.
        variables : List[Dict[str, Any]]
            List of dictionaries describing variable updates.

        Raises
        ------
        RuntimeError
            If the update operation fails.

        Notes
        -----
        Each dictionary must include:

        - ``type`` (str or VisorVtkVariableType): "POINT" or "CELL"
        - ``name`` (str): Non-empty variable name
        - ``num_components`` (int): Number of components (> 0)
        - ``data`` (array-like): List, tuple, or numpy.ndarray shaped
          as (num_points, num_components) or a flat list divisible by ``num_components``.

        """
        raise NotImplementedError

    """ Protected Methods """
    def _set_default_url(self, url: str | None) -> None:
        """Validate and parse the provided URL, set as default if None"""
        if url is None:
            scheme = settings.url_scheme
            url = f"{scheme}://{settings.default_host}:{settings.default_port}"
            logger.debug(f"Initializing server with default url {url}")
            self._host = settings.default_host
            self._port = settings.default_port
            # Exposed/binding host may be provided by evaluator via settings.binding_host
            self._binding_host = settings.binding_host or self._host
            # Advertised URL should use the public host (self._host), not the binding/listen host
            self._url = f"{scheme}://{self._host}:{self._port}"
            return

        self._set_url(url)

    def _set_url(self, url: str) -> None:
        """Validate and parse the provided URL"""
        if url is None:
            logger.error(f"Null url provided: {url}")
            raise errors.InvalidUrlError(f"Null url provided: {url}")

        logger.debug(f"Initializing server with url {url}")

        path = urllib.parse.urlparse(url)
        try:
            validate_url(url)
        except TypeError:
            logger.error(f"Invalid url provided: {url}")
            raise errors.InvalidUrlError(url)
        if validate_url is None:
            logger.error(f"Invalid url provided: {url}")
            raise errors.InvalidUrlError(url)

        self._host = path.hostname
        self._port = int(path.port)
        # Exposed/binding host may be provided by evaluator via settings.binding_host
        self._binding_host = settings.binding_host or self._host
        # Advertised URL should use the public host (self._host) and reflect TLS availability
        scheme = settings.url_scheme
        self._url = f"{scheme}://{self._host}:{self._port}"
