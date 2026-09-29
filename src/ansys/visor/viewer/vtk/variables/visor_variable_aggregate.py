"""Pure aggregation of the scene's variable records from the dataset registry."""

from typing import TYPE_CHECKING, Dict, List, Tuple

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.common.visor_variable_record import (
    VisorVariableRecord,
    compose_variable_identifier,
)
from ansys.visor.viewer.models.common.visor_variable_state import VisorVariableState

if TYPE_CHECKING:
    from ansys.visor.viewer.vtk.datasets.visor_dataset_registry import VisorDatasetRegistry

logger = VisorDefaultLogger(__name__)

Range = Tuple[float, float]


def _widen(current: Range | None, other: Range | None) -> Range | None:
    """Return the union of two ranges; ``None`` contributes nothing."""
    if other is None:
        return current
    other = (float(other[0]), float(other[1]))
    if current is None:
        return other
    return (min(current[0], other[0]), max(current[1], other[1]))


def _follow_or_keep(previous_custom: Range, previous_default: Range, new_default: Range) -> Range:
    """A custom slot equal to its previous default follows the new default; otherwise it is kept."""
    if tuple(previous_custom) == tuple(previous_default):
        return new_default
    return tuple(previous_custom)


def build_variable_records(
        registry: "VisorDatasetRegistry",
        previous: Dict[str, VisorVariableRecord],
) -> Dict[str, VisorVariableRecord]:
    """Build the records from every dataset's variables, carrying custom ranges from ``previous``.

    1. Union: each part carrying a variable joins that identifier's ``part_ids``.
    2. Widen: default ranges are the min of the mins and the max of the maxes.
    3. Custom: an existing id keeps an edited custom slot; an unedited slot (equal to the
       previous default) follows the new default.  A new id starts with custom equal to default.

    Returns a new dict of new records; ``previous`` is never mutated.
    """
    parts: Dict[str, List[int]] = {}
    identity: Dict[str, tuple] = {}
    magnitude: Dict[str, Range | None] = {}
    components: Dict[str, List[Range | None]] = {}

    for dataset in list(registry.datasets.values()):
        for part_variables in dataset.list_variables():
            for variable in part_variables.variables:
                n = int(variable.num_components)
                variable_id = compose_variable_identifier(variable.type, variable.name, n)
                if variable_id not in identity:
                    identity[variable_id] = (variable.name, variable.type, n)
                    parts[variable_id] = []
                    magnitude[variable_id] = None
                    components[variable_id] = [None] * n
                if part_variables.part_id not in parts[variable_id]:
                    parts[variable_id].append(part_variables.part_id)

                variable_magnitude = variable.magnitude_range
                if variable_magnitude is None and n == 1 and variable.ranges:
                    variable_magnitude = variable.ranges[0]
                magnitude[variable_id] = _widen(magnitude[variable_id], variable_magnitude)

                slots = components[variable_id]
                for k in range(min(n, len(variable.ranges))):
                    slots[k] = _widen(slots[k], variable.ranges[k])

    records: Dict[str, VisorVariableRecord] = {}
    for variable_id, (name, variable_type, n) in identity.items():
        default_magnitude = magnitude[variable_id] or (0.0, 0.0)
        default_ranges = [slot if slot is not None else (0.0, 0.0) for slot in components[variable_id]]

        custom_magnitude = default_magnitude
        custom_ranges = list(default_ranges)
        old = previous.get(variable_id)
        if old is not None:
            custom_magnitude = _follow_or_keep(old.magnitude_range, old.default_magnitude_range, default_magnitude)
            custom_ranges = [
                _follow_or_keep(old.ranges[k], old.default_ranges[k], default_ranges[k])
                if k < len(old.ranges) and k < len(old.default_ranges) else default_ranges[k]
                for k in range(n)
            ]

        records[variable_id] = VisorVariableRecord(
            id=variable_id,
            array_name=name,
            type=variable_type,
            num_components=n,
            part_ids=sorted(parts[variable_id]),
            default_magnitude_range=default_magnitude,
            default_ranges=default_ranges,
            magnitude_range=custom_magnitude,
            ranges=custom_ranges,
        )
    return records


def overlay_persisted_ranges(
        records: Dict[str, VisorVariableRecord],
        persisted: Dict[str, VisorVariableState],
) -> Dict[str, VisorVariableRecord]:
    """Overlay the file's custom ranges onto freshly built records.

    - A null or absent ``magnitudeRange`` falls back to the default (DEBUG).
    - ``ranges`` whose length differs from ``num_components`` fall back to the default (DEBUG).
    - A file id with no record is dropped (WARNING).

    Returns a new dict; ``records`` is never mutated.
    """
    result = dict(records)
    for variable_id, entry in (persisted or {}).items():
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
    return result


def resolve_record_range(record: VisorVariableRecord, component: int) -> Range | None:
    """Return the effective range for a component slot: ``-1`` is magnitude, ``0..n-1`` a component."""
    if component == -1:
        return record.magnitude_range
    if 0 <= component < record.num_components and component < len(record.ranges):
        return record.ranges[component]
    return None

