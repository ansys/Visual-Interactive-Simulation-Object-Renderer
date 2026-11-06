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


class VisorClient:
    """Minimal HTTP client example for the Visor update_variables endpoint."""

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    def update_variables(self, dataset_id: int, variables: List[Dict[str, Any]]) -> None:
        """Send variable updates as one multipart request with float32 binary parts."""
        metadata = {"variables": [self._metadata_of(var) for var in variables]}
        files = [
            ("data", (f"{i}.bin", self._payload_of(var), "application/octet-stream"))
            for i, var in enumerate(variables)
        ]
        resp = requests.post(
            f"{self._base_url}/{dataset_id}/update_variables",
            data={"metadata": json.dumps(metadata)},
            files=files,
        )
        resp.raise_for_status()

    @staticmethod
    def _metadata_of(variable: Dict[str, Any]) -> Dict[str, Any]:
        """Returns the variable's fields other than data, with an enum type converted to its name."""
        var_type = variable["type"]
        return {
            "name": variable["name"],
            "type": var_type.name if isinstance(var_type, Enum) else str(var_type),
            "num_components": int(variable["num_components"]),
            "part_id": variable.get("part_id"),
        }

    @staticmethod
    def _payload_of(variable: Dict[str, Any]) -> bytes:
        """Encodes the variable's data as C-ordered little-endian float32 bytes."""
        return np.asarray(variable["data"], dtype="<f4").tobytes(order="C")
