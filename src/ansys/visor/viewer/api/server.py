"""FastAPI-based service for managing Visor visualizer instances"""

import functools
from typing import Tuple

from fastapi import (
    Body,
    FastAPI,
    HTTPException,
)

import ansys.visor.viewer.core.errors as errors
from ansys.visor.viewer import Visor
from ansys.visor.viewer.api.models import (
    Info,
    InitProps,
    LoadStateProps,
    RemoveDatasetProps,
    SaveStateProps,
    StartProps,
    UpdateProps,
    UpdateVariableProps,
)
from ansys.visor.viewer.api.visor_cache import VisorCache
from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.net import find_unused_port
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_logging import VisorLogger

logger = VisorLogger(__name__, "server.log")



def handle_exceptions(func):
    """
    Decorator for async route handlers to catch known errors,
    log them, and return appropriate HTTP responses.

    Args:
        func: The async function to wrap.

    Returns:
        The wrapped async function with error handling.
    """
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        """ Wrapper function to handle exceptions for async route handlers."""
        try:
            return await func(self, *args, **kwargs)
        except errors.VisorAddDatasetError as ade:
            # For dataset-id returning APIs, we want to surface the error and
            # return a sentinel dataset_id so clients don't mistake it for a valid ID.
            msg = f"Failed to add dataset: {ade}"
            logger.error(msg)
            return {"success": False, "dataset_id": -1, "error": msg}
        except errors.InvalidUrlError as ue:
            msg = f"Invalid URL: {ue}"
            logger.error(msg)
            raise HTTPException(status_code=422, detail=msg)
        except errors.InvalidFileError as f:
            msg = f"Invalid file: {f}"
            logger.error(msg)
            raise HTTPException(status_code=422, detail=msg)
        except errors.InvalidFileFormatError as ff:
            msg = f"Invalid file format: {ff}"
            logger.error(msg)
            raise HTTPException(status_code=422, detail=msg)
        except errors.ServerNotStartedError as se:
            msg = f"Server not started: {se}"
            logger.error(msg)
            raise HTTPException(status_code=400, detail=msg)
        except TypeError as te:
            msg = f"Type error: {te}"
            logger.error(msg)
            raise HTTPException(status_code=500, detail=msg)
        except RuntimeError as re:
            msg = f"Runtime error: {re}"
            logger.error(msg)
            raise HTTPException(status_code=500, detail=msg)
        except HTTPException:
            raise
        except Exception as e:
            msg = f"Unhandled exception: {e}"
            logger.error(msg)
            raise HTTPException(status_code=500, detail=msg)
    return wrapper


