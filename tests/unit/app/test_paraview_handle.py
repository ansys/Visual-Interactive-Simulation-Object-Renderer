"""Unit tests for ``VisorParaviewHandle``: the launch of its session process,
the forwarding of each Visor method over the session channel, blocking start
and the end of the session process.

Mocking boundary: ``VisorParaviewHandle._create_session_process`` returns a
fake session process whose channel records each call and the thread it was
made on; ``ParaviewSessionProcess.from_settings`` where the ``Visor`` factory
is exercised.  No pvpython is started.
"""

import asyncio
import gc
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.app.paraview import paraview_handle
from ansys.visor.viewer.app.paraview.paraview_handle import VisorParaviewHandle
from ansys.visor.viewer.app.paraview.session_process import ParaviewSessionProcess
from ansys.visor.viewer.app.visor import Visor
from ansys.visor.viewer.config import settings
from ansys.visor.viewer.core.errors import (
    ParaviewNotConfiguredError,
    ParaviewSessionError,
    PvserverConnectionError,
    UnsupportedInModeError,
)
from ansys.visor.viewer.core.pvserver_address import PvserverAddress

URL = "http://localhost:8095"
ADDRESS = PvserverAddress(host="pv.example", port=22222)


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


class FakeChannel:
    """Records each call; a handler set for a method runs in its place."""

    def __init__(self):
        self.calls = []
        self.handlers = {}
        self.started = threading.Event()

    def call(self, method, *args):
        self.calls.append((method, args, threading.get_ident()))
        if method == "start":
            self.started.set()
        if method in self.handlers:
            return self.handlers[method](*args)
        return f"{method}-result"


class FakeSessionProcess:
    def __init__(self, launch_error=None):
        self.channel = FakeChannel()
        self.launch_error = launch_error
        self.requests = []
        self.alive = False
        self.exit_code = None
        self.end_calls = 0
        self.pid = 4242
        self.log_path = Path("logs") / "visor_paraview_session_8095.log"

    def launch(self, request):
        self.requests.append(request)
        if self.launch_error is not None:
            raise self.launch_error
        self.alive = True
        return self.channel

    def end(self):
        self.end_calls += 1
        self.alive = False
        self.exit_code = 0


@pytest.fixture
def fake(monkeypatch):
    """The session process every handle built in the test is given."""
    process = FakeSessionProcess()
    monkeypatch.setattr(VisorParaviewHandle, "_create_session_process", lambda self: process)
    monkeypatch.setattr(paraview_handle, "BLOCKING_WAIT_SLICE_S", 0.01)
    return process


@pytest.fixture
def handle(fake):
    built = VisorParaviewHandle(url=URL, pvserver=ADDRESS)
    yield built
    built.close()


class StubEvent:
    """An event whose wait is chosen by the test; set and is_set behave as threading.Event."""

    def __init__(self, wait):
        self._flag = False
        self._wait = wait

    def set(self):
        self._flag = True

    def clear(self):
        self._flag = False

    def is_set(self):
        return self._flag

    def wait(self, timeout=None):
        return self._wait()


def test_init_launches_session_with_request_fields(fake):
    handle = VisorParaviewHandle(url=URL, standalone=False, dark_mode=True, trame_log_dir="tl", pvserver=ADDRESS)

    request = fake.requests[0]
    assert request.url == "http://localhost:8095"
    assert request.standalone is False
    assert request.dark_mode is True
    assert request.trame_log_dir == "tl"
    assert request.pvserver == ADDRESS
    assert handle.pvserver == ADDRESS
    handle.close()


def test_init_uses_settings_default_pvserver_when_omitted(fake, monkeypatch):
    monkeypatch.setattr(paraview_handle, "settings", MagicMock())
    paraview_handle.settings.default_pvserver_address.return_value = PvserverAddress(host="dflt", port=11111)

    handle = VisorParaviewHandle(url=URL)

    assert fake.requests[0].pvserver == PvserverAddress(host="dflt", port=11111)
    assert handle.pvserver == PvserverAddress(host="dflt", port=11111)
    handle.close()


