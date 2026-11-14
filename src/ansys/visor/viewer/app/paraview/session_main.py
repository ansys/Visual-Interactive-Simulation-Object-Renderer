"""
Session main
============
The program pvpython runs for one PARAVIEW session.

It reads the channel authkey from the first line of stdin, connects to the
parent on ``--channel-host``/``--channel-port``, receives a
:class:`SessionLaunchRequest`, connects to pvserver, builds a
:class:`VisorVTKParaview` and reports ready or failed.  It then serves the
channel until shutdown or until the connection closes, and exits.  A parent
that exits or crashes closes the connection, so this process exits with it.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import traceback
from multiprocessing.connection import Connection, answer_challenge, deliver_challenge
from typing import TextIO

from ansys.visor.viewer.app.paraview.session_channel import (
    SERVED_METHODS,
    SessionError,
    SessionLaunchRequest,
    SessionReady,
    SessionServer,
)
from ansys.visor.viewer.app.paraview.visor_vtk_paraview import VisorVTKParaview
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.renderer.paraview_session import PvSimpleSession

logger = VisorDefaultLogger(__name__)


class ParaviewSessionMain:
    """The pvpython-side program: parse argv, read the authkey, build the session, serve the channel."""

    def __init__(self, argv: list[str], stdin: TextIO) -> None:
        """Parse --channel-host/--channel-port with parse_known_args, since pvpython adds arguments of its own."""
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--channel-host", required=True)
        parser.add_argument("--channel-port", required=True, type=int)
        options, _unknown = parser.parse_known_args(argv)
        self._host: str = options.channel_host
        self._port: int = options.channel_port
        self._stdin = stdin

    def run(self) -> int:
        """Connect the channel, build VisorVTKParaview, report ready or failed, serve; return the exit code."""
        authkey = bytes.fromhex(self._stdin.readline().strip())
        if not authkey:
            logger.error("No channel authkey on stdin")
            print("No channel authkey on stdin", file=sys.stderr)
            return 1
        connection = self._connect(authkey)
        try:
            return self._serve(connection)
        finally:
            connection.close()

    def connect_session(self, request: SessionLaunchRequest) -> PvSimpleSession:
        """Connect to the requested pvserver."""
        return PvSimpleSession(request.pvserver)

    def build_visor(self, request: SessionLaunchRequest, session: PvSimpleSession) -> VisorVTKParaview:
        """Build the session's Visor over the connected session."""
        return VisorVTKParaview(
            url=request.url,
            standalone=request.standalone,
            dark_mode=request.dark_mode,
            trame_log_dir=request.trame_log_dir,
            pvserver=request.pvserver,
            session=session,
        )

    def _connect(self, authkey: bytes) -> Connection:
        """Connect to the parent and authenticate both ways, in the order the parent expects."""
        sock = socket.create_connection((self._host, self._port))
        connection = Connection(sock.detach())
        answer_challenge(connection, authkey)
        deliver_challenge(connection, authkey)
        return connection

    def _serve(self, connection: Connection) -> int:
        """Build the session from the parent's request, report the outcome, and serve until the channel ends."""
        request: SessionLaunchRequest = connection.recv()
        try:
            session = self.connect_session(request)
        except Exception as exc:
            logger.exception("Could not connect the ParaView session")
            traceback.print_exc()
            connection.send(SessionError.from_exception(exc))
            return 1
        try:
            try:
                visor = self.build_visor(request, session)
            except Exception as exc:
                logger.exception("Could not build the PARAVIEW Visor")
                traceback.print_exc()
                connection.send(SessionError.from_exception(exc))
                return 1
            connection.send(SessionReady())
            runner = visor._server_manager.async_runner
            server = SessionServer(
                connection,
                visor,
                SERVED_METHODS,
                run_coroutine=lambda coroutine: runner.run_coroutine_block(coroutine, False),
            )
            server.serve_forever()
            if visor.running:
                visor.stop()
            return 0
        finally:
            session.disconnect()


def main() -> int:
    """Run ParaviewSessionMain over sys.argv and sys.stdin, then end the process.

    A failure is written to stderr, which is the session log, as well as to
    the Visor log.  ``os._exit`` ends the process even if a non-daemon thread
    is still running, so the process never outlives its channel.
    """
    code = 1
    try:
        code = ParaviewSessionMain(sys.argv[1:], sys.stdin).run()
    except BaseException:
        logger.exception("PARAVIEW session failed")
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code


if __name__ == "__main__":
    main()
