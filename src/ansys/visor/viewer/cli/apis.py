"""API client for controlling a Visor server."""

import json
import os
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

    def health(self):
        """Print the server health-check response."""
        url = f"{self.base}/health"
        resp = requests.get(url)
        print(resp.json())

    def info(self):
        """Print general information about the running server."""
        resp = requests.get(f"{self.base}/info")
        print(resp.json())

    def initialize(self, host, port, rendering_mode, standalone, dark_mode):
        """Initialize the server with viewer configuration.

        Parameters
        ----------
        host : str
            Hostname the viewer client should connect to.
        port : int
            Port the viewer client should connect to.  Pass ``0`` to let
            the Visor server pick an unused port on its own host.
        standalone : RenderingMode
            Rendering mode to use for the viewer instance.  Must be one of the
            values defined in ``RenderingMode``.
        standalone : bool
            Whether to run in standalone mode (no external orchestrator).
        dark_mode : bool
            Whether to enable dark mode in the viewer UI.
        """
        data = {"host": host, "port": port, "rendering_mode": rendering_mode, "standalone": standalone, "dark_mode": dark_mode}
        resp = requests.post(f"{self.base}/initialize", json=data)
        print(resp.json())

    def list(self):
        """Print the URLs of all currently available viewer instances."""
        resp = requests.get(f"{self.base}")
        data = resp.json()
        if 'urls' in data and data['urls']:
            print("Available instances:")
            for url in data['urls']:
                print("  " + url)


class InstanceAPI:
    """Client for controlling a single Visor viewer instance.

    Wraps the instance-level REST endpoints exposed by the Visor server,
    allowing callers to start and stop visualizations, manage datasets,
    and save or restore viewer state.

    Parameters
    ----------
    host : str
        Hostname or IP address of the Visor server.
    port : int or str
        Port number of the Visor server.
    """
    def __init__(self, host, port):
        binding_host = settings.binding_host or host
        scheme = settings.url_scheme
        self.base = f"{scheme}://{binding_host}:{port}"

    def start(self, file_path, metadata_path, timeout):
        """Start a visualization for the given file.

        Parameters
        ----------
        file_path : str
            Path to the data file to visualize.
        metadata_path : str
            Path to the associated metadata file.
        timeout : int or float
            Maximum number of seconds to wait for the visualization to start.
        """
        data = {"file_path": file_path, "metadata": metadata_path, "timeout": timeout}
        resp = requests.post(f"{self.base}/start", json=data)
        print(resp)
        print(resp.json())

    def update(self, file_path, metadata_path):
        """Update the current visualization with new data.

        Parameters
        ----------
        file_path : str
            Path to the updated data file.
        metadata_path : str
            Path to the updated metadata file.
        """
        data = {"file_path": file_path, "metadata": metadata_path}
        resp = requests.post(f"{self.base}/update", json=data)
        print(resp.json())

    def add_dataset(self, file_path, metadata_path):
        """Add an additional dataset to the current visualization.

        Parameters
        ----------
        file_path : str
            Path to the data file to add.
        metadata_path : str
            Path to the associated metadata file.
        """
        data = {"file_path": file_path, "metadata": metadata_path}
        resp = requests.post(f"{self.base}/add_dataset", json=data)
        print(resp.json())

    def list_datasets(self):
        """Print all datasets currently loaded in the viewer."""
        resp = requests.get(f"{self.base}/list_datasets")
        print(json.dumps(resp.json().get("datasets", {}), indent=4))

    def remove_dataset(self, dataset_id: int):
        """Remove a dataset from the current visualization.

        Parameters
        ----------
        dataset_id : int
            Numeric identifier of the dataset to remove.
        """
        data = {"dataset_id": dataset_id}
        resp = requests.post(f"{self.base}/remove_dataset", json=data)
        print(resp.json())

    def stop_visualization(self):
        """Stop the active visualization without shutting down the instance."""
        resp = requests.post(f"{self.base}/stop_visualization")
        print(resp.json())

    def stop(self):
        """Stop the viewer instance entirely."""
        resp = requests.post(f"{self.base}/stop")
        print(resp.json())

    def save(self, state_dir):
        """Save the current viewer state to disk.

        Parameters
        ----------
        state_dir : str
            Directory path where the state files will be written.
        """
        data = {"state_dir": state_dir}
        resp = requests.post(f"{self.base}/save_state", json=data)
        print(resp.json())

    def load(self, state_dir):
        """Load a previously saved viewer state from disk.

        Parameters
        ----------
        state_dir : str
            Directory path containing the state files to load.
        """
        data = {"state_dir": state_dir}
        resp = requests.post(f"{self.base}/load_state", json=data)
        print(resp.json())


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
            print("No log files found.")
        else:
            print("Available log files:")
            for f in files:
                print("  " + f[:-4])  # strip .log

    def show_log(self, log_name, follow=False, lines=10):
        """Display the contents of a log file.

        Parameters
        ----------
        log_name : str
            Name of the log file to display, without the ``.log`` extension.
        follow : bool, optional
            When ``True``, print the last *lines* lines and then stream new
            content as it is appended (like ``tail -f``).  Defaults to
            ``False``.
        lines : int, optional
            Number of lines from the end of the file to display.  Defaults
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
