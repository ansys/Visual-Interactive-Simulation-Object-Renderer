"""
Session channel
===============
The messages and both ends of the connection between the API process and the
pvpython session process.

Every class that crosses the connection is defined here, never in the child's
entry script: that script runs as ``__main__``, and a class pickled from there
would be named ``__main__.X`` and fail to load on the other side.

Payloads are pickled by the connection.  Numpy values in arguments and results
are turned into plain Python values first (:func:`to_plain`), so neither end
unpickles a numpy object written by the other end's numpy version.
"""

from __future__ import annotations

import dataclasses
import inspect
import threading
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Callable, Coroutine

import numpy as np
from pydantic import BaseModel

from ansys.visor.viewer.app.visor import Visor
from ansys.visor.viewer.core import errors
from ansys.visor.viewer.core.pvserver_address import PvserverAddress
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)

def served_methods(visor_class: type) -> frozenset[str]:
    """The public methods declared on visor_class, plus ``_health``."""
    declared = {
        name for name, member in vars(visor_class).items()
        if inspect.isfunction(member) and not name.startswith("_")
    }
    return frozenset(declared | {"_health"})


SERVED_METHODS: frozenset[str] = served_methods(Visor)
"""The methods the session process serves on its Visor: Visor's public interface and ``_health``."""

_VALUE_STYLE_ERRORS: tuple[type[Exception], ...] = (
    errors.InvalidFileError,
    errors.InvalidFileFormatError,
    errors.InvalidUrlError,
    errors.InvalidPathError,
    errors.ServerNotStartedError,
    errors.InvalidServerTimeoutError,
)
"""Errors whose ``str`` wraps the constructor value in a prefix, so the value is sent instead."""

_KNOWN_ERRORS: dict[str, type[Exception]] = {
    cls.__name__: cls
    for cls in (
        *_VALUE_STYLE_ERRORS,
        errors.VisorAddDatasetError,
        errors.PvserverConnectionError,
        errors.UnsupportedInModeError,
        TypeError,
        ValueError,
        FileNotFoundError,
        RuntimeError,
    )
}


def to_plain(value: Any) -> Any:
    """Return value with numpy scalars and arrays replaced by Python values, inside lists, tuples, dicts and dataclasses.

    A dataclass keeps its type: it is rebuilt with ``dataclasses.replace``.
    Any other object, including a pydantic model, is returned unchanged.
    """
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {to_plain(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, tuple):
        return tuple(to_plain(item) for item in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        changes = {f.name: to_plain(getattr(value, f.name)) for f in dataclasses.fields(value) if f.init}
        return dataclasses.replace(value, **changes)
    return value


class SessionLaunchRequest(BaseModel):
    """Everything the session process needs to build its VisorVTKParaview."""

    url: str
    standalone: bool
    dark_mode: bool | None
    trame_log_dir: str | None
    pvserver: PvserverAddress


class SessionReady(BaseModel):
    """Sent once by the session process when its Visor is built."""


class SessionError(BaseModel):
    """An error crossing the process boundary as its class name and message."""

    type_name: str
    message: str

    @classmethod
    def from_exception(cls, exc: BaseException) -> SessionError:
        """Describe exc; a value-style Visor error sends its constructor value so it is not wrapped twice."""
        if isinstance(exc, _VALUE_STYLE_ERRORS) and exc.args:
            message = str(exc.args[0])
        else:
            message = str(exc)
        return cls(type_name=type(exc).__name__, message=message)

    def to_exception(self) -> Exception:
        """Rebuild a known Visor or builtin error type; anything else becomes RuntimeError with the type named."""
        error_cls = _KNOWN_ERRORS.get(self.type_name)
        if error_cls is None:
            return RuntimeError(f"{self.type_name}: {self.message}")
        return error_cls(self.message)


@dataclass(frozen=True)
class SessionRequest:
    """One method call on the session's Visor."""

    method: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SessionResult:
    """The value a served method returned."""

    value: Any = None


@dataclass(frozen=True)
class SessionShutdown:
    """Ends the serve loop; the session process then exits."""


class SessionChannel:
    """Parent end of the session connection: one request, one reply, serialized by a lock."""

    def __init__(self, connection: Connection, log_path: Path) -> None:
        """Wrap an authenticated connection; log_path is named when the connection is lost."""
        self._connection = connection
        self._log_path = log_path
        self._lock = threading.Lock()

    def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Send one request and return its result, or raise the error the child reported.

        There is no per-call timeout.  A session process that exits or crashes
        closes the connection, and the wait ends in ParaviewSessionError.
        """
        request = SessionRequest(method=method, args=to_plain(args), kwargs=to_plain(kwargs))
        with self._lock:
            try:
                self._connection.send(request)
                reply = self._connection.recv()
            except (EOFError, OSError) as exc:
                raise errors.ParaviewSessionError(
                    f"The PARAVIEW session process was lost during {method!r}; see its log at {self._log_path}"
                ) from exc
        if isinstance(reply, SessionError):
            raise reply.to_exception()
        return reply.value

    def shutdown(self) -> bool:
        """Ask the session process to exit; return False when a call holds the channel or the connection is gone."""
        if not self._lock.acquire(blocking=False):
            return False
        try:
            self._connection.send(SessionShutdown())
            return True
        except OSError:
            return False
        finally:
            self._lock.release()

    def close(self) -> None:
        """Close the connection."""
        self._connection.close()


class SessionServer:
    """Child end: receive requests, dispatch them to a target object, reply."""

    def __init__(
        self,
        connection: Connection,
        target: object,
        allowed: frozenset[str],
        run_coroutine: Callable[[Coroutine], Any],
    ) -> None:
        """Serve only the method names in allowed; run_coroutine runs a coroutine result to completion."""
        self._connection = connection
        self._target = target
        self._allowed = allowed
        self._run_coroutine = run_coroutine

    def serve_forever(self) -> None:
        """Serve until shutdown or until the connection closes."""
        while True:
            try:
                message = self._connection.recv()
            except (EOFError, OSError):
                logger.info("Session channel closed")
                return
            if isinstance(message, SessionShutdown):
                logger.info("Session shutdown requested")
                return
            reply = self._dispatch(message)
            try:
                self._connection.send(reply)
            except OSError:
                logger.info("Session channel closed while replying")
                return
            except Exception as exc:
                logger.exception("Result of %r could not be sent", getattr(message, "method", message))
                try:
                    self._connection.send(SessionError.from_exception(exc))
                except OSError:
                    return

    def _dispatch(self, message: object) -> SessionResult | SessionError:
        """Run one request on the target and describe its outcome."""
        if not isinstance(message, SessionRequest):
            return SessionError(type_name="RuntimeError", message=f"Unexpected session message {type(message).__name__}")
        if message.method not in self._allowed:
            return SessionError(
                type_name="RuntimeError",
                message=f"Method {message.method!r} is not served by the PARAVIEW session",
            )
        try:
            result = getattr(self._target, message.method)(*message.args, **message.kwargs)
            if inspect.iscoroutine(result):
                result = self._run_coroutine(result)
            return SessionResult(value=to_plain(result))
        except Exception as exc:
            logger.exception("Session method %r failed", message.method)
            return SessionError.from_exception(exc)
