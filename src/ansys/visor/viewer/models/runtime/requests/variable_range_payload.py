"""Model for the ``set_variable_range`` trigger payload."""

from pydantic import BaseModel, ConfigDict, Field


class SetVariableRangePayload(BaseModel):
    """
    Payload of the ``set_variable_range`` trigger.

    Scene-wide: it names a variable and one of its slots, not a part.
    ``component`` uses the server convention, ``-1`` for magnitude and
    ``0..n-1`` for a component.  Finiteness and ``min <= max`` are checked by
    the coordinator, which refuses with a WARNING, not here.
    """

    model_config = ConfigDict(populate_by_name=True)

    variable_id: str = Field(alias="variableId")
    component: int
    min_val: float = Field(alias="min")
    max_val: float = Field(alias="max")

