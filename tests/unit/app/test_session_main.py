"""Unit tests for ``ParaviewSessionMain``: reporting a failed build, reporting
ready and serving until shutdown, and ending when the parent closes the channel.

Mocking boundary: the ``connect_session`` and ``build_visor`` seams, overridden
in a subclass.  The test plays the parent over a real loopback connection;
ParaView is not imported and no trame server starts.
"""

import io
import secrets
import socket
import threading
from multiprocessing.connection import Connection, answer_challenge, deliver_challenge
from unittest.mock import MagicMock

import pytest

from ansys.visor.viewer.app.paraview.session_channel import (
    SessionError,
    SessionLaunchRequest,
    SessionReady,
    SessionRequest,
    SessionResult,
    SessionShutdown,
)
from ansys.visor.viewer.app.paraview.session_main import ParaviewSessionMain
from ansys.visor.viewer.core.errors import InvalidPathError
from ansys.visor.viewer.core.pvserver_address import PvserverAddress

REQUEST = SessionLaunchRequest(
    url="http://localhost:8081",
    standalone=True,
    dark_mode=False,
    trame_log_dir=None,
    pvserver=PvserverAddress(host="localhost", port=11111),
)


class SeamedMain(ParaviewSessionMain):
    """ParaviewSessionMain with the session and the Visor supplied by the test."""

    def __init__(self, argv, stdin, session, visor=None, build_error=None):
        super().__init__(argv, stdin)
        self.session = session
        self.visor = visor
        self.build_error = build_error
        self.built_with = None

    def connect_session(self, request):
        return self.session

    def build_visor(self, request, session):
        self.built_with = (request, session)
        if self.build_error is not None:
            raise self.build_error
        return self.visor


@pytest.fixture
def parent():
    """Return a function that starts a SeamedMain against a listening parent and yields (connection, outcome, thread)."""
    started = []

    def start(**seams):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(10)
        authkey = secrets.token_bytes(32)
        argv = ["--channel-host", "127.0.0.1", "--channel-port", str(listener.getsockname()[1]), "--pvpython-own-arg"]
        main = SeamedMain(argv, io.StringIO(authkey.hex() + "\n"), **seams)
        outcome = {}
        thread = threading.Thread(target=lambda: outcome.update(code=main.run()), daemon=True)
        thread.start()
        sock, _address = listener.accept()
        listener.close()
        sock.setblocking(True)
        connection = Connection(sock.detach())
        deliver_challenge(connection, authkey)
        answer_challenge(connection, authkey)
        connection.send(REQUEST)
        assert connection.poll(10), "no reply to the launch request"
        started.append(connection)
        return connection, outcome, thread, main

    yield start
    for connection in started:
        connection.close()


def test_build_failure_is_reported_and_run_returns_1(parent):
    session = MagicMock(name="session")

    connection, outcome, thread, main = parent(session=session, build_error=InvalidPathError("p"))
    reply = connection.recv()
    thread.join(10)

    assert reply == SessionError(type_name="InvalidPathError", message="p")
    assert main.built_with == (REQUEST, session)
    assert outcome == {"code": 1}
    session.disconnect.assert_called_once_with()


def test_ready_then_serves_until_shutdown(parent):
    session = MagicMock(name="session")
    visor = MagicMock(name="visor")
    visor.list_datasets.return_value = {1: "a"}
    visor.running = True

    connection, outcome, thread, _main = parent(session=session, visor=visor)
    ready = connection.recv()
    connection.send(SessionRequest(method="list_datasets"))
    assert connection.poll(10)
    result = connection.recv()
    connection.send(SessionShutdown())
    thread.join(10)

    assert ready == SessionReady()
    assert result == SessionResult(value={1: "a"})
    assert outcome == {"code": 0}
    visor.stop.assert_called_once_with()
    session.disconnect.assert_called_once_with()


def test_parent_closing_channel_ends_the_session(parent):
    session = MagicMock(name="session")
    visor = MagicMock(name="visor")
    visor.running = False

    connection, outcome, thread, _main = parent(session=session, visor=visor)
    assert connection.recv() == SessionReady()
    connection.close()
    thread.join(10)

    assert not thread.is_alive()
    assert outcome == {"code": 0}
    visor.stop.assert_not_called()
    session.disconnect.assert_called_once_with()
