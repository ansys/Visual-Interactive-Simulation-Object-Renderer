"""API client for controlling a Visor server."""

import os
import shutil
import time

import requests
import uvicorn

from ansys.visor.viewer.config import settings


class ServerAPI:
    """Client for managing the Visor server process.

    Provides methods to start the server and interact with server-level
    endpoints such as health checks, server info, initialization, and
    listing available viewer instances.

    Parameters
    ----------
    host : str
        Hostname or IP address on which the server is (or will be) running.
    port : int or str
        Port number on which the server is (or will be) listening.
    """
    def __init__(self, host, port):
        """Initialize the server with viewer configuration."""
        self.host = host
        self.port = port
        binding_host = settings.binding_host or host
        scheme = settings.url_scheme
        self.base = f"{scheme}://{binding_host}:{port}"

    def start(self):
        """Start the Visor server.

        Notes
        -----
        This call blocks until the server is stopped.
        """
        app = "ansys.visor.viewer.api.server:app"

        print(
            f"Starting the Visor server using uvicorn.run({app!r}, host={self.host!r}, port={self.port!r})"
        )

        # Note: uvicorn.run() blocks until shutdown.
        uvicorn.run(app, host=self.host, port=int(self.port), log_level="info")

    def initialize(self, host, port, rendering_mode, standalone, dark_mode, start=False):
        """Initialize the server with viewer configuration.

        Parameters
        ----------
        host : str
            Hostname the viewer client should connect to.
        port : int
            Port the viewer client should connect to.  Pass ``0`` to let
            the Visor server pick an unused port on its own host.
        rendering_mode : RenderingMode
            Rendering mode to use for the viewer instance.  Must be one of the
            values defined in ``RenderingMode``.
        standalone : bool
            Whether to run in standalone mode (no external orchestrator).
        dark_mode : bool
            Whether to enable dark mode in the viewer UI.
        start : bool
            Whether to start the viewer instance immediately after initialization.

        Raises
        ------
        requests.HTTPError
            If the ``/initialize`` request or, when ``start`` is ``True``,
            the ``/start`` request returns an HTTP error status.
        """
        data = {"host": host, "port": port, "rendering_mode": rendering_mode, "standalone": standalone,
                "dark_mode": dark_mode}
        resp = requests.post(f"{self.base}/initialize", json=data)
        print(resp.json())
        resp.raise_for_status()
        if start:
            resp = requests.post(f"{self.base}/start", json={})
            print(resp)
            print(resp.json())
            resp.raise_for_status()


class LogsAPI:
    """Utility for browsing and tailing Visor log files.

    Provides methods to list available log files and print their contents,
    with optional real-time following similar to ``tail -f``.

    Parameters
    ----------
    log_dir : str, optional
        Directory that contains the ``.log`` files.  Defaults to
        ``settings.default_log_dir`` when not supplied.
    """
    def __init__(self, log_dir=None):
        self.log_dir = log_dir or settings.default_log_dir

    def list_logs(self):
        """Print the names of all ``.log`` files found in the log directory."""
        if not os.path.isdir(self.log_dir):
            print(f"Log directory not found: {self.log_dir}")
            return
        files = [f for f in os.listdir(self.log_dir) if f.endswith(".log")]
        if not files:
            print(f"No log files found in log dir {self.log_dir}.")
        else:
            print(f"Available log files in log dir {self.log_dir}:")
            for f in files:
                print("  " + f[:-4])  # strip .log

    def tail_log(self, log_name, follow=False, lines=10):
        """Display the contents of a log file.

        Parameters
        ----------
        log_name : str
            Name of the log file to tail, without the ``.log`` extension.
        follow : bool, optional
            When ``True``, print the last *lines* lines and then stream new
            content as it is appended (like ``tail -f``).  Defaults to
            ``False``.
        lines : int, optional
            Number of lines from the end of the file to tail.  Defaults
            to ``10``.
        """
        log_path = os.path.join(self.log_dir, f"{log_name}.log")
        try:
            with open(log_path, "r") as f:
                from collections import deque
                if follow:
                    # Print last n lines first
                    f.seek(0)
                    last_lines = deque(f, maxlen=lines)
                    print("".join(last_lines), end="")
                    # Now follow new lines
                    f.seek(0, 2)
                    while True:
                        line = f.readline()
                        if not line:
                            time.sleep(0.5)
                            continue
                        print(line, end="")
                else:
                    # Only print last n lines
                    print("".join(deque(f, maxlen=lines)), end="")
        except FileNotFoundError:
            print(f"Log file not found: {log_path}")

    def clear_logs(self, force=False):
        """Delete the log directory.

        Parameters
        ----------
        force : bool, optional
            When ``True``, skip the confirmation prompt.  Defaults to ``False``.

        Returns
        -------
        bool
            ``False`` if removing the log directory failed, ``True`` otherwise
            (including when the directory does not exist or the user aborts).

        Notes
        -----
        Nothing should be writing to the log directory (e.g. a running Visor
        server); otherwise deletion may fail on Windows or remove files that
        are still in use on Unix.
        """
        if not os.path.isdir(self.log_dir):
            print(f"Log directory not found: {self.log_dir}")
            return True
        if not force:
            print(f"Remove log directory {self.log_dir}? (y/n): ", end="")
            choice = input().strip().lower()
            if choice != "y":
                print("Aborted.")
                return True
        try:
            shutil.rmtree(self.log_dir)
        except Exception as e:
            print(f"Failed to remove log directory {self.log_dir}: {e}")
            return False
        print(f"Log directory removed: {self.log_dir}")
        return True
