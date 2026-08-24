"""Model for metadata for a variable on a dataset part in a Visor visualization."""

from typing import List, Tuple

from pydantic import BaseModel, ConfigDict, Field


class VisorVariableState(BaseModel):
    """
    Represents the state of all Visor variables, currently including the ranges
    for each individual component, and for the magnitude.

    Note: Currently the frontend aggregates global variables across all datasets and dataset parts loaded in the
     scene at a given time.  It generates the ID from three properties that, combined, form
    a unique identifier for the variable: the variable name, type (POINT/CELL), and number of components, and computes
    the ranges across all datasets/parts that contain that variable.

    In the future, the backend can own this, but for now we can treat this as passthrough data,
    as the id value is stable across sessions.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(...)
    magnitude_range: Tuple[float, float] | None = Field(default=None, alias="magnitudeRange")
    ranges: List[Tuple[float, float]] = Field(default_factory=list)
