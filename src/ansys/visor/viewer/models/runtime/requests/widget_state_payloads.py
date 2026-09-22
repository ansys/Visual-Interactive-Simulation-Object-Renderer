"""Models for the widget-state trigger payloads.

One model per server-tracked widget toggle, plus the projection.

Projection is not a fourth toggle.  It has no store field on the scene: it
is the camera record's ``parallel_projection``, written through the
renderer and derived back out in ``get_state``, so that the projection has
exactly one source.

These live here rather than inline in ``local_app.py`` beside the six
per-part payload models, whose own block comment scopes itself to
per-part triggers carrying camelCase aliases.  These are neither.  The
precedent is ``sync_camera_payload.py``, the one existing non-per-part
trigger, whose model lives in this package.

``SyncCrossSectionPlanePayload`` is not a toggle either.  It is the plane
the client's drag settled on, reported at end of interaction, and it
carries two three-component vectors rather than a boolean.  It lives here
rather than beside the per-part models for the same reason the four above
do: it is scene-wide and carries no ``nodeId``.
"""

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class SetCrossSectionVisibilityPayload(BaseModel):
    """Payload of the ``set_cross_section_visibility`` trigger."""

    model_config = ConfigDict(populate_by_name=True)

    visible: bool


class SetEdgesVisiblePayload(BaseModel):
    """Payload of the ``set_edges_visible`` trigger."""

    model_config = ConfigDict(populate_by_name=True)

    visible: bool


class SetBoundingBoxVisibilityPayload(BaseModel):
    """Payload of the ``set_bounding_box_visibility`` trigger."""

    model_config = ConfigDict(populate_by_name=True)

    visible: bool


class SetProjectionPayload(BaseModel):
    """Payload of the ``set_projection`` trigger."""

    model_config = ConfigDict(populate_by_name=True)

    parallel: bool


class SyncCrossSectionPlanePayload(BaseModel):
    """Payload of the ``sync_cross_section_plane`` trigger."""

    model_config = ConfigDict(populate_by_name=True)

    origin: List[float] = Field(min_length=3, max_length=3)
    normal: List[float] = Field(min_length=3, max_length=3)

