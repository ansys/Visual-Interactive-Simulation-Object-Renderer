"""Model for runtime dataset state serialization."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

from ansys.visor.viewer.models.common.part_properties import PartProperties


class RuntimePartProperties(BaseModel):
    """
    Frontend-facing model of part properties for runtime state serialization.

    This class mirrors the fields of ``PartProperties`` using snake_case Python
    attribute names, but serializes with camelCase aliases (``variableId``,
    ``variableComponent``, ``diffuseRgb``) for parity with the frontend wire
    format.  Callers must pass ``by_alias=True`` when dumping (e.g., in
    ``get_scene_details_json``) so the emitted keys stay camelCase.

    Serialization semantics (aligned with the frontend state model):

    - ``variableId`` is **always included** in the serialized output, even when
      ``None``.  On the frontend, ``null`` means "no variable applied" (a real
      value), while an absent key means "leave this property unchanged".
    - All other optional fields (``opacity``, ``visible``, ``selected``,
      ``variableComponent``, ``diffuseRgb``) are **omitted from the serialized
      output when ``None``**, so that the frontend treats them as pass-through
      / unchanged.

    id: int
    opacity: Optional[float]: The opacity of the part, between 0.0 (fully transparent) and 1.0 (fully opaque).
    visible: Optional[bool]: Whether the part is visible in the scene.
    selected: Optional[bool]: Whether the part is currently selected by the user.
    variable_id: Optional[str]: The ID of the variable used to colour this part,
        or ``None`` to indicate that no variable is applied.  Always serialized.
    variable_component: Optional[int]: If the variable specified by variable_id has multiple components,
        this specifies which component to use for coloring.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: int
    opacity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    visible: Optional[bool] = Field(default=None)
    selected: Optional[bool] = Field(default=None)

    # variable_id=None means "no variable applied" — a real, meaningful value.
    # It is always included in serialized output so the frontend can act on it.
    variable_id: Optional[str] = Field(default=None, alias="variableId")
    # If the variable with ID variable_id has multiple components, this specifies which component to use for coloring.
    variable_component: Optional[int] = Field(default=None, alias="variableComponent")

    # If set, this part's color is determined by the specified RGB values (each between 0 and 1).
    diffuse_rgb: Optional[List[float]] = Field(default=None, alias="diffuseRgb")

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any, info: Any = None) -> dict:
        """Custom serializer that implements the frontend undefined-vs-null contract.

        ``variableId`` is always present in the output (``null`` is meaningful).
        All other optional fields are omitted when their value is ``None``, so
        the frontend interprets them as pass-through / undefined.

        The set of "omit-when-None" keys is checked against **both** the
        snake_case attribute names and their camelCase aliases so this works
        regardless of whether the caller uses ``by_alias=True``.
        """
        data: dict = handler(self)
        keys_to_omit_when_none = {
            "opacity", "visible", "selected",
            "variable_component", "variableComponent",
            "diffuse_rgb", "diffuseRgb",
        }
        return {k: v for k, v in data.items() if not (k in keys_to_omit_when_none and v is None)}

    def to_part_properties(self) -> PartProperties:
        return PartProperties(
            opacity=self.opacity,
            visible=self.visible,
            selected=self.selected,
            color_by=self.variable_id,
            color_by_component=self.variable_component,
            diffuse_rgb=self.diffuse_rgb,
        )

    @classmethod
    def from_part_properties(cls, id: int, props: PartProperties) -> "RuntimePartProperties":
        return cls(
            id=id,
            opacity=props.opacity,
            visible=props.visible,
            selected=props.selected,
            variable_id=props.color_by,
            variable_component=props.color_by_component,
            diffuse_rgb=props.diffuse_rgb,
        )


class RuntimeDatasetState(BaseModel):
    """
    Represents the runtime, in-memory state of a Visor visualization,
    including properties for individual parts.

    The part dictionary is keyed by internal dataset IDs.

    This class is for serialization of the runtime state that is sent
    to the frontend viewer.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: int
    part_states: Dict[int, "RuntimePartProperties"] = Field(default_factory=dict, alias="partStates")

    @field_validator("part_states", mode="before")
    @classmethod
    def _coerce_part_states(cls, v: Any) -> Any:
        if v is None:
            return {}

        # Common case: JSON object -> dict with string keys
        if isinstance(v, dict):
            out: Dict[int, Any] = {}
            for k, val in v.items():
                try:
                    ik = int(k)
                except (TypeError, ValueError):
                    ik = k  # type: ignore[assignment]
                out[ik] = val
            return out

        return v

    @classmethod
    def from_components(
            cls,
            id: int,
            part_states: Dict[int, PartProperties],
    ) -> "RuntimeDatasetState":
        runtime_part_states = {
            part_id: RuntimePartProperties.from_part_properties(id=part_id, props=props) \
            for part_id, props in part_states.items()
        }
        return cls(
            id=id,
            part_states=runtime_part_states,
        )
