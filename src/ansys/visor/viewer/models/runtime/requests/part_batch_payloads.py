"""Models for the batched per-part trigger payloads.

A batch carries one absolute target value per part, so the server applies the
whole batch in one critical section and presents it in one frame.  One element
that does not validate rejects the whole batch.
"""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class PartSelection(BaseModel):
    """One part's target selection state within a ``set_parts_selected`` batch."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: int = Field(alias="nodeId")
    selected: bool


class SetPartsSelectedPayload(BaseModel):
    """
    Payload of the ``set_parts_selected`` trigger.

    No colour crosses this trigger: the server reads each part's stored
    diffuse colour from its own record.
    """

    model_config = ConfigDict(populate_by_name=True)

    parts: List[PartSelection]


class PartVisibility(BaseModel):
    """One part's target visibility within a ``set_parts_visibility`` batch."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: int = Field(alias="nodeId")
    visible: bool


class SetPartsVisibilityPayload(BaseModel):
    """Payload of the ``set_parts_visibility`` trigger."""

    model_config = ConfigDict(populate_by_name=True)

    parts: List[PartVisibility]
