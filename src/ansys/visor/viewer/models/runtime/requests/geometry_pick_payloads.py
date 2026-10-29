"""Models for the geometry-pick trigger payloads."""

from pydantic import BaseModel

from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPickMode


class PickGeometryAtPayload(BaseModel):
    """pick_geometry_at payload: a render-window pixel, origin bottom-left, and the mode."""

    x: int
    y: int
    mode: GeometryPickMode
