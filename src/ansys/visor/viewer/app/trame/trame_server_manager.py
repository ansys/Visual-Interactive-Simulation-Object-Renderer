"""Class to manage the Trame server lifecycle."""

import asyncio
from asyncio import Task
from typing import Awaitable

from trame.app import get_server
from trame.app.core import Server

import ansys.visor.viewer.core.errors as errors
from ansys.visor.viewer.app.trame.async_runner import AsyncRunner
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger, get_trame_log_path

"""Logging configuration"""
logger = VisorDefaultLogger(__name__)
from ansys.visor.viewer.config import settings


class TrameServerManager:
    """
    `TrameServerManager` provides a synchronous and asynchronous interface
    for starting and stopping a Trame server. It uses `AsyncRunner` to
    run the server on a dedicated background thread, allowing the main
    thread to remain responsive.
    Attributes:
        server (Server): The Trame server instance to control.
        _host (str): The host address for the server (default is "localhost").
        _port (int): The port number for the server (default is 8080).
        __async_runner (AsyncRunner): An instance of AsyncRunner to manage
            asynchronous execution.
    Methods:
        start(timeout: int = 0, blocking: bool = False) -> None:
            Starts the server synchronously.
        stop() -> None:
            Stops the server synchronously.
        start_async(timeout: int = 0, blocking: bool = False) -> Awaitable
            Starts the server asynchronously.
        stop_async() -> None:
            Stops the server asynchronously.
    Protected Methods:
        _start_core(timeout: int = 0, blocking: bool = False) -> Task
            Core coroutine to start the server.
        _stop_core() -> None
            Core coroutine to stop the server.

    """
    def __init__(
            self,
            host: str = "localhost",
            port: int = 8080,
            trame_log_dir: str | None = None
    ):
        """Initialize the Trame server manager."""
        self._host = host
        self._port = port
        self._server = self._initialize_server(trame_log_dir)
        self._async_runner = AsyncRunner()

    @property
    def running(self) -> bool:
        """Return whether the server is running."""
        return self._server is not None and self._server.running

    @property
    def server(self) -> Server:
        """Return the Trame server instance."""
        return self._server

    @property
    def state(self):
        """
        VisorState is not yet defined.
        """
        raise NotImplementedError

    @property
    def url(self) -> str:
        """Return the URL of the server."""
        scheme = settings.url_scheme
        return f"{scheme}://{self._host}:{self._port}"

    @property
    def health(self) -> bool:
        """Return whether the server is running."""
        if self._server is None:
            logger.error("Server not initialized")
            raise RuntimeError("Server not initialized")
        if self._server.controller is None:
            logger.error("Server controller not initialized")
            raise RuntimeError("Server controller not initialized")
        return self._server.running

    def start(self, timeout: int = 0, blocking: bool = False) -> None:
        """
        Start the server synchronously.

        At a minimum, this method will block until the server has started.
        If blocking is True, this method will continue blocking after the server has started,
        and only return when the server has stopped.
        Args:
            timeout (int): The timeout in seconds for starting the server.
                A value of 0 means no timeout. Default is 0.
            blocking (bool): If True, the call will block until the server
                stops. Default is False.
        Raises:
            InvalidServerTimeoutError: If the provided timeout is negative.
            RuntimeError: If the server fails to start for any reason.
        """
        coroutine = self._start_core(timeout, blocking)
        self._async_runner.run_coroutine_block(coroutine, True)

    def stop(self):
        """
        Stop the server synchronously.
        Raises:
            RuntimeError: If the server fails to stop for any reason.
        """
        coroutine = self._stop_core()
        self._async_runner.run_coroutine_block(coroutine, False)

    async def start_async(self, timeout: int = 0, blocking: bool = False) -> Awaitable:
        """
        Start the server asynchronously.

        If this method is awaited, it will do one of two things depending on whether
        blocking is True or False:
        1. If blocking is False, awaiting this method will only block until the
           underlying Trame server is started, and then promptly return an Awaitable object
           representing the Trame server. You may then await this object later on in your code
           to block until the server is stopped.
        2. If blocking is True, awaiting this method will block until the underlying Trame
           server is started, and then continue blocking until the server is stopped.

        Args:
            timeout (int): The timeout in seconds for starting the server.
                A value of 0 means no timeout. Default is 0.
            blocking (bool): If True, the coroutine will not complete until
                the server stops. Default is False.
        Returns:
            Awaitable: An awaitable that completes when the server has started.
        Raises:
            InvalidServerTimeoutError: If the provided timeout is negative.
            RuntimeError: If the server fails to start for any reason.
        """
        coroutine = self._start_core(timeout, blocking)
        return await self._async_runner.run_coroutine_async(coroutine, True)

    async def stop_async(self) -> None:
        """
        Stop the server asynchronously.
        Raises:
            RuntimeError: If the server fails to stop for any reason.
        """
        coroutine = self._stop_core()
        await self._async_runner.run_coroutine_async(coroutine, False)

    async def _start_core(self,
                           timeout: int = 0,
                           blocking: bool = False
                           ) -> Task:
        """
        Core coroutine to start the server.
        Args:
            timeout (int): The timeout in seconds for starting the server.
                A value of 0 means no timeout. Default is 0.
            blocking (bool): If True, the coroutine will not complete until
                the server stops. Default is False.
        Returns:
            Task: The asyncio Task representing the server.
        Raises:
            InvalidServerTimeoutError: If the provided timeout is negative.
            RuntimeError: If the server fails to start for any reason.
        """
        print("Server starting...")

        logger.debug("Starting server on main thread")

        """Start the server on the main thread"""
        if timeout and timeout < 0:
            raise errors.InvalidServerTimeoutError(timeout)

        server_coroutine = self._server.start(
            # Specify the background thread here, or else you will
            # get the error "set_wakeup_fd only works in main thread
            # of the main interpreter".
            thread=self._async_runner.thread,
            host=self._host,
            port=self._port,
            # Start as coroutine in case we need to
            # see Trame server console logging (the
            # server console logging only works if
            # exec_mode is "coroutine").
            exec_mode="coroutine",
            open_browser=False,
            show_connection_info=False,
            timeout=timeout,
        )

        if server_coroutine is None:
            # If you try start a Trame server with the same host and
            # port as an existing Trame server running on the same thread,
            # server.start() will return None instead of throwing a port
            # conflict error. Port conflict errors are only thrown if the
            # existing Trame server is running on a different thread.
            msg = "Could not create server coroutine. Are you using the"
            msg += " same host and port as an existing server instance?"
            logger.error(msg)
            raise RuntimeError(msg)

        # Start the server by turning the server coroutine into a task.
        server_task = asyncio.create_task(server_coroutine)

        done, pending = await asyncio.wait(
            [self._server.ready, server_task],
            timeout=10,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if self._server.ready in done:
            e = self._server.ready.exception()
            if e is not None:
                raise e
            if not self._server.ready:
                # If we make it here, server.ready was set, but it is false for
                # some reason (server.start() failed but didn't throw an exception).
                msg = "Server could not start (unknown cause)"
                logger.error(msg)
                raise RuntimeError(msg)
        elif server_task in done:
            e = server_task.exception()
            if e is not None:
                raise e
            if not self._server.ready:
                # If we make it here, the server task finished without exceptions
                # before server.ready got set. This should never happen.
                msg = "Server could not start (unknown cause)"
                logger.error(msg)
                raise RuntimeError(msg)
        else:
            # If we make it here, server.ready never got set, and no
            # server exception was thrown (we timed out for an unknown reason).
            msg = "Timed out while starting server."
            logger.error(msg)
            raise RuntimeError(msg)

        if blocking:
            await server_task

        # Success! We can now return the actual server task in all its glory.
        return server_task

    # Protected Methods
    async def _stop_core(self):
        """
        Core coroutine to stop the server.
        Raises:
            RuntimeError: If the server fails to stop for any reason.
        """
        logger.debug("Stopping server on main thread")
        if self._server.running:
            await self._server.stop()
        # TODO: Trame's 'on_server_exited' handler never runs (might
        #       be bug), so log 'Server stopped' here. Remove this
        #       when the handler is fixed. BHB 2025-09-10
        print("Server stopped")

    def _initialize_server(self, trame_log_dir: str | None = None) -> Server:
        """Initialize the server instance based on the input server or url"""

        logger.debug(
            f"Initializing server with url {self.url}, hostname "
            f"{self._host} and port {self._port}"
        )
        server = get_server(name=self.url, log_network=get_trame_log_path(trame_log_dir))

        # Platform-native TLS support (optional): if the platform provides
        # a pre-resolved SSL certificate path (from Settings), configure
        # wslink/trame to use it so the websocket endpoint speaks WSS.
        try:
            ssl_val = getattr(settings, "ssl_certificate", None)
            if isinstance(ssl_val, str) and ssl_val.strip():
                # Only attempt to set defaults if the server exposes a CLI
                if hasattr(server, "cli") and hasattr(server.cli, "set_defaults"):
                    try:
                        server.cli.set_defaults(ssl=ssl_val)
                        logger.debug(f"Configured Trame/wslink SSL using {ssl_val}")
                    except Exception:
                        logger.exception("Failed to set trame CLI ssl defaults")
        except Exception:
            # Don't fail server initialization if TLS auto-config fails
            logger.exception("Error while attempting to configure Trame SSL from settings")

        return server