def test_init_logs_ready_line_with_url_pvserver_and_pid(fake, monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(paraview_handle, "logger", logger)

    handle = VisorParaviewHandle(url=URL, pvserver=ADDRESS)

    logger.info.assert_called_once_with(
        "PARAVIEW session ready on %s (pvserver %s, pid %s)", "http://localhost:8095", ADDRESS, 4242
    )
    handle.close()


def test_finalizer_ends_session_process(fake):
    handle = VisorParaviewHandle(url=URL, pvserver=ADDRESS)

    del handle
    gc.collect()

    assert fake.end_calls == 1


def test_launch_error_propagates(monkeypatch):
    process = FakeSessionProcess(launch_error=PvserverConnectionError("Could not connect to pvserver at pv.example:22222"))
    monkeypatch.setattr(VisorParaviewHandle, "_create_session_process", lambda self: process)

    with pytest.raises(PvserverConnectionError, match="^Could not connect to pvserver at pv.example:22222$"):
        VisorParaviewHandle(url=URL, pvserver=ADDRESS)


@pytest.mark.parametrize(("method", "args"), [
    ("update", ("a.vtu", None)),
    ("add_dataset", ("a.vtu", None)),
    ("remove_dataset", (3,)),
    ("list_datasets", ()),
    ("list_variables", (3,)),
    ("load_state", ("state_dir",)),
])
def test_methods_forward_to_channel(handle, fake, method, args):
    result = getattr(handle, method)(*args)

    assert result == f"{method}-result"
    assert [(name, called_args) for name, called_args, _ in fake.channel.calls] == [(method, args)]


def test_start_forwards_without_blocking(handle, fake):
    result = run_bounded(lambda: handle.start("a.vtu", None, 5))

    assert result == "start-result"
    assert [(name, args) for name, args, _ in fake.channel.calls] == [("start", ("a.vtu", None, 5))]


@pytest.mark.parametrize("method", ["start", "update", "add_dataset"])
def test_non_str_input_raises_without_channel_call(handle, fake, method):
    with pytest.raises(UnsupportedInModeError, match="^in-memory dataset input is not supported in PARAVIEW mode$"):
        getattr(handle, method)(MagicMock(name="dataset"))

    assert fake.channel.calls == []


def test_blocking_start_returns_when_stopped(handle, fake):
    def stop_once_started():
        assert fake.channel.started.wait(5)
        handle.stop()

    stopper = threading.Thread(target=stop_once_started, daemon=True)
    stopper.start()

    result = run_bounded(lambda: handle.start("a.vtu", blocking=True))
    stopper.join(5)

    assert result == "start-result"
    assert [name for name, _, _ in fake.channel.calls] == ["start", "stop"]
    assert fake.end_calls == 0


def test_blocking_start_returns_when_closed(handle, fake):
    def close_once_started():
        assert fake.channel.started.wait(5)
        handle.close()

    closer = threading.Thread(target=close_once_started, daemon=True)
    closer.start()

    result = run_bounded(lambda: handle.start("a.vtu", blocking=True))
    closer.join(5)

    assert result == "start-result"
    assert fake.end_calls == 1


def test_blocking_start_raises_when_session_process_exits_by_itself(handle, fake):
    def exit_by_itself(*args):
        fake.alive = False
        fake.exit_code = 3
        return "start-result"

    fake.channel.handlers["start"] = exit_by_itself

    with pytest.raises(ParaviewSessionError) as raised:
        run_bounded(lambda: handle.start("a.vtu", blocking=True))

    assert str(raised.value) == (
        "The PARAVIEW session process exited with code 3 while start was blocking; "
        f"see its log at {Path('logs') / 'visor_paraview_session_8095.log'}"
    )
    assert fake.end_calls == 1


def test_blocking_start_interrupt_ends_session_and_reraises(handle, fake):
    def interrupt():
        raise KeyboardInterrupt

    handle._wait_released = StubEvent(interrupt)

    with pytest.raises(KeyboardInterrupt):
        handle.start("a.vtu", blocking=True)

    assert fake.end_calls == 1
    assert [name for name, _, _ in fake.channel.calls] == ["start"]


def test_session_ended_by_close_is_not_reported_as_error(handle, fake):
    """A wait that times out just as close ends the session process returns normally."""
    handle._wait_released = StubEvent(lambda: False)

    def close_during_start(*args):
        handle.close()
        return "start-result"

    fake.channel.handlers["start"] = close_during_start

    result = run_bounded(lambda: handle.start("a.vtu", blocking=True))

    assert result == "start-result"
    assert fake.end_calls == 1


def test_update_variables_raises_unsupported(handle, fake):
    with pytest.raises(UnsupportedInModeError, match="^update_variables is not supported in PARAVIEW mode$"):
        handle.update_variables(0, [])

    assert fake.channel.calls == []


def test_save_state_forwards_off_event_loop(handle, fake):
    loop_thread = threading.get_ident()

    asyncio.run(handle.save_state("state_dir"))

    [(name, args, thread)] = fake.channel.calls
    assert (name, args) == ("save_state", ("state_dir",))
    assert thread != loop_thread


def test_start_async_returns_dataset_id_and_none(handle, fake):
    fake.channel.handlers["start"] = lambda *args: 7

    result = asyncio.run(handle._start_async("a.vtu", None, 5))

    assert result == (7, None)
    assert [(name, args) for name, args, _ in fake.channel.calls] == [("start", ("a.vtu", None, 5))]


def test_stop_async_forwards_stop(handle, fake):
    asyncio.run(handle._stop_async())

    assert [(name, args) for name, args, _ in fake.channel.calls] == [("stop", ())]


def test_health_false_when_process_gone(handle, fake):
    fake.alive = False

    assert handle._health() is False
    assert fake.channel.calls == []


def test_health_forwards_when_alive(handle, fake):
    fake.channel.handlers["_health"] = lambda: True

    assert handle._health() is True


def test_close_ends_session_process_once(handle, fake):
    handle.close()
    handle.close()

    assert fake.end_calls == 1


def test_running_reflects_process_alive(handle, fake):
    assert handle.running is True

    fake.alive = False

    assert handle.running is False


def test_rendering_mode_other_than_paraview_rejected(fake):
    with pytest.raises(ValueError, match="^VisorParaviewHandle runs PARAVIEW sessions only, not CLIENT$"):
        VisorParaviewHandle(url=URL, rendering_mode="CLIENT")

    assert fake.requests == []


def test_visor_factory_returns_handle_for_paraview(monkeypatch):
    process = FakeSessionProcess()
    received = []

    def from_settings(given_settings, port):
        received.append((given_settings, port))
        return process

    monkeypatch.setattr(ParaviewSessionProcess, "from_settings", from_settings)

    handle = Visor(rendering_mode="PARAVIEW", url=URL, pvserver=ADDRESS)

    assert type(handle) is VisorParaviewHandle
    assert received == [(settings, 8095)]
    assert process.requests[0].pvserver == ADDRESS
    handle.close()


def test_production_seam_names_missing_pvpython(monkeypatch):
    monkeypatch.setattr(settings, "paraview_pvpython", None)

    with pytest.raises(ParaviewNotConfiguredError, match="^PARAVIEW mode needs 'paraview_pvpython' set in the .visor file$"):
        VisorParaviewHandle(url=URL, pvserver=ADDRESS)
