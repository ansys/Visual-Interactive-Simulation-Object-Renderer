"""Model for properties on a dataset part in the Visor visualization."""

from typing import List, Optional

from pydantic import BaseModel, Field


class PartProperties(BaseModel):
    """
    Represents properties for a part in the Visor visualization.

    opacity: The opacity of the part, between 0.0 (fully transparent) and 1.0 (fully opaque).
    visible: Whether the part is visible in the scene.
    selected: Whether the part is currently selected by the user.
    color_by: If set, this part's color is determined by the values of the variable with this ID.
    color_by_component: If the variable specified by color_by has multiple components,
       this specifies which component to use for coloring.
    diffuse_rgb: If set, this part's color is determined by the specified RGB values (each between 0 and 1).

    """
    opacity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    visible: Optional[bool] = Field(default=None)
    selected: Optional[bool] = Field(default=None)
    color_by: Optional[str] = Field(default=None)
    color_by_component: Optional[int] = Field(default=None)
    diffuse_rgb: Optional[List[float]] = Field(default=None)
