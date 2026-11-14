"""
Session process
===============
Spawns and ends the pvpython process that runs one PARAVIEW session, and
returns the channel to it once the session reports ready.

The parent listens on a loopback port and the child connects.  The 32-byte
authkey reaches the child as one hex line on its stdin, never in argv or the
environment.  The child's stdout and stderr go to a log file, so no pipe can
fill and block it.  The child is not detached: it exits when its connection
closes, so it does not outlive this process.
"""

from __future__ import annotations

import importlib.util
import secrets
import socket
import subprocess
import time
from multiprocessing import AuthenticationError
from multiprocessing.connection import Connection, answer_challenge, deliver_challenge
from pathlib import Path

from ansys.visor.viewer.app.paraview.session_channel import (
    SessionChannel,
    SessionError,
    SessionLaunchRequest,
    SessionReady,
)
from ansys.visor.viewer.config import Settings
from ansys.visor.viewer.core.errors import ParaviewNotConfiguredError, ParaviewSessionError
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)

SESSION_MAIN_MODULE = "ansys.visor.viewer.app.paraview.session_main"
"""The child entry module; its file path is passed to pvpython."""

CHANNEL_HOST = "127.0.0.1"
"""The loopback address the parent listens on."""

WAIT_SLICE_S = 0.5
"""Seconds between checks that the child is still running while waiting for it."""

END_GRACE_S = 5.0
"""Seconds end() waits after each step before escalating."""


