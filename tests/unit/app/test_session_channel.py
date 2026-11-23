"""Unit tests for the session channel: error transport, dispatch, coroutine results,
lost connections and numpy values in payloads.

Both ends run in this process over a loopback socket pair, the transport the
session uses.  Coroutine results run on a real ``AsyncRunner``.  Every
blocking call runs under a thread guard so a hang fails instead of stalling.
"""

import inspect
import socket
import struct
import sys
import threading
from multiprocessing.connection import Connection
from pathlib import Path

import numpy as np
import pytest

from ansys.visor.viewer.app.paraview.session_channel import (
    SERVED_METHODS,
    SessionChannel,
    SessionError,
    SessionServer,
    to_plain,
)
from ansys.visor.viewer.app.trame.async_runner import AsyncRunner
from ansys.visor.viewer.app.visor import Visor
from ansys.visor.viewer.core.errors import InvalidFileError, ParaviewSessionError
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables

LOG_PATH = Path("logs") / "visor_paraview_session_8081.log"


def run_bounded(fn, timeout=10.0):
    """Run fn in a thread; fail if it has not returned within timeout, else return or raise its outcome."""
    outcome = {}

    def target():
        try:
            outcome["value"] = fn()
        except BaseException as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), "the call did not return within the guard"
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


class Target:
    """Stands in for the session's Visor."""

    def __init__(self):
        self.calls = []
        self.coroutine_thread = None

    def list_datasets(self):
        return {1: "a"}

    def remove_dataset(self, dataset_id):
        self.calls.append(("remove_dataset", dataset_id, type(dataset_id)))

    def add_dataset(self, input, metadata=None):
        raise ValueError("bad input")

    def list_variables(self, dataset_id):
        return [VisorPartVariables(part_id=np.int64(dataset_id), part_name="p", variables=[])]

    def clear(self):
        self.calls.append(("clear",))

    async def save_state(self, state_dir):
        self.coroutine_thread = threading.current_thread()
        self.calls.append(("save_state", state_dir))


def connection_pair():
    """Two connected Connections over a socket pair."""
    left, right = socket.socketpair()
    return Connection(left.detach()), Connection(right.detach())


@pytest.fixture
def served():
    """Yield (channel, target, runner) with a SessionServer serving target in a thread."""
    parent, child = connection_pair()
    runner = AsyncRunner()
    target = Target()
    server = SessionServer(
        child, target, SERVED_METHODS, run_coroutine=lambda coroutine: runner.run_coroutine_block(coroutine, False)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    channel = SessionChannel(parent, LOG_PATH)
    yield channel, target, runner
    channel.shutdown()
    thread.join(5)
    channel.close()
    child.close()
    runner.dispose()


def test_value_style_error_crosses_with_its_message_once():
    """The constructor value is sent, so the rebuilt error's str has one prefix."""
    rebuilt = SessionError.from_exception(InvalidFileError("x")).to_exception()

    assert type(rebuilt) is InvalidFileError
    assert str(rebuilt) == "'Invalid file: x'"


def test_unknown_error_type_becomes_runtime_error_naming_it():
    rebuilt = SessionError.from_exception(KeyError("k")).to_exception()

    assert type(rebuilt) is RuntimeError
    assert str(rebuilt) == "KeyError: 'k'"


def test_int_keyed_dict_round_trips(served):
    channel, _target, _runner = served

    result = run_bounded(lambda: channel.call("list_datasets"))

    assert result == {1: "a"}
    assert [type(key) for key in result] == [int]


def test_target_value_error_reaches_caller_and_server_keeps_serving(served):
    channel, _target, _runner = served

    with pytest.raises(ValueError, match="^bad input$"):
        run_bounded(lambda: channel.call("add_dataset", "file.vtu"))

    assert run_bounded(lambda: channel.call("list_datasets")) == {1: "a"}


def test_method_outside_served_set_is_refused_without_calling_target(served):
    channel, target, _runner = served

    with pytest.raises(RuntimeError, match="^Method 'clear' is not served by the PARAVIEW session$"):
        run_bounded(lambda: channel.call("clear"))

    assert target.calls == []


def test_served_set_is_visors_public_interface_and_health():
    public = {name for name, _ in inspect.getmembers(Visor, inspect.isfunction) if not name.startswith("_")}

    assert SERVED_METHODS == public | {"_health"}


def test_coroutine_method_runs_on_the_runner_loop(served):
    channel, target, runner = served

    assert run_bounded(lambda: channel.call("save_state", "state_dir")) is None

    assert target.calls == [("save_state", "state_dir")]
    assert target.coroutine_thread is runner.thread


def test_serve_forever_returns_when_channel_closes():
    parent, child = connection_pair()
    server = SessionServer(child, Target(), SERVED_METHODS, run_coroutine=lambda coroutine: None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    parent.close()
    thread.join(5)

    assert not thread.is_alive()
    child.close()


@pytest.mark.parametrize("close", ["graceful", "reset"])
def test_call_on_lost_channel_raises_session_error_naming_log(close):
    """A peer that closes, or whose process dies (a reset), ends the wait with ParaviewSessionError."""
    left, right = socket.socketpair()
    channel = SessionChannel(Connection(left.detach()), LOG_PATH)
    if close == "reset":
        linger_on_zero_seconds = struct.pack("HH" if sys.platform == "win32" else "ii", 1, 0)
        right.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger_on_zero_seconds)
    right.close()

    with pytest.raises(ParaviewSessionError) as raised:
        run_bounded(lambda: channel.call("list_datasets"))

    assert str(raised.value) == (
        f"The PARAVIEW session process was lost during 'list_datasets'; see its log at {LOG_PATH}"
    )
    channel.close()


def test_to_plain_replaces_numpy_values_and_keeps_visor_types():
    payload = {
        np.int64(1): [np.float32(0.5), np.arange(2)],
        "flags": (np.bool_(True), "s"),
        "part": VisorPartVariables(part_id=np.int64(3), part_name="p", variables=[]),
    }

    plain = to_plain(payload)

    assert plain == {1: [0.5, [0, 1]], "flags": (True, "s"), "part": VisorPartVariables(3, "p", [])}
    assert [type(key) for key in plain] == [int, str, str]
    assert [type(item) for item in plain[1]] == [float, list]
    assert type(plain[1][1][0]) is int
    assert type(plain["flags"][0]) is bool
    assert type(plain["part"]) is VisorPartVariables
    assert type(plain["part"].part_id) is int


def test_numpy_arguments_and_results_cross_as_python_values(served):
    channel, target, _runner = served

    run_bounded(lambda: channel.call("remove_dataset", np.int64(4)))
    variables = run_bounded(lambda: channel.call("list_variables", 2))

    assert target.calls == [("remove_dataset", 4, int)]
    assert variables == [VisorPartVariables(part_id=2, part_name="p", variables=[])]
    assert type(variables[0].part_id) is int
