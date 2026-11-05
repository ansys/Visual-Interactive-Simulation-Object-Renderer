"""A single visualization step without shared product instances."""

import base64
import os
from pathlib import Path

import requests
from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import Solution, StepModel, StepsModel, StepSpec, transaction


def visor_request(path: str, payload: dict[str, object] | None = None) -> dict:
    """Call the Visor management API at `SAF_VISOR_API_URL`.

    Args:
        path: Endpoint path such as `/initialize`.
        payload: JSON body. The request is a POST when given, otherwise a GET.

    Returns:
        The decoded JSON response.
    """
    endpoint = os.environ["SAF_VISOR_API_URL"]
    response = requests.request(
        "GET" if payload is None else "POST",
        f"{endpoint}{path}",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def decode_upload(filename: str, contents: str) -> bytes:
    """Validate an uploaded VTP or VTU file name and decode its base64 data URL contents.

    Raises:
        ValueError: If the name is not a plain VTP/VTU filename or the file is empty.
    """
    if Path(filename).name != filename or Path(filename).suffix.lower() not in {".vtp", ".vtu"}:
        raise ValueError("Upload a VTP or VTU file with a plain filename.")
    data = base64.b64decode(contents.partition(";base64,")[2])
    if not data:
        raise ValueError("The uploaded file is empty.")
    return data


class VisualizationStep(StepModel):
    """Step that starts Visor and loads one uploaded geometry file."""

    initialized: bool = False
    viewer_host: str = ""
    viewer_port: int = 0
    uploaded_file: EntityHandle = NO_ENTITY
    uploaded_name: str = ""

    @transaction(self=StepSpec(upload=["initialized", "viewer_host", "viewer_port"]))
    def initialize(self) -> None:
        """Initialize and start an empty Visor visualizer and record its host and port."""
        visor_request("/initialize", {"host": "127.0.0.1", "port": 0, "standalone": False})
        visor_request("/start", {"file_path": None, "timeout": 60})
        info = visor_request("/info")
        self.viewer_host = info["host"]
        self.viewer_port = info["port"]
        self.initialized = True

    @transaction(
        self=StepSpec(
            download=["initialized"],
            upload=["uploaded_file", "uploaded_name"],
        )
    )
    def upload(self, filename: str, contents: str) -> None:
        """Store the uploaded file in BDM storage and pass the cached copy to Visor.

        Raises:
            RuntimeError: If Visor has not been initialized.
            ValueError: If the upload is not a valid, non-empty VTP or VTU file.
        """
        if not self.initialized:
            raise RuntimeError("Initialize Visor before uploading geometry.")
        data = decode_upload(filename, contents)
        scope = self.storage_scope
        path = scope.get_storage_root() / filename
        path.write_bytes(data)
        self.uploaded_file = scope.store(path)
        cached_path = scope.get_cached(self.uploaded_file)
        visor_request(
            "/update",
            {"file_path": str(cached_path), "metadata": {"name": filename, "unit": "m"}},
        )
        self.uploaded_name = filename


class Steps(StepsModel):
    """Steps of the smoke solution."""

    visualization: VisualizationStep


class SmokeSolution(Solution):
    """SAF solution with a single visualization step."""

    display_name: str = "Visor SAF smoke test"
    version: int = 1
    steps: Steps
