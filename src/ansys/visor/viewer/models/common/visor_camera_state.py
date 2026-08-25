"""Model for camera state in a Visor visualization."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class VisorCameraState(BaseModel):
    """
    Represents the camera settings in a Visor visualization.
    """
    model_config = ConfigDict(populate_by_name=True)

    position: List[float]
    focal_point: List[float] = Field(alias="focalPoint")
    view_up: List[float] = Field(alias="viewUp")
    clipping_range: List[float] = Field(alias="clippingRange")
    parallel_projection: bool = Field(alias="parallelProjection")
    view_angle: float = Field(alias="viewAngle")
    parallel_scale: float = Field(alias="parallelScale")
