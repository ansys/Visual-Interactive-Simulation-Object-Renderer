"""Unit tests for ``ParaviewSessionProcess``: the launch command line, the authkey
on stdin, the ready handshake, reported errors, start timeouts and ``end``.

Mocking boundary: ``subprocess.Popen``.  The fake process plays the session
process in a thread once the parent closes its stdin: it connects with a real
``multiprocessing.connection.Client`` using the authkey written to its stdin
and serves a real ``SessionServer``.  No pvpython is started.
"""

import asyncio
import subprocess
import threading
import time
from multiprocessing.connection import Client
from pathlib import Path

import pytest

from ansys.visor.viewer.app.paraview import session_process
from ansys.visor.viewer.app.paraview.session_channel import (
    SERVED_METHODS,
    SessionError,
    SessionLaunchRequest,
    SessionReady,
    SessionServer,
)
from ansys.visor.viewer.app.paraview.session_process import ParaviewSessionProcess
from ansys.visor.viewer.config import Settings
from ansys.visor.viewer.core.errors import (
    ParaviewNotConfiguredError,
    ParaviewSessionError,
    PvserverConnectionError,
)
from ansys.visor.viewer.core.pvserver_address import PvserverAddress

REQUEST = SessionLaunchRequest(
    url="http://localhost:8081",
    standalone=True,
    dark_mode=None,
    trame_log_dir=None,
    pvserver=PvserverAddress(host="localhost", port=11111),
)


def run_bounded(fn, timeout=15.0):
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
    def list_datasets(self):
        return {1: "a"}


class FakeStdin:
    """Collects what the parent writes and starts the fake child when closed."""

    def __init__(self, on_close):
        self.data = b""
        self._on_close = on_close

    def write(self, data):
        self.data += data

    def flush(self):
        pass

    def close(self):
        self._on_close()


class FakePopen:
    """A session process whose behaviour is chosen by the test.

    ready     connect, report ready, serve until shutdown, exit 0
    error     connect, report PvserverConnectionError, exit 1
    silent    connect, read the request, never reply
    absent    never connect
    exits     exit with code 3 before connecting
    stubborn  like ready, but survives shutdown and terminate until killed
    """

    def __init__(self, command, stdin, stdout, stderr, behaviour):
        self.args = command
        self.stdin_arg = stdin
        self.stdout_arg = stdout
        self.stderr_arg = stderr
        self.behaviour = behaviour
        self.stdin = FakeStdin(self._start)
        self.pid = 4242
        self.returncode = None
        self.request = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self._exited = threading.Event()
        self._released = threading.Event()

    def _start(self):
        if self.behaviour == "exits":
            self._exit(3)
            return
        if self.behaviour != "absent":
            threading.Thread(target=self._play, daemon=True).start()

    def _play(self):
        authkey = bytes.fromhex(self.stdin.data.decode("ascii").strip())
        connection = Client(("127.0.0.1", int(self.args[-1])), authkey=authkey)
        self.request = connection.recv()
        if self.behaviour == "error":
            connection.send(SessionError.from_exception(
                PvserverConnectionError("Could not connect to pvserver at localhost:11111")
            ))
            connection.close()
            self._exit(1)
            return
        if self.behaviour == "silent":
            self._released.wait(30)
            connection.close()
            return
        connection.send(SessionReady())
        SessionServer(connection, Target(), SERVED_METHODS, run_coroutine=asyncio.run).serve_forever()
        connection.close()
        if self.behaviour == "ready":
            self._exit(0)

    def _exit(self, code):
        self.returncode = code
        self._exited.set()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if not self._exited.wait(timeout):
            raise subprocess.TimeoutExpired(self.args, timeout)
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1
        if self.behaviour != "stubborn":
            self._released.set()
            self._exit(1)

    def kill(self):
        self.kill_calls += 1
        self._released.set()
        self._exit(-9)


@pytest.fixture
def spawn(monkeypatch, tmp_path):
    """Return a function that builds a ParaviewSessionProcess whose Popen is a FakePopen with the given behaviour."""
    monkeypatch.setattr(session_process, "END_GRACE_S", 0.2)
    created = []

    def build(behaviour, start_timeout=10.0):
        def fake_popen(command, stdin, stdout, stderr):
            created.append(FakePopen(command, stdin, stdout, stderr, behaviour))
            return created[-1]

        monkeypatch.setattr(session_process.subprocess, "Popen", fake_popen)
        process = ParaviewSessionProcess(
            pvpython=Path("pv") / "pvpython.exe",
            venv=Path("pv") / ".pvenv",
            log_path=tmp_path / "logs" / "visor_paraview_session_8081.log",
            start_timeout=start_timeout,
        )
        return process, created

    return build


