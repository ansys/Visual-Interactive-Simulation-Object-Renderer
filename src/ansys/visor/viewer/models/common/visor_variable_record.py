"""Server-owned record for one color variable across every dataset in the scene."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState
from ansys.visor.viewer.models.persist.scene.persisted_scene_state import _IDENTIFIER_SEPARATOR

if TYPE_CHECKING:
    from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry
    from ansys.visor.viewer.vtk.variables.visor_variables import VisorVariable

logger = VisorDefaultLogger(__name__)

Range = Tuple[float, float]


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

    def range_for(self, component: int) -> Range | None:
        """Return the effective range for a slot: ``-1`` is magnitude, ``0..n-1`` a component, else None."""
        if component == -1:
            return self.magnitude_range
        if 0 <= component < self.num_components and component < len(self.ranges):
            return self.ranges[component]
        return None


@dataclass
class _VariableAccumulator:
    """Participation and widened default ranges for one (association, name, width) key."""

    variable_type: VisorVtkVariableType
    name: str
    num_components: int
    part_ids: List[int] = field(default_factory=list, init=False)
    magnitude: Range | None = field(default=None, init=False)
    components: List[Range | None] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Start with one empty default slot per component."""
        self.components = [None] * self.num_components

    @staticmethod
    def _widen(current: Range | None, other: Range | None) -> Range | None:
        """Return the union of two ranges; ``None`` contributes nothing."""
        if other is None:
            return current
        other = (float(other[0]), float(other[1]))
        if current is None:
            return other
        return (min(current[0], other[0]), max(current[1], other[1]))

    @staticmethod
    def _follow_or_keep(previous_custom: Range, previous_default: Range, new_default: Range) -> Range:
        """A custom slot equal to its previous default follows the new default; otherwise it is kept."""
        if tuple(previous_custom) == tuple(previous_default):
            return new_default
        return tuple(previous_custom)

    @property
    def variable_id(self) -> str:
        """The composed identifier for this key: the one compose_variable_identifier call site."""
        return compose_variable_identifier(self.variable_type, self.name, self.num_components)

    def add_part(self, part_id: int, variable: "VisorVariable") -> None:
        """Record the part's participation and widen the default ranges with its variable's ranges."""
        if part_id not in self.part_ids:
            self.part_ids.append(part_id)

        variable_magnitude = variable.magnitude_range
        if variable_magnitude is None and self.num_components == 1 and variable.ranges:
            variable_magnitude = variable.ranges[0]
        self.magnitude = self._widen(self.magnitude, variable_magnitude)

        for k in range(min(self.num_components, len(variable.ranges))):
            self.components[k] = self._widen(self.components[k], variable.ranges[k])

    def to_record(self, previous_record: VisorVariableRecord | None) -> VisorVariableRecord:
        """Build the record, carrying each custom slot from ``previous_record`` by the D3 rule."""
        n = self.num_components
        default_magnitude = self.magnitude or (0.0, 0.0)
        default_ranges = [slot if slot is not None else (0.0, 0.0) for slot in self.components]

        custom_magnitude = default_magnitude
        custom_ranges = list(default_ranges)
        old = previous_record
        if old is not None:
            custom_magnitude = self._follow_or_keep(old.magnitude_range, old.default_magnitude_range, default_magnitude)
            custom_ranges = [
                self._follow_or_keep(old.ranges[k], old.default_ranges[k], default_ranges[k])
                if k < len(old.ranges) and k < len(old.default_ranges) else default_ranges[k]
                for k in range(n)
            ]

        return VisorVariableRecord(
            id=self.variable_id,
            array_name=self.name,
            type=self.variable_type,
            num_components=n,
            part_ids=sorted(self.part_ids),
            default_magnitude_range=default_magnitude,
            default_ranges=default_ranges,
            magnitude_range=custom_magnitude,
            ranges=custom_ranges,
        )


class VisorVariableRecords(BaseModel):
    """Holder for the scene's variable records, keyed by identifier.

    Created once by the scene and never rebound.  Writers assign a new dict to
    ``variables`` (copy-on-write); readers are handed ``model_copy(deep=True)``.
    """
    variables: Dict[str, VisorVariableRecord] = Field(default_factory=dict)

    @classmethod
    def from_registry(
            cls,
            registry: "VisorDatasetRegistry",
            previous: "VisorVariableRecords",
    ) -> "VisorVariableRecords":
        """Build a new holder from the registry's per-part variables, carrying custom ranges from ``previous``.

        1. Union: each part carrying a variable joins that identifier's ``part_ids``.
        2. Widen: default ranges are the min of the mins and the max of the maxes.
        3. Custom: an existing id keeps an edited custom slot; an unedited slot (equal to the
           previous default) follows the new default.  A new id starts with custom equal to default.

        ``previous`` is never mutated.
        """
        accumulators: Dict[tuple, _VariableAccumulator] = {}
        for dataset in list(registry.datasets.values()):
            for part_variables in dataset.list_variables():
                for variable in part_variables.variables:
                    key = (variable.type, variable.name, int(variable.num_components))
                    if key not in accumulators:
                        accumulators[key] = _VariableAccumulator(*key)
                    accumulators[key].add_part(part_variables.part_id, variable)

        variables: Dict[str, VisorVariableRecord] = {}
        for accumulator in accumulators.values():
            variable_id = accumulator.variable_id
            variables[variable_id] = accumulator.to_record(previous.variables.get(variable_id))
        return cls(variables=variables)

    def overlay(self, file_states: Dict[str, VisorVariableState]) -> "VisorVariableRecords":
        """Apply a file's ranges to this fresh build by the D3 load rule and return this holder.

        - A null or absent ``magnitudeRange`` falls back to the default (DEBUG).
        - ``ranges`` whose length differs from ``num_components`` fall back to the default (DEBUG).
        - A file id with no record is dropped (WARNING).

        Assigns a new dict to ``variables``; the previous dict and its entries are never mutated.
        """
        result = dict(self.variables)
        for variable_id, entry in (file_states or {}).items():
            record = result.get(variable_id)
            if record is None:
                logger.warning("persisted variable %s has no record in the scene; dropped", variable_id)
                continue

            magnitude = entry.magnitude_range
            if magnitude is None:
                logger.debug("persisted variable %s has no magnitudeRange; default used", variable_id)
                magnitude = record.default_magnitude_range

            ranges = entry.ranges
            if ranges is None or len(ranges) != record.num_components:
                logger.debug(
                    "persisted variable %s has %s ranges for %d components; default used",
                    variable_id, None if ranges is None else len(ranges), record.num_components,
                )
                ranges = record.default_ranges

            result[variable_id] = record.model_copy(
                update={"magnitude_range": tuple(magnitude), "ranges": [tuple(r) for r in ranges]},
                deep=True,
            )
        self.variables = result
        return self

