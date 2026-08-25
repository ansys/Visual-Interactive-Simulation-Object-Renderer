"""
PartIndex: owns stable runtime part-ID assignment for a dataset.

Built once from a vtkDataObject at add_dataset time.  IDs are seeded from
the scene-graph node IDs (same JavaScript-safe integer convention) so that
part_id == scene-graph node ID -- the contract the frontend relies on to
apply per-part state (opacity, visibility, color) to the right VTK actor.
If no seed is provided for a given name, a fresh random ID is generated as
a fallback.  IDs are session-scoped -- they do not survive a server restart.
The name <-> id bridge exists so that VisorStateMapper can translate between
the runtime layer (IDs) and the persistence layer (names) for
save_state / load_state.
"""
from __future__ import annotations

from dataclasses import dataclass

from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet, vtkDataObject

from ansys.visor.viewer.core.visor_helpers import get_random_javascript_safe_id, is_composite_dataset
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)


@dataclass
class PartEntry:
    """Metadata for a single leaf part inside a dataset."""
    part_id: int       # stable runtime ID, assigned once at load
    name: str          # block name from VTK metadata (or fallback)
    flat_index: int    # ordinal position in the SkipEmptyNodes composite iterator


class PartIndex:
    """
    Builds and owns stable runtime part IDs for a vtkDataObject.

    For non-composite datasets there is exactly one implicit part.
    For composite datasets there is one entry per non-empty leaf block,
    traversed with SkipEmptyNodesOn() so flat_index values are contiguous.

    Contract
    --------
    - part_id values are assigned once and never change for the lifetime
      of the dataset.
    - Part names must be unique within a dataset for save_state / load_state
      round-trips to be reliable (the same constraint already applies to
      dataset names in the registry).
    - Part IDs are NOT stable across server restarts.
    """

    def __init__(self, data: vtkDataObject, dataset_name: str = "", seed_ids: dict[str, int] | None = None):
        self._parts: dict[int, PartEntry] = {}  # part_id -> entry
        self._name_to_id: dict[str, int] = {}
        self._seed_ids: dict[str, int] = seed_ids or {}
        self._build(data, dataset_name)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, data: vtkDataObject, dataset_name: str) -> None:
        """Build the part IDs and names."""
        if not is_composite_dataset(data):
            self._add_entry(name=dataset_name, flat_index=0)
        else:
            composite = data  # type: vtkCompositeDataSet
            it = composite.NewIterator()
            it.SkipEmptyNodesOn()
            flat_idx = 0
            while not it.IsDoneWithTraversal():
                meta = it.GetCurrentMetaData()
                name_key = vtkCompositeDataSet.NAME()
                name = (
                    meta.Get(name_key)
                    if (meta is not None and meta.Has(name_key))
                    else "untitled"
                )
                if name in self._name_to_id:
                    logger.warning(
                        f"Duplicate part name '{name}' detected in dataset. "
                        f"The name→id map will only retain the last part with this name, "
                        f"which means save_state/load_state will be unreliable for these parts. "
                        f"Part IDs remain unique and all runtime operations are unaffected."
                    )
                self._add_entry(name=name, flat_index=flat_idx)
                flat_idx += 1
                it.GoToNextItem()

    def _add_entry(self, name: str, flat_index: int) -> PartEntry:
        """Add a new entry to the part IDs and names."""
        pid = self._seed_ids.get(name) or get_random_javascript_safe_id()
        entry = PartEntry(part_id=pid, name=name, flat_index=flat_index)
        self._parts[pid] = entry
        self._name_to_id[name] = pid  # last writer wins on collision
        return entry


    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_entry(self, part_id: int) -> PartEntry | None:
        """Get the entry corresponding to the given part_id."""
        return self._parts.get(part_id)

    def get_leaf_block(self, part_id: int, data: vtkDataObject) -> vtkDataObject | None:
        """
        Return the leaf vtkDataObject corresponding to *part_id*.

        For a non-composite dataset the data object itself is returned.
        For composite datasets the iterator is advanced to the correct
        flat_index (SkipEmptyNodesOn, matching build order).
        """
        entry = self._parts.get(part_id)
        if entry is None:
            logger.warning(f"part_id {part_id} not found in PartIndex.")
            return None

        if not is_composite_dataset(data):
            return data

        composite = data  # type: vtkCompositeDataSet
        it = composite.NewIterator()
        it.SkipEmptyNodesOn()
        for _ in range(entry.flat_index):
            it.GoToNextItem()
        return it.GetCurrentDataObject()

    # ------------------------------------------------------------------
    # Maps (used by VisorStateMapper for runtime <-> persisted translation)
    # ------------------------------------------------------------------

    @property
    def name_to_id_map(self) -> dict[str, int]:
        """Return a dictionary that maps part IDs to ids."""
        return dict(self._name_to_id)

    @property
    def id_to_name_map(self) -> dict[int, str]:
        """Return a dictionary that maps part IDs to names."""
        return {e.part_id: e.name for e in self._parts.values()}

    @property
    def part_ids(self) -> list[int]:
        """Return a list of all part IDs."""
        return list(self._parts.keys())

    def list_parts(self) -> list[dict]:
        """Return a list containing each part's ID and name."""
        return [{"part_id": e.part_id, "name": e.name} for e in self._parts.values()]