def test_launch_command_line_and_streams(spawn, tmp_path):
    process, created = spawn("ready")

    run_bounded(lambda: process.launch(REQUEST))
    popen = created[0]
    authkey_hex = popen.stdin.data.decode("ascii").strip()
    run_bounded(process.end)

    assert popen.args[0] == str(Path("pv") / "pvpython.exe")
    assert popen.args[1:3] == ["--venv", "pv/.pvenv"]
    assert Path(popen.args[3]).name == "session_main.py"
    assert popen.args[4:7] == ["--channel-host", "127.0.0.1", "--channel-port"]
    assert popen.args[7].isdigit() and popen.args[7] != "0"
    assert len(authkey_hex) == 64
    assert authkey_hex not in " ".join(popen.args)
    assert popen.stdin_arg is subprocess.PIPE
    assert popen.stdout_arg.name == str(tmp_path / "logs" / "visor_paraview_session_8081.log")
    assert popen.stdout_arg.mode == "ab"
    assert popen.stderr_arg is subprocess.STDOUT


def test_launch_delivers_request_and_returns_working_channel(spawn):
    process, created = spawn("ready")

    channel = run_bounded(lambda: process.launch(REQUEST))
    result = run_bounded(lambda: channel.call("list_datasets"))
    run_bounded(process.end)

    assert created[0].request == REQUEST
    assert result == {1: "a"}
    assert created[0].returncode == 0
    assert created[0].terminate_calls == 0
    assert process.alive is False


def test_reported_pvserver_error_is_raised_and_child_ended(spawn):
    process, created = spawn("error")

    with pytest.raises(PvserverConnectionError, match="^Could not connect to pvserver at localhost:11111$"):
        run_bounded(lambda: process.launch(REQUEST))

    assert process.alive is False
    assert created[0].returncode == 1


def test_child_that_never_reports_ready_is_terminated_and_log_named(spawn, tmp_path):
    process, created = spawn("silent", start_timeout=1.0)

    with pytest.raises(ParaviewSessionError) as raised:
        run_bounded(lambda: process.launch(REQUEST))

    assert str(raised.value) == (
        "The PARAVIEW session process did not report ready within 1.0 s; "
        f"see its log at {tmp_path / 'logs' / 'visor_paraview_session_8081.log'}"
    )
    assert created[0].terminate_calls == 1
    assert process.alive is False


def test_child_that_never_connects_times_out(spawn, tmp_path):
    process, created = spawn("absent", start_timeout=1.0)

    with pytest.raises(ParaviewSessionError) as raised:
        run_bounded(lambda: process.launch(REQUEST))

    assert str(raised.value) == (
        "The PARAVIEW session process did not connect within 1.0 s; "
        f"see its log at {tmp_path / 'logs' / 'visor_paraview_session_8081.log'}"
    )
    assert created[0].terminate_calls == 1


def test_child_that_exits_before_connecting_fails_fast(spawn, tmp_path):
    process, _created = spawn("exits", start_timeout=60.0)
    started = time.monotonic()

    with pytest.raises(ParaviewSessionError) as raised:
        run_bounded(lambda: process.launch(REQUEST))

    assert time.monotonic() - started < 5.0
    assert str(raised.value) == (
        "The PARAVIEW session process exited with code 3 before it could connect; "
        f"see its log at {tmp_path / 'logs' / 'visor_paraview_session_8081.log'}"
    )


def test_end_escalates_to_kill_and_is_idempotent(spawn):
    process, created = spawn("stubborn")
    run_bounded(lambda: process.launch(REQUEST))

    run_bounded(process.end)
    run_bounded(process.end)

    assert created[0].terminate_calls == 1
    assert created[0].kill_calls == 1
    assert created[0].returncode == -9


def test_from_settings_names_missing_key_and_builds_log_path(tmp_path):
    with pytest.raises(ParaviewNotConfiguredError, match="^PARAVIEW mode needs 'paraview_pvpython' set in the .visor file$"):
        ParaviewSessionProcess.from_settings(Settings(paraview_pvpython=None, paraview_venv="venv"), 8081)
    with pytest.raises(ParaviewNotConfiguredError, match="^PARAVIEW mode needs 'paraview_venv' set in the .visor file$"):
        ParaviewSessionProcess.from_settings(Settings(paraview_pvpython="pvpython", paraview_venv=None), 8081)

    process = ParaviewSessionProcess.from_settings(
        Settings(paraview_pvpython="pvpython", paraview_venv="venv", default_log_dir=str(tmp_path)), 8081
    )

    assert process.log_path == tmp_path / "visor_paraview_session_8081.log"
