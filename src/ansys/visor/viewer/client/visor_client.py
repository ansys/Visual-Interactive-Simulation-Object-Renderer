"""Example HTTP client for the Visor server's update_variables endpoint.

Usage::

    client = VisorClient("http://localhost:53211")
    client.update_variables(dataset_id, [
        {"type": "POINT", "name": "temperature", "num_components": 1, "data": temps},
        {"type": "CELL", "name": "velocity", "num_components": 3, "data": vel, "part_id": 42},
    ])
"""

import json
from enum import Enum
from typing import Any, Dict, List

import numpy as np
import requests

from ansys.visor.viewer.api.models import StartProps, UpdateProps, SaveStateProps, LoadStateProps, \
    UpdateVariableBinaryProps, RemoveDatasetProps, UpdateVariableBinaryInfo
from ansys.visor.viewer.config import settings


class _VisorClient:
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

    def start(self, args: StartProps) -> requests.Response:
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
        resp = requests.post(f"{self.base}/start", json=args.model_dump(exclude_none=True))
        resp.raise_for_status()
        return resp

    def update(self, args: UpdateProps) -> requests.Response:
        """Update the current visualization with new data.

        Parameters
        ----------
        file_path : str
            Path to the updated data file.
        metadata_path : str
            Path to the updated metadata file.
        """
        resp = requests.post(f"{self.base}/update", json=args.model_dump(exclude_none=True))
        resp.raise_for_status()
        return resp

    def add_dataset(self, args: UpdateProps) -> requests.Response:
        """Add an additional dataset to the current visualization.

        Parameters
        ----------
        file_path : str
            Path to the data file to add.
        metadata_path : str
            Path to the associated metadata file.
        """
        resp = requests.post(f"{self.base}/add_dataset", json=args.model_dump(exclude_none=True))
        resp.raise_for_status()
        return resp

    def list_datasets(self) -> requests.Response:
        """Print all datasets currently loaded in the viewer."""
        resp = requests.get(f"{self.base}/list_datasets")
        resp.raise_for_status()
        return resp

    def remove_dataset(self, args: RemoveDatasetProps) -> requests.Response:
        """Remove a dataset from the current visualization.

        Parameters
        ----------
        dataset_id : int
            Numeric identifier of the dataset to remove.
        """
        resp = requests.post(f"{self.base}/remove_dataset", json=args.model_dump(exclude_none=True))
        resp.raise_for_status()
        return resp

    def stop_visualization(self) -> requests.Response:
        """Stop the active visualization without shutting down the instance."""
        resp = requests.post(f"{self.base}/stop_visualization")
        resp.raise_for_status()
        return resp

    def stop(self) -> requests.Response:
        """Stop the viewer instance entirely."""
        resp = requests.post(f"{self.base}/stop")
        resp.raise_for_status()
        return resp

    def save_state(self, args: SaveStateProps) -> requests.Response:
        """Save the current viewer state to disk.

        Parameters
        ----------
        state_dir : str
            Directory path where the state files will be written.
        """
        resp = requests.post(f"{self.base}/save_state", json=args.model_dump(exclude_none=True))
        resp.raise_for_status()
        return resp

    def load_state(self, args: LoadStateProps) -> requests.Response:
        """Load a previously saved viewer state from disk.

        Parameters
        ----------
        state_dir : str
            Directory path containing the state files to load.
        """
        resp = requests.post(f"{self.base}/load_state", json=args.model_dump(exclude_none=True))
        resp.raise_for_status()
        return resp

    def list_variables(self, dataset_id: int) -> requests.Response:
        """List all variables for a given dataset."""
        resp = requests.get(f"{self.base}/{dataset_id}/list_variables")
        resp.raise_for_status()
        return resp

    def update_variables(self, dataset_id: int, args: UpdateVariableBinaryProps) -> requests.Response:
        """Send variable updates as one multipart request with float32 binary parts."""
        metadata = {"variables": [self._metadata_of(var) for var in args.variables]}
        files = [
            ("data", (f"{i}.bin", self._payload_of(var), "application/octet-stream"))
            for i, var in enumerate(args.variables)
        ]
        resp = requests.post(
            f"{self.base}/{dataset_id}/update_variables",
            data={"metadata": json.dumps(metadata)},
            files=files,
        )
        resp.raise_for_status()
        return resp

    @staticmethod
    def _metadata_of(variable: UpdateVariableBinaryInfo) -> Dict[str, Any]:
        """Returns the variable's fields other than data, with an enum type converted to its name."""
        var_type = variable["type"]
        return {
            "name": variable["name"],
            "type": var_type.name if isinstance(var_type, Enum) else str(var_type),
            "num_components": int(variable["num_components"]),
            "part_id": variable.get("part_id"),
        }

    @staticmethod
    def _payload_of(variable: UpdateVariableBinaryInfo) -> bytes:
        """Encodes the variable's data as C-ordered little-endian float32 bytes."""
        return np.asarray(variable["data"], dtype="<f4").tobytes(order="C")