class VisorAPI:
    """
    FastAPI-based API for managing a Visor visualizer instance.

    Provides endpoints to initialize, start, update, stop,
    check the health of the visualizer, and retrieve server info

    Public route methods:
        info() -> Info
            Get the information of the visualizer instance.
        connect_or_initialize_server(init_props: InitProps)
            Connects to an existing instance on the provided host and port,
             if it exists.
            If a Visor instance has not already been initialized
             on the provided host and port, it creates it with the provided
             standalone and dark_mode properties.
        list_instances()
            Get the URL of the visualizer.
        start_instance(start_props: StartProps)
            Start the visualizer instance.
        update(update_props: UpdateProps)
            Update the input file of the visualizer instance.
        stop_visualization()
            Stop the visualization but keep the Visor instance.
        stop_instance()
            Stop the visualization and delete the Visor instance from
            the cache.
        health()
            Get the health status of the visualizer instance.

    Protected helper methods:
        _get_url(host: str, port: int) -> str
            Get the URL for a host and port.
        _initialize_visualizer(host: str, port: int) -> Visor
            Initialize a Visor instance with the given host and port.
        _stop_visualization() -> str
            Stop the visualizer instance and return the URL.
    """
    def __init__(self):
        """Initialize the VisorAPI instance."""
        self.settings = settings

        # Initialize Visor instance with default settings
        self.standalone = self.settings.default_standalone
        self.trame_log_dir = self.settings.trame_log_dir
        self.visualizer: Visor = self._connect_or_initialize_visualizer(
            self.settings.default_host,
            self.settings.default_port,
            self.settings.default_standalone,
            self.settings.default_dark_mode,
        )[0]

        # Configure FastAPI application
        self.app = FastAPI()

        # Register routes
        self.app.get("/info")(self.info)
        self.app.post("/initialize")(self.connect_or_initialize_server)
        self.app.get("/")(self.list_instances)
        self.app.post("/start")(self.start_instance)
        self.app.post("/update")(self.update)
        self.app.post("/stop_visualization")(self.stop_visualization)
        self.app.post("/stop")(self.stop_instance)
        self.app.post("/add_dataset")(self.add_dataset)
        self.app.post("/remove_dataset")(self.remove_dataset)
        self.app.get("/list_datasets")(self.list_datasets)
        self.app.get("/{dataset_id}/list_variables")(self.list_variables)
        self.app.post("/{dataset_id}/update_variables")(self.update_variables)
        self.app.post("/save_state")(self.save_state)
        self.app.post("/load_state")(self.load_state)
        self.app.get("/health")(self.health_live)

    # Route method definitions
    async def info(self) -> Info:
        '''Get the information of the visualizer instance'''
        if self.visualizer is not None:
            info_dict = self.visualizer.info()
        else:
            info_dict = {
                "app_name": self.settings.app_name,
                "host": self.settings.default_host,
                "port": self.settings.default_port,
                "standalone": self.settings.default_standalone,
                "datasets": []
            }
        return Info(**info_dict)

    @handle_exceptions
    async def connect_or_initialize_server(self, init_props: InitProps = Body(
        examples=[{
            "host": "localhost",
            "port": 0,
            "standalone": False,
            "dark_mode": False
        }]
    )):
        """
        If an existing visualizer instance exists on the provided host and port, connect
        to that instance, making it the active instance.
        If no such instance exists, initialize a new visualizer instance on the provided
        host and port.
        """
        host = init_props.host
        port = init_props.port
        if port == 0:
            # Visor owns port selection: probe on the exact interface the
            # visualizer will actually bind to (binding_host if configured,
            # otherwise the client-supplied host).
            probe_host = self.settings.binding_host or host
            port = find_unused_port(host=probe_host)
            if port is None:
                msg = "Error: Could not find an unused port to initialize the server."
                logger.error(msg)
                raise HTTPException(status_code=503, detail=msg)
        standalone = init_props.standalone if init_props.standalone is not None\
            else settings.default_standalone
        dark_mode = init_props.dark_mode if init_props.dark_mode is not None\
            else settings.default_dark_mode
        rendering_mode = init_props.rendering_mode if init_props.rendering_mode is not None\
            else RenderingMode.LOCAL
        # initialize an instance of Visor
        self.visualizer, warnings = self._connect_or_initialize_visualizer(
            host,
            port,
            standalone,
            dark_mode,
            rendering_mode
        )
        url = self._get_url(host, port)
        response = {"message": f"Set active instance to {url}"}
        if warnings:
            response["warnings"] = warnings
        return response

    async def list_instances(self):
        """List the URLs of all Visor instances in the cache."""
        return {"urls": VisorCache.list_instances()}

    @handle_exceptions
    async def start_instance(self, start_props: StartProps = Body(
        examples=[{
            "file_path": "path/to/file.vtk",
            "metadata": {"name": "model", "unit": "m"},
            "timeout": 0
        }]
    )):
        """Start the active visualizer instance with the given input file and metadata."""
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)

        # Start visualizer instance
        dataset_id, task = await self.visualizer._start_async(
            input=start_props.file_path,
            metadata=start_props.metadata,
            timeout=start_props.timeout
        )
        return {"success": f"Server started on {self.visualizer.url}",
                "dataset_id": dataset_id}

    @handle_exceptions
    async def update(self, update_props: UpdateProps = Body(
        examples=[{
            "file_path": "path/to/updated_file.vtk",
            "metadata": {"name": "updated_model", "unit": "m"}
        }]
    )):
        """
        Update the input file and metadata of the active visualizer instance,
        clearing any previous datasets.
        """
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)

        # Update the input file of visualizer instance
        dataset_id = self.visualizer.update(update_props.file_path, update_props.metadata)
        return {"success": f"Server input updated on {self.visualizer.url}",
                "dataset_id": dataset_id}

    async def _stop_visualization(self):
        """Stop active visualizer instance and return the URL"""
        if self.visualizer is None:
            logger.error("Server not initialized")
            raise HTTPException(status_code=503, detail="Server not initialized")
        url = self.visualizer.url
        await self.visualizer._stop_async()
        return url

    @handle_exceptions
    async def stop_visualization(self):
        """Stop active visualizer instance but keep the Visor instance in cache"""
        url = await self._stop_visualization()
        return {"success": f"Stopped visualization for server running on {url}"}

    @handle_exceptions
    async def stop_instance(self):
        """Stop visualizer server and delete Visor instance from cache"""
        url = await self._stop_visualization()
        VisorCache.delete_instance(url)
        self.visualizer = None
        return {"success": f"Stopped visualization for server running on {url} and deleted instance"}

    @handle_exceptions
    async def add_dataset(self, update_props: UpdateProps = Body(
        examples=[{
            "file_path": "path/to/updated_file.vtk",
            "metadata": {"name": "updated_model", "unit": "m"}
        }]
    )):
        """Add a dataset to the active visualizer instance without clearing previous datasets."""
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)

        # Add dataset to the visualizer instance
        dataset_id = self.visualizer.add_dataset(update_props.file_path, update_props.metadata)
        return {"success": f"Added dataset to visualizer running on {self.visualizer.url}",
                "dataset_id": dataset_id}

    @handle_exceptions
    async def remove_dataset(self, remove_dataset_props: RemoveDatasetProps = Body(
        examples=[{
            "dataset_id": 123456
        }]
    )):
        """Remove a dataset from the active visualizer instance by its ID."""
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)

        # Remove dataset from the active visualizer instance
        self.visualizer.remove_dataset(remove_dataset_props.dataset_id)
        return {"success": f"Removed dataset with ID {remove_dataset_props.dataset_id}"
                           f"to visualizer running on {self.visualizer.url}"
                }

    @handle_exceptions
    async def list_datasets(self):
        """List all datasets in the active visualizer instance."""
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)

        # List datasets loaded in the visualizer instance
        return {"datasets": self.visualizer.list_datasets()}

    @handle_exceptions
    async def list_variables(self, dataset_id: int):
        """List variables for a dataset, grouped by part."""
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)

        # List variables for a dataset, grouped by part.
        variables = self.visualizer.list_variables(dataset_id)
        return {"parts": [part.to_dict() for part in variables]}

    @handle_exceptions
    async def update_variables(self, dataset_id: int, variables: UpdateVariableProps):
        """Update variables for a dataset, grouped by part."""
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)

        # List datasets loaded in the visualizer instance
        update_variables = [var.model_dump() for var in variables.variables]
        return {"variables": self.visualizer.update_variables(dataset_id, update_variables)}

    @handle_exceptions
    async def save_state(self, save_props: SaveStateProps = Body(
        examples=[{
            "state_dir": "path/to/state_dir"
        }]
    )):
        """Save the current state of the visualizer instance to a directory."""
        state_dir = save_props.state_dir
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)
        # Save the current state of the visualizer instance to a file
        await self.visualizer.save_state(state_dir)
        return {"success": f"Saved state to {state_dir} for visualizer running on {self.visualizer.url}"}

    @handle_exceptions
    async def load_state(self, save_props: LoadStateProps = Body(
        examples=[{
            "state_dir": "path/to/state_dir"
        }]
    )):
        """Load the current state of the visualizer instance from a directory."""
        state_dir = save_props.state_dir
        if self.visualizer is None:
            msg = "No active Visor instance. Please initialize and start the server first."
            logger.error(msg)
            raise HTTPException(status_code=503, detail=msg)
        # Load the state of the visualizer instance from a file
        self.visualizer.load_state(state_dir)
        return {"success": f"Loaded state from {state_dir} for visualizer running on {self.visualizer.url}"}

    async def health_live(self):
        """Get the health status of the FastAPI server"""
        return {"status": "ok"}

    # Protected methods
    def _get_url(self, host: str, port: int) -> str:
        """Get the URL for a host and port"""
        # Report the public hostname provided by the initializer (host).
        # The server may listen on a separate binding host (settings.binding_host),
        # but the URLs advertised to clients MUST use the public host.
        # Prefer the Settings-provided `url_scheme` when available; fall back
        # to a safe runtime check for environments where `settings` may be
        # monkeypatched (e.g. unit tests using MagicMock).
        scheme = self.settings.url_scheme
        return f"{scheme}://{host}:{port}"

    def _connect_or_initialize_visualizer(
            self,
            host: str,
            port: int,
            standalone: bool,
            dark_mode: bool,
            rendering_mode: RenderingMode = RenderingMode.LOCAL,
    ) -> Tuple[Visor, str]:
        """Connect to a visualizer instance with the given host and port if one
        exists; otherwise, create a new visualizer instance on that host and port."""
        url = self._get_url(host, port)
        msg = (
            f'Connecting to Visor server on {url} (standalone={standalone}, dark_mode={dark_mode})'
        )
        logger.info(msg)
        # Initialize the server with the given port, host and client distribution path
        instance, warnings = VisorCache.get_instance(url, rendering_mode, standalone, dark_mode, self.trame_log_dir)
        return instance, warnings


app = VisorAPI().app
