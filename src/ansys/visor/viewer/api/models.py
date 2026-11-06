"""Models for the Visor Viewer API."""

from typing import Any

import numpy as np
from pydantic import BaseModel, Field, field_validator

from ansys.visor.viewer.core.metadata import Metadata
from ansys.visor.viewer.core.visor_enums import RenderingMode
from ansys.visor.viewer.core.visor_helpers import validate_host


class Info(BaseModel):
    """Input for getting the current state of the visualizer instance."""
    app_name: str = Field(..., description="Application name")
    host: str = Field(..., description="Host address")
    port: int = Field(..., description="Port number")
    standalone: bool = Field(..., description="Standalone mode")
    datasets: list[str] = Field(description="Path to the input file")

class InitProps(BaseModel):
    """Properties for initializing the server."""
    host: str = Field(..., description="Host address", examples=["localhost"])
    port: int = Field(
        0,
        description=(
            "Port number.  Use 0 (the default) to let the Visor server pick an "
            "unused port on its own host."
        ),
        examples=[0],
    )
    standalone: bool | None = Field(None, description="Standalone", examples=[True])
    dark_mode: bool | None = Field(None, description="Dark mode enabled", examples=[False])
    rendering_mode: RenderingMode | None = Field(None, description="Rendering mode (CLIENT or SERVER)", examples=["CLIENT"])

    @field_validator("rendering_mode", mode="before")
    @classmethod
    def coerce_rendering_mode(cls, v):
        """Accept both the enum member and its name as a string (e.g. 'CLIENT', 'SERVER')."""
        if v is None or isinstance(v, RenderingMode):
            return v
        if isinstance(v, str):
            try:
                return RenderingMode[v.upper()]
            except KeyError:
                valid = [e.name for e in RenderingMode]
                raise ValueError(f"Invalid rendering mode {v!r}. Valid values: {valid}")
        return v

    @field_validator("host")
    @classmethod
    def check_host(cls, v):
        """Validate the host address."""
        if not validate_host(v):
            raise ValueError("Invalid host address")
        return v

class StartProps(BaseModel):
    """Properties for starting the visualizer instance."""
    file_path: str | None = Field(None, description="Path to the input file", examples=["path/to/file.vtk"])
    metadata: Metadata | str | None = Field(None, description="Metadata for the visualizer", examples=[{"name": "test_model", "unit": "m"}])
    timeout: int | None = Field(0, description="Timeout in seconds")

class UpdateProps(BaseModel):
    """Input for updating the visualizer instance."""
    file_path: str = Field(..., description="Path to the new input file", examples=["path/to/updated_file.vtk"])
    metadata: Metadata | str | None = Field(None, description="Metadata for the visualizer", examples=[{"name": "updated_model", "unit": "m"}])

class RemoveDatasetProps(BaseModel):
    """Input for removing a dataset from the visualizer instance."""
    dataset_id: int = Field(..., description="ID of the dataset to remove", examples=[12345])

class UpdateVariableInfo(BaseModel):
    """Input for updating a variable in the visualizer instance."""
    name: str = Field(..., description="Name of the variable to update", examples=["temperature"])
    type: str = Field(..., description="Type of the variable (point/cell)", examples=["point"])
    num_components: int = Field(..., description="Number of components", examples=[1])
    data: list[float] = Field(..., description="Data array for the variable", examples=[[0.0, 1.0, 2.0, 3.0]])
    part_id: int | None = Field(
        None,
        description=(
            "Part ID targeting a specific leaf block in a multiblock dataset. "
            "Obtain valid part_id values from the list_variables endpoint. "
            "For composite (multiblock) datasets: if set, the update is applied only to that part. "
            "If omitted (null/None), the update is broadcast to every part where the variable "
            "exists and the data length matches — parts that do not satisfy both conditions are "
            "skipped with a warning. "
            "For single-block datasets this field is ignored."
        ),
        examples=[1234567890123456],
    )

class UpdateVariableProps(BaseModel):
    """Input for updating a variable in the visualizer instance."""
    variables: list[UpdateVariableInfo] = Field(..., description="List of variables to update")

class UpdateVariableBinaryInfo(BaseModel):
    """Metadata for one variable whose values travel in a separate binary part."""
    name: str = Field(..., description="Name of the variable to update", examples=["temperature"])
    type: str = Field(..., description="Type of the variable (point/cell)", examples=["point"])
    num_components: int = Field(..., description="Number of components", examples=[1])
    part_id: int | None = Field(
        None,
        description=(
            "Part ID targeting a specific leaf block in a multiblock dataset; "
            "same semantics as part_id on the JSON update_variables endpoint."
        ),
        examples=[1234567890123456],
    )

    def to_update_dict(self, payload: bytes) -> dict[str, Any]:
        """Returns the update dict with payload decoded as little-endian float32, shaped (n, num_components)."""
        bytes_per_tuple = 4 * self.num_components
        if self.num_components <= 0 or len(payload) % bytes_per_tuple != 0:
            raise ValueError(
                f"Payload for variable '{self.name}' is {len(payload)} bytes, which is not a "
                f"multiple of {bytes_per_tuple} (float32 x {self.num_components} components)."
            )
        data = np.frombuffer(payload, dtype="<f4").reshape(-1, self.num_components)
        return {
            "name": self.name,
            "type": self.type,
            "num_components": self.num_components,
            "part_id": self.part_id,
            "data": data,
        }

class UpdateVariableBinaryProps(BaseModel):
    """Metadata for a batch of binary variable updates, in the order of the uploaded parts."""
    variables: list[UpdateVariableBinaryInfo] = Field(
        ..., description="Variable metadata, one entry per binary part, in part order"
    )

    def to_update_dicts(self, payloads: list[bytes]) -> list[dict[str, Any]]:
        """Pairs each metadata entry with its payload by position; raises ValueError on count mismatch."""
        if len(payloads) != len(self.variables):
            raise ValueError(
                f"Received {len(payloads)} binary parts for {len(self.variables)} variables."
            )
        return [info.to_update_dict(payload) for info, payload in zip(self.variables, payloads)]

class SaveStateProps(BaseModel):
    """Input for saving the current state of the visualizer instance."""
    state_dir: str = Field(..., description="Path to directory to save the state", examples=["path/to/state_dir"])

class LoadStateProps(BaseModel):
    """Input for loading a saved state into the visualizer instance."""
    state_dir: str = Field(..., description="Path to directory to load the state from", examples=["path/to/state_dir"])
