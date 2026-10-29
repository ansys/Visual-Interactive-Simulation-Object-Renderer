"""Models for the geometry-pick trigger payloads."""

from pydantic import BaseModel

from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick, GeometryPickMode


class PickGeometryAtPayload(BaseModel):
    """pick_geometry_at payload: a render-window pixel, origin bottom-left, and the mode."""

    x: int
    y: int
    mode: GeometryPickMode


class SetGeometryHighlightPayload(BaseModel):
    """set_geometry_highlight payload: the pick whose feature to highlight; a not-found pick clears it."""

    pick: GeometryPick
