"""Server-owned record for one color variable across every dataset in the scene."""

from typing import Dict, List, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.scene.persisted_scene_state import _IDENTIFIER_SEPARATOR


def compose_variable_identifier(type: VisorVtkVariableType, name: str, num_components: int) -> str:
    """Compose the stable variable identifier ``<type>::<name>::<num_components>``.

    The inverse of :func:`derive_variable_fields_from_identifier`, and the same
    composition the client uses, so identifiers in existing files key identically.
    """
    return f"{type.value}{_IDENTIFIER_SEPARATOR}{name}{_IDENTIFIER_SEPARATOR}{num_components}"


class VisorVariableRecord(BaseModel):
    """
    The server's record of one variable, keyed by its composed identifier.

    Every field is required: a record never carries an unset range.  ``magnitude_range``
    and ``ranges`` are the custom (effective) ranges; ``default_magnitude_range`` and
    ``default_ranges`` are the ranges widened across every participating part.
    ``part_ids`` lists the parts that carry the variable.

    The identity and range fields share their attribute names and aliases with
    :class:`VisorVariableState`, which is the persisted projection (:meth:`to_variable_state`).
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(...)
    array_name: str = Field(..., alias="arrayName")
    type: VisorVtkVariableType = Field(...)
    num_components: int = Field(..., alias="numComponents")
    part_ids: List[int] = Field(..., alias="partIds")
    default_magnitude_range: Tuple[float, float] = Field(..., alias="defaultMagnitudeRange")
    default_ranges: List[Tuple[float, float]] = Field(..., alias="defaultRanges")
    magnitude_range: Tuple[float, float] = Field(..., alias="magnitudeRange")
    ranges: List[Tuple[float, float]] = Field(...)

    @field_serializer("type")
    def _serialize_type(self, value: VisorVtkVariableType) -> str:
        """Emit the wire value (e.g. "POINT"/"CELL") for both dict-mode and JSON-mode dumps."""
        return value.value

    def to_variable_state(self) -> VisorVariableState:
        """Project the record onto the persisted entry: identity plus the effective ranges."""
        return VisorVariableState(
            id=self.id,
            array_name=self.array_name,
            type=self.type,
            num_components=self.num_components,
            magnitude_range=self.magnitude_range,
            ranges=list(self.ranges),
        )


class VisorVariableRecords(BaseModel):
    """Holder for the scene's variable records, keyed by identifier.

    Created once by the scene and never rebound.  Writers assign a new dict to
    ``variables`` (copy-on-write); readers are handed ``model_copy(deep=True)``.
    """
    variables: Dict[str, VisorVariableRecord] = Field(default_factory=dict)

