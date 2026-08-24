"""Models for the renderer annotation half of the scene-details payload.

The annotation carries every renderer-specific handle
a client needs in order to bind to the scene description: per-node
handles for registered part nodes, and handles for the renderer's singleton
widgets.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RendererAnnotation(BaseModel):
    """Base for every renderer's annotation.

    Discriminated on the wire by ``rendererKind`` so the client can narrow to a
    concrete type at the parse boundary without a permissive union.
    """
    model_config = ConfigDict(populate_by_name=True)

    renderer_kind: str = Field(alias="rendererKind")


class WasmNodeHandles(BaseModel):
    """Wasm object-manager ids for one renderable part node."""
    model_config = ConfigDict(populate_by_name=True)

    actor_id: int = Field(alias="actorId")
    property_id: int = Field(alias="propertyId")
    mapper_id: int = Field(alias="mapperId")


class WasmWidgetHandles(BaseModel):
    """Wasm object-manager ids for the renderer's singleton widgets.

    Static after renderer initialisation; independent of scene contents.
    """
    model_config = ConfigDict(populate_by_name=True)

    orientation_widget_id: int = Field(alias="orientationWidgetId")
    cross_section_plane_id: int = Field(alias="crossSectionPlaneId")
    cross_section_plane_widget_id: int = Field(alias="crossSectionPlaneWidgetId")
    cross_section_plane_representation_id: int = Field(
        alias="crossSectionPlaneRepresentationId"
    )
    bounding_box_algorithm_id: int = Field(alias="boundingBoxAlgorithmId")
    bounding_box_outline_actor_id: int = Field(alias="boundingBoxOutlineActorId")
    bounding_box_axes_actor_id: int = Field(alias="boundingBoxAxesActorId")


class WasmRendererAnnotation(RendererAnnotation):
    """Annotation produced by :class:`VisorLocalRenderer`."""

    renderer_kind: Literal["wasm"] = Field(default="wasm", alias="rendererKind")
    # Keyed by str(node_id): JSON object keys must be strings.
    # Only part nodes appear. Group and root nodes have no renderable objects.
    nodes: dict[str, WasmNodeHandles] = Field(default_factory=dict)
    widgets: WasmWidgetHandles

