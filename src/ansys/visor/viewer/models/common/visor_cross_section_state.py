"""Model for cross section widget state in a Visor visualization."""

from typing import List

from pydantic import BaseModel


class VisorCrossSectionState(BaseModel):
    """
    Represents the cross-section widget state in a Visor visualization.
    """
    origin: List[float] | None = None
    normal: List[float] | None = None

