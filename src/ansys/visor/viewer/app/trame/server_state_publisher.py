"""
ServerStatePublisher
====================
Writes server-originated trame state keys from any thread onto the trame
event loop.

A state write flushes through wslink's publish path, which schedules its send
on the calling thread's event loop; from a caller thread that loop never runs,
so every write is handed to the :class:`AsyncRunner` that runs the trame server.
"""

from __future__ import annotations

from trame_server.state import State

from ansys.visor.viewer.app.trame.async_runner import AsyncRunner
from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.renderer.server_renderer import CameraPublisher

SERVER_CAMERA_STATE_KEY: str = "server_camera_state"
"""State key carrying the server's camera record, as its camelCase fields, or None."""


class ServerStatePublisher(CameraPublisher):
    """Writes server-originated state keys from any thread onto the trame event loop."""

    _async_runner: AsyncRunner
    _state: State

    def __init__(self, async_runner: AsyncRunner, state: State) -> None:
        """Both required: the runner whose loop runs the trame server, and that server's state."""
        self._async_runner = async_runner
        self._state = state

    def publish_camera(self, camera_state: VisorCameraState | None) -> None:
        """Dump the record by alias on the calling thread, or None, then write server_camera_state on the loop thread.

        The dump is taken here, not on the loop: the record is mutated in
        place by later camera writes, and the caller holds the scene lock.
        """
        camera_record = None if camera_state is None else camera_state.model_dump(by_alias=True)
        self._async_runner.call_soon(lambda: self._write(SERVER_CAMERA_STATE_KEY, camera_record))

    def _write(self, key: str, value: object) -> None:
        """Set one state key and flush it; loop thread only."""
        self._state[key] = value
        self._state.flush()