class ParaviewSessionProcess:
    """Spawns and ends one pvpython session process and owns its channel."""

    def __init__(self, pvpython: Path, venv: Path, log_path: Path, start_timeout: float) -> None:
        """Hold the launch settings; spawns nothing."""
        self._pvpython = Path(pvpython)
        self._venv = Path(venv)
        self._log_path = Path(log_path)
        self._start_timeout = start_timeout
        self._process: subprocess.Popen | None = None
        self._connection: Connection | None = None
        self._channel: SessionChannel | None = None
        self._ended = False

    @classmethod
    def from_settings(cls, settings: Settings, url_port: int) -> ParaviewSessionProcess:
        """Build from settings; raise ParaviewNotConfiguredError naming the missing .visor key."""
        for key in ("paraview_pvpython", "paraview_venv"):
            if not getattr(settings, key):
                raise ParaviewNotConfiguredError(f"PARAVIEW mode needs '{key}' set in the .visor file")
        return cls(
            pvpython=Path(settings.paraview_pvpython),
            venv=Path(settings.paraview_venv),
            log_path=Path(settings.default_log_dir) / f"visor_paraview_session_{url_port}.log",
            start_timeout=settings.paraview_session_start_timeout,
        )

    @property
    def alive(self) -> bool:
        """Whether the child process is still running."""
        return self._process is not None and self._process.poll() is None

    @property
    def log_path(self) -> Path:
        """The file receiving the child's stdout and stderr."""
        return self._log_path

    def launch(self, request: SessionLaunchRequest) -> SessionChannel:
        """Spawn the child, hand it the authkey on stdin, and return the channel once it reports ready.

        An error the child reports is raised as its own type after the child
        is ended.  A child that exits, never connects or never reports ready
        within the start timeout is ended, and ParaviewSessionError names the log.
        """
        if self._process is not None:
            raise RuntimeError("This session process has already been launched")
        authkey = secrets.token_bytes(32)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind((CHANNEL_HOST, 0))
            listener.listen(1)
            listener.settimeout(WAIT_SLICE_S)
            self._spawn(listener.getsockname()[1], authkey)
            deadline = time.monotonic() + self._start_timeout
            reply = self._await_ready(listener, authkey, request, deadline)
        except ParaviewSessionError:
            self.end()
            raise
        except (EOFError, OSError, AuthenticationError) as exc:
            self.end()
            raise ParaviewSessionError(
                f"The PARAVIEW session process was lost before it reported ready; see its log at {self._log_path}"
            ) from exc
        finally:
            listener.close()
        if isinstance(reply, SessionError):
            logger.error("PARAVIEW session failed to start: %s: %s", reply.type_name, reply.message)
            self.end()
            raise reply.to_exception()
        self._channel = SessionChannel(self._connection, self._log_path)
        logger.info("PARAVIEW session ready; log at %s", self._log_path)
        return self._channel

    def end(self) -> None:
        """Send shutdown and wait, then terminate and wait, then kill; idempotent.

        A child that reported an error gets the same wait to exit by itself.
        With no connection to the child, it is terminated at once.
        """
        if self._process is None or self._ended:
            return
        self._ended = True
        process = self._process
        if self._channel is not None:
            self._channel.shutdown()
        if self._connection is not None and process.poll() is None:
            if self._wait(process):
                self._close_connection()
                return
        if process.poll() is None:
            logger.warning("Terminating PARAVIEW session process %s", process.pid)
            process.terminate()
            if not self._wait(process):
                logger.warning("Killing PARAVIEW session process %s", process.pid)
                process.kill()
                process.wait()
        self._close_connection()

    def _spawn(self, port: int, authkey: bytes) -> None:
        """Start pvpython with stdout and stderr appended to the log, then write the authkey line and close stdin."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        command = self._command(port)
        logger.info("Launching PARAVIEW session: %s", command)
        with open(self._log_path, "ab") as log:
            try:
                self._process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            except OSError as exc:
                raise ParaviewSessionError(f"Could not start pvpython at {self._pvpython}: {exc}") from exc
        try:
            self._process.stdin.write(authkey.hex().encode("ascii") + b"\n")
            self._process.stdin.flush()
        finally:
            self._process.stdin.close()

    def _command(self, port: int) -> list[str]:
        """The pvpython command line; --venv takes a forward-slash path."""
        script = importlib.util.find_spec(SESSION_MAIN_MODULE).origin
        return [
            str(self._pvpython),
            "--venv",
            self._venv.as_posix(),
            script,
            "--channel-host",
            CHANNEL_HOST,
            "--channel-port",
            str(port),
        ]

    def _await_ready(
        self,
        listener: socket.socket,
        authkey: bytes,
        request: SessionLaunchRequest,
        deadline: float,
    ) -> SessionReady | SessionError:
        """Accept the child, authenticate both ways, send the request and return its reply."""
        sock = self._accept(listener, deadline)
        sock.setblocking(True)
        self._connection = Connection(sock.detach())
        deliver_challenge(self._connection, authkey)
        answer_challenge(self._connection, authkey)
        self._connection.send(request)
        while not self._connection.poll(WAIT_SLICE_S):
            self._check_waiting("report ready", deadline)
        return self._connection.recv()

    def _accept(self, listener: socket.socket, deadline: float) -> socket.socket:
        """Accept the child's connection, checking between waits that it is running and in time."""
        while True:
            try:
                sock, _address = listener.accept()
                return sock
            except TimeoutError:
                self._check_waiting("connect", deadline)

    def _check_waiting(self, step: str, deadline: float) -> None:
        """Raise ParaviewSessionError when the child has exited or the deadline has passed."""
        code = self._process.poll()
        if code is not None:
            raise ParaviewSessionError(
                f"The PARAVIEW session process exited with code {code} before it could {step}; "
                f"see its log at {self._log_path}"
            )
        if time.monotonic() >= deadline:
            raise ParaviewSessionError(
                f"The PARAVIEW session process did not {step} within {self._start_timeout} s; "
                f"see its log at {self._log_path}"
            )

    @staticmethod
    def _wait(process: subprocess.Popen) -> bool:
        """Wait up to END_GRACE_S for process to exit; return whether it did."""
        try:
            process.wait(END_GRACE_S)
            return True
        except subprocess.TimeoutExpired:
            return False

    def _close_connection(self) -> None:
        """Close the parent end of the connection, if any."""
        if self._connection is not None:
            self._connection.close()
