"""Model for runtime dataset state serialization."""

from typing import Any, Dict, List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
)

from ansys.visor.viewer.core.visor_colors import VisorPartDefaults
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.part_properties import PartProperties

logger = VisorDefaultLogger(__name__)


class VariableReference(BaseModel):
    """The variable and component a part is coloured by."""
    model_config = ConfigDict(populate_by_name=True)

    variable_id: str = Field(alias="variableId")
    variable_component: int = Field(alias="variableComponent")


class RuntimePartProperties(BaseModel):
    """
    Frontend-facing record of one part's properties, every field resolved.

    No field holds ``None`` except ``color_variable``, whose ``None`` is the
    resolved value "not coloured by a variable".

    The wire carries the reference flat, as ``variableId`` and
    ``variableComponent``.  With no reference, ``variableId`` is ``null`` and
    ``variableComponent`` is absent; under ``exclude_none`` ``variableId`` is
    absent too.  Callers pass ``by_alias=True`` so the keys stay camelCase.

    id: The part's scene-graph node ID.
    opacity: Between 0.0 (fully transparent) and 1.0 (fully opaque).
    visible: Whether the part is visible in the scene.
    selected: Whether the part is selected by the user.
    diffuse_rgb: The part's diffuse colour, each channel between 0 and 1.
    color_variable: The variable the part is coloured by, or ``None``.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: int
    opacity: float = Field(ge=0.0, le=1.0)
    visible: bool
    selected: bool
    diffuse_rgb: List[float] = Field(alias="diffuseRgb")
    color_variable: VariableReference | None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> dict:
        """Emit the reference flat as variableId/variableComponent; with none, variableId is null unless
        exclude_none."""
        data: dict = handler(self)
        data.pop("color_variable", None)
        id_key = "variableId" if info.by_alias else "variable_id"
        component_key = "variableComponent" if info.by_alias else "variable_component"
        reference = self.color_variable
        if reference is not None:
            data[id_key] = reference.variable_id
            data[component_key] = reference.variable_component
        elif not info.exclude_none:
            data[id_key] = None
        return data

    @classmethod
    def default_for(cls, part_id: int) -> "RuntimePartProperties":
        """The record of a part none of whose properties has been set."""
        return cls(
            id=part_id,
            opacity=VisorPartDefaults.Opacity,
            visible=VisorPartDefaults.Visible,
            selected=VisorPartDefaults.Selected,
            diffuse_rgb=list(VisorPartDefaults.DiffuseRgb),
            color_variable=None,
        )

    def to_part_properties(self) -> PartProperties:
        """The persisted entry for this record; the reference maps back to color_by/color_by_component."""
        reference = self.color_variable
        return PartProperties(
            opacity=self.opacity,
            visible=self.visible,
            selected=self.selected,
            color_by=reference.variable_id if reference is not None else None,
            color_by_component=reference.variable_component if reference is not None else None,
            diffuse_rgb=self.diffuse_rgb,
        )

    @classmethod
    def from_part_properties(cls, id: int, props: PartProperties) -> "RuntimePartProperties":
        """Resolve a persisted entry: a null field takes its default, color_by/color_by_component become the
        reference.

        A reference with only one of its two halves resolves to ``None`` and
        logs one WARNING.
        """
        return cls(
            id=id,
            opacity=props.opacity if props.opacity is not None else VisorPartDefaults.Opacity,
            visible=props.visible if props.visible is not None else VisorPartDefaults.Visible,
            selected=props.selected if props.selected is not None else VisorPartDefaults.Selected,
            diffuse_rgb=(
                props.diffuse_rgb if props.diffuse_rgb is not None else list(VisorPartDefaults.DiffuseRgb)
            ),
            color_variable=cls._resolve_color_variable(id, props),
        )

    @staticmethod
    def _resolve_color_variable(part_id: int, props: PartProperties) -> VariableReference | None:
        """The reference a persisted entry names, or None when it names none or only half of one."""
        if props.color_by is not None and props.color_by_component is not None:
            return VariableReference(variable_id=props.color_by, variable_component=props.color_by_component)
        if props.color_by is not None or props.color_by_component is not None:
            logger.warning(
                "part %s stores color_by %r with color_by_component %r; resolved as not coloured.",
                part_id, props.color_by, props.color_by_component
            )
        return None


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
