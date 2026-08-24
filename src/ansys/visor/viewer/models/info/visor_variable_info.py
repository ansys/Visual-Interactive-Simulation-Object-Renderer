"""Model for a VTK variable array."""

from typing import List, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType


class VisorVariableInfo(BaseModel):
    """
    Metadata for a VTK variable array.
    Attributes:
        index_for_type (int): Index of the variable within its type (point or cell).
        type (VisorVtkVariableType): Type of the variable (e.g., POINT or CELL).
        name (str): Name of the variable.
        num_components (int): Number of components in the variable array.
        ranges (List[Tuple[float, float]]): List of ranges for each component.
        magnitude_range (Tuple[float, float] | None): Range of magnitudes if applicable.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    index_for_type: int = Field(alias="indexForType")
    type: VisorVtkVariableType
    name: str
    num_components: int = Field(alias="numComponents")
    ranges: List[Tuple[float, float]]
    magnitude_range: Tuple[float, float] | None = Field(default=None, alias="magnitudeRange")

    @field_serializer("type")
    def _serialize_type(self, value: VisorVtkVariableType) -> str:
        """Emit the wire value (e.g. "POINT"/"CELL") for both dict-mode and JSON-mode dumps."""
        return value.value