class VisorCliClient:
    """Client for controlling a single Visor viewer instance via the command-line interface.

    Uses _VisorClient internally to send requests to the Visor server, but provides a simpler interface
    for CLI commands.

    Parameters
    ----------
    host : str
        Hostname or IP address of the Visor server.
    port : int or str
        Port number of the Visor server.
    """
    def __init__(self, host, port):
        self._client = _VisorClient(host, port)

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
        resp = self._client.start(StartProps(**data))
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
        resp = self._client.update(UpdateProps(**data))
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
        resp = self._client.add_dataset(UpdateProps(**data))
        print(resp.json())

    def list_datasets(self):
        """Print all datasets currently loaded in the viewer."""
        resp = self._client.list_datasets()
        print(json.dumps(resp.json().get("datasets", {}), indent=4))

    def remove_dataset(self, dataset_id: int):
        """Remove a dataset from the current visualization.

        Parameters
        ----------
        dataset_id : int
            Numeric identifier of the dataset to remove.
        """
        data = {"dataset_id": dataset_id}
        resp = self._client.remove_dataset(RemoveDatasetProps(**data))
        print(resp.json())

    def stop_visualization(self):
        """Stop the active visualization without shutting down the instance."""
        resp = self._client.stop_visualization()
        print(resp.json())

    def stop(self):
        """Stop the viewer instance entirely."""
        resp = self._client.stop()
        print(resp.json())

    def save(self, state_dir):
        """Save the current viewer state to disk.

        Parameters
        ----------
        state_dir : str
            Directory path where the state files will be written.
        """
        data = {"state_dir": state_dir}
        resp = self._client.save_state(SaveStateProps(**data))
        print(resp.json())

    def load(self, state_dir):
        """Load a previously saved viewer state from disk.

        Parameters
        ----------
        state_dir : str
            Directory path containing the state files to load.
        """
        data = {"state_dir": state_dir}
        resp = self._client.load_state(LoadStateProps(**data))
        print(resp.json())

    def list_variables(self, dataset_id: int) -> None:
        """List all variables for a given dataset."""
        resp = self._client.list_variables(dataset_id)
        data = [self._variable_summary(part) for part in resp.json().get("parts", [])]
        print(json.dumps(data, indent=4))

    def _variable_summary(self, part: Dict[str, Any]) -> Dict[str, Any]:
        """Return a summary of the variables in a part, excluding the actual data."""
        return {
            "part_id": part.get("part_id"),
            "variables": [f"{var.get('name')}::{var.get('type')}::{var.get('num_components')}"
                for var in part.get("variables", [])
            ],
        }

    def update_variables(self, dataset_id: int, variables: List[Dict[str, Any]]) -> None:
        """Send variable updates as one multipart request with float32 binary parts."""
        data = {"variables": [UpdateVariableBinaryInfo(**var) for var in variables]}
        resp = self._client.update_variables(dataset_id, UpdateVariableBinaryProps(**data))
        print(resp.json())
        print(f'Updated {len(variables)} variables for dataset {dataset_id}. Status code: {resp.status_code}')

