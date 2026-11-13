"""Models for the geometry-pick trigger payloads."""

from typing import Annotated

from pydantic import BaseModel, Field

from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick, GeometryPickMode


class PickGeometryAtPayload(BaseModel):
    """pick_geometry_at payload: a render-window pixel, origin bottom-left, and the mode."""

    x: int
    y: int
    mode: GeometryPickMode


class PickGeometryInViewPayload(BaseModel):
    """pick_geometry_in_view payload: a pixel of the client's window, origin bottom-left, the window's size, its camera record, and the mode."""

    x: int
    y: int
    width: Annotated[int, Field(gt=0)]
    height: Annotated[int, Field(gt=0)]
    mode: GeometryPickMode
    camera: VisorCameraState


class SetGeometryHighlightPayload(BaseModel):
    """set_geometry_highlight payload: the pick whose feature to highlight; a not-found pick clears it."""

    pick: GeometryPick
