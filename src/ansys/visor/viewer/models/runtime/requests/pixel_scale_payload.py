"""Model for the ``set_pixel_scale`` trigger payload."""

from typing import Annotated

from pydantic import BaseModel, Field


class SetPixelScalePayload(BaseModel):
    """set_pixel_scale payload: the client's device pixels per CSS pixel, finite and positive."""

    scale: Annotated[float, Field(gt=0, allow_inf_nan=False)]
