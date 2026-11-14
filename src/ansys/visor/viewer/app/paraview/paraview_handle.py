"""
PARAVIEW handle
===============
The Visor that ``Visor(rendering_mode="PARAVIEW", ...)`` returns.  The session
runs in its own pvpython process; this object launches it, forwards each
Visor method over the session channel, and ends it.

The session process is ended by :meth:`VisorParaviewHandle.close`, or at
interpreter exit if close was never called.
"""

from __future__ import annotations

import asyncio
import threading
import weakref
from typing import Any

from ansys.visor.viewer.app.paraview.session_channel import SessionLaunchRequest
from ansys.visor.viewer.app.paraview.session_process import ParaviewSessionProcess
from ansys.visor.viewer.app.visor import Visor
from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.errors import ParaviewSessionError, UnsupportedInModeError
from ansys.visor.viewer.core.metadata import Metadata
from ansys.visor.viewer.core.pvserver_address import PvserverAddress
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables

logger = VisorDefaultLogger(__name__)

BLOCKING_WAIT_SLICE_S = 0.5
"""Seconds between checks that the session process is running while a blocking start waits."""


class VisorParaviewHandle(Visor):
    """Visor for PARAVIEW mode: the session runs in its own pvpython process, reached over its channel."""

    def __init__(
            self,
            url: str | None = None,
            rendering_mode: RenderingMode = RenderingMode.PARAVIEW,
            standalone: bool = True,
            dark_mode: bool | None = None,
            trame_log_dir: str | None = None,
            pvserver: PvserverAddress | None = None,
    ) -> None:
        """Launch the session for url against pvserver, the settings default when None.

        Raises ValueError for a rendering mode other than PARAVIEW, and
        whatever the session process raises when it cannot start.
        """
        rendering_mode = RenderingMode.from_string(rendering_mode)
        if rendering_mode is not RenderingMode.PARAVIEW:
            raise ValueError(f"VisorParaviewHandle runs PARAVIEW sessions only, not {rendering_mode.name}")
        super().__init__(url, standalone, dark_mode)
        self._pvserver = pvserver if pvserver is not None else settings.default_pvserver_address()
        self._wait_released = threading.Event()
        process = self._create_session_process()
        self._channel = process.launch(
            SessionLaunchRequest(
                url=self.url,
                standalone=standalone,
                dark_mode=self.dark_mode,
                trame_log_dir=trame_log_dir,
                pvserver=self._pvserver,
            )
        )
        self._process = process
        self._finalizer = weakref.finalize(self, process.end)
        logger.info("PARAVIEW session ready on %s (pvserver %s, pid %s)", self.url, self._pvserver, process.pid)

    def _create_session_process(self) -> ParaviewSessionProcess:
        """The session process for this handle's port, configured from settings."""
        return ParaviewSessionProcess.from_settings(settings, self.port)

    """ Properties """
    @property
    def pvserver(self) -> PvserverAddress:
        """The pvserver this session renders on."""
        return self._pvserver

    @property
    def running(self) -> bool:
        """Whether the session process is running."""
        return self._process.alive

    """ Public Methods """
    def start(self,
              input: str | VisorDatasetType | None = None,
              metadata: Metadata | str | None = None,
              timeout: int = 0,
              blocking: bool = False,
              ) -> int | None:
        """Start the session's server; with blocking, wait until the session ends.

        The wait ends when :meth:`stop` or :meth:`close` is called.  A session
        process that exits by itself during the wait raises
        ParaviewSessionError.  KeyboardInterrupt during the wait ends the
        session through :meth:`close` and is raised again.
        """
        self._reject_in_memory_input(input)
        self._wait_released.clear()
        dataset_id = self._channel.call("start", input, metadata, timeout)
        if blocking:
            self._wait_until_released()
        return dataset_id

    def stop(self) -> None:
        """Stop the session's server; a blocking start waiting on this handle returns."""
        self._channel.call("stop")
        self._wait_released.set()

    def update(self,
               input: str | VisorDatasetType,
               metadata: Metadata | str | None = None,
               ) -> int:
        """Replace the session's datasets with the file at input."""
        self._reject_in_memory_input(input)
        return self._channel.call("update", input, metadata)

    def add_dataset(self,
                    input: str | VisorDatasetType,
                    metadata: Metadata | str | None = None,
                    ) -> int:
        """Add the file at input to the session's scene and return its dataset ID."""
        self._reject_in_memory_input(input)
        return self._channel.call("add_dataset", input, metadata)

    def remove_dataset(self, dataset_id: int) -> None:
        """Remove a dataset from the session's scene."""
        return self._channel.call("remove_dataset", dataset_id)

    def list_datasets(self) -> dict:
        """List the datasets in the session's scene."""
        return self._channel.call("list_datasets")

    def list_variables(self, dataset_id: int) -> list[VisorPartVariables]:
        """List the variables of a dataset in the session's scene, grouped by part."""
        return self._channel.call("list_variables", dataset_id)

    def update_variables(self, dataset_id: int, variables: list[dict[str, Any]]) -> None:
        """Raise UnsupportedInModeError: pvserver holds its own copy of the arrays."""
        raise UnsupportedInModeError("update_variables is not supported in PARAVIEW mode")

    async def save_state(self, state_dir: str) -> None:
        """Save the session's state to state_dir; the call waits on a worker thread, not the event loop."""
        await asyncio.to_thread(self._channel.call, "save_state", state_dir)

    def load_state(self, state_dir: str) -> None:
        """Load the session's state from state_dir."""
        return self._channel.call("load_state", state_dir)

    def close(self) -> None:
        """End the session process; idempotent.  A blocking start waiting on this handle returns."""
        self._wait_released.set()
        self._finalizer()

    def _health(self) -> bool:
        """The session server's health; False when the session process is gone."""
        if not self._process.alive:
            return False
        return self._channel.call("_health")

    """ Protected Async Methods (for use in the FastAPI endpoints) """
    async def _start_async(self,
                           input: str | VisorDatasetType | None = None,
                           metadata: Metadata | str | None = None,
                           timeout: int = 0,
                           ) -> tuple[int | None, None]:
        """Start the session's server on a worker thread; there is no server task in this process."""
        dataset_id = await asyncio.to_thread(self.start, input, metadata, timeout)
        return dataset_id, None

    async def _stop_async(self) -> None:
        """Stop the session's server on a worker thread."""
        await asyncio.to_thread(self.stop)

    """ Private Methods """
    @staticmethod
    def _reject_in_memory_input(input: str | VisorDatasetType | None) -> None:
        """Raise UnsupportedInModeError for input other than a file path or None: pvserver opens files only."""
        if input is not None and not isinstance(input, str):
            raise UnsupportedInModeError("in-memory dataset input is not supported in PARAVIEW mode")

    def _wait_until_released(self) -> None:
        """Wait until stop or close releases the wait.

        close releases the wait before it ends the session process, so a
        process found gone with the wait released was ended by close, not by
        itself.
        """
        try:
            while not self._wait_released.wait(BLOCKING_WAIT_SLICE_S):
                if self._process.alive:
                    continue
                if self._wait_released.is_set():
                    return
                code = self._process.exit_code
                self.close()
                raise ParaviewSessionError(
                    f"The PARAVIEW session process exited with code {code} while start was blocking; "
                    f"see its log at {self._process.log_path}"
                )
        except KeyboardInterrupt:
            logger.info("Interrupted; ending the PARAVIEW session on %s", self.url)
            self.close()
            raise
