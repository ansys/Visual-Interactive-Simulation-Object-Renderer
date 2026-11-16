"""
ParaviewRenderer
================
:class:`IRenderer` over a ParaView render view on pvserver.

Each opened dataset is one pvserver source shown by one representation,
written through a :class:`ParaviewSession`.  Like :class:`ServerRenderer`, it
never renders on the calling thread: every write ends in a frame request, and
only the capture renders.  Each camera write also hands the record to a
:class:`ViewRecordPublisher`.

A non-composite dataset is one part, written through its representation's
properties.  Each leaf of a composite dataset is one part, written through the
representation's per-block properties under the leaf's selector.  Those
per-block lists, and the source's block selection, are written at the next
frame, once each, however many parts changed since the last one; the capture
calls :meth:`ParaviewRenderer.flush_writes` before it renders.  Parts
coloured by a variable share one colour map per :class:`ColorMapKey`, and at
most :data:`MAX_COLOR_MAPS` maps are in use at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet, vtkDataAssembly, vtkDataAssemblyUtilities

from ansys.visor.viewer.core.errors import VisorAddDatasetError
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_helpers import is_composite_dataset
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.renderer.base import IRenderer

if TYPE_CHECKING:
    from collections.abc import Callable

    from vtkmodules.vtkCommonDataModel import vtkDataObject, vtkDataObjectTree
    from vtkmodules.vtkRenderingCore import vtkRenderWindow

    from ansys.visor.viewer.core.visor_types import VisorDatasetType
    from ansys.visor.viewer.models.common.visor_camera_state import VisorCameraState
    from ansys.visor.viewer.models.runtime.picking.geometry_pick import GeometryPick
    from ansys.visor.viewer.renderer.paraview_session import (
        ParaviewSession,
        PvLookupTable,
        PvRepresentation,
        PvSource,
    )
    from ansys.visor.viewer.renderer.streamed_protocols import FrameRequester, ViewRecordPublisher
    from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphPartNode

logger = VisorDefaultLogger(__name__)

SELECTED_AMBIENT_RGB: tuple[float, float, float] = (0 / 255, 62 / 255, 111 / 255)
"""Ambient tint of a selected part, as the VTK pipeline applies it; also the colour of a selected block."""

SELECTED_BLOCK_OPACITY: float = 1.0
"""Opacity of a selected block's wireframe outline."""

MAX_COLOR_MAPS: int = 30
"""Colour maps in use at once, across every representation; more exceed the texture units of the GPU."""

_ASSOCIATIONS: dict[VisorVtkVariableType, str] = {
    VisorVtkVariableType.POINT: "POINTS",
    VisorVtkVariableType.CELL: "CELLS",
}

# Field association codes ParaView reads in the per-block colour-array list.
_BLOCK_ASSOCIATIONS: dict[str, str] = {"POINTS": "0", "CELLS": "1"}


@dataclass(frozen=True)
class ColorMapKey:
    """Every lookup-table field Visor stores for a part; parts with equal keys share one colour map.

    *association* is ``"POINTS"`` or ``"CELLS"``; *component* ``-1`` is the
    magnitude; *min_val* and *max_val* are the map's range.
    """

    association: str
    array_name: str
    component: int
    min_val: float
    max_val: float


@dataclass
class _ColorMap:
    """One shared colour map and the number of parts using it."""

    lut: PvLookupTable
    users: int


class _ColorMaps:
    """The colour maps in use across every representation, one per key, counted by the parts using them.

    A map is never changed once a part uses it: a part whose key changes
    moves to the map for its new key.  A map no part uses stops counting at
    once and is deleted by :meth:`delete_retired`, which runs after the
    per-block lists that named it are rewritten.
    """

    def __init__(self, session: ParaviewSession) -> None:
        """Hold no maps."""
        self._session = session
        self._maps: dict[ColorMapKey, _ColorMap] = {}
        self._retired: list[PvLookupTable] = []

    def acquire(self, key: ColorMapKey, releasing: ColorMapKey | None) -> PvLookupTable | None:
        """The map for key, with one more user; None when a new map would exceed :data:`MAX_COLOR_MAPS`.

        *releasing* is the key the caller releases once it has moved to the
        returned map; a map only the caller uses does not count against the
        limit.  A new map is created and given its range here, before any
        part uses it.
        """
        shared = self._maps.get(key)
        if shared is not None:
            shared.users += 1
            return shared.lut
        in_use = len(self._maps)
        if releasing is not None and self._maps[releasing].users == 1:
            in_use -= 1
        if in_use >= MAX_COLOR_MAPS:
            return None
        lut = self._session.new_color_map(key.component)
        self._session.rescale_color_map(lut, key.min_val, key.max_val)
        self._maps[key] = _ColorMap(lut, 1)
        return lut

    def release(self, key: ColorMapKey) -> None:
        """Drop one user of key's map; a map no part uses is retired, to be deleted by delete_retired."""
        shared = self._maps[key]
        shared.users -= 1
        if shared.users == 0:
            del self._maps[key]
            self._retired.append(shared.lut)

    def delete_retired(self) -> None:
        """Delete every retired map; the caller has rewritten every list that named one."""
        retired, self._retired = self._retired, []
        for lut in retired:
            self._session.delete_color_map(lut)

    def release_all(self) -> None:
        """Delete every map, retired or in use."""
        for shared in self._maps.values():
            self._session.delete_color_map(shared.lut)
        self._maps.clear()
        self.delete_retired()


@dataclass
class _BlockEntry:
    """What one block shows; None leaves the representation's value in force."""

    visible: bool = True
    opacity: float | None = None
    rgb: list[float] | None = None
    color: tuple[ColorMapKey, PvLookupTable] | None = None


class BlockTable:
    """The registered blocks of one composite representation, written as its per-block property lists.

    Each list is written whole, in registration order, from the entries;
    values are strings, as ParaView stores them.  A block not in the table is
    hidden.  Changes only mark their lists stale; :meth:`flush` writes each
    stale list, and the source's block selection, once.
    """

    def __init__(self, session: ParaviewSession, source: PvSource, rep: PvRepresentation) -> None:
        """Hold no blocks, so none is shown; selected blocks are outlined in the opaque selection colour."""
        self._session = session
        self._source = source
        self._rep = rep
        self._entries: dict[str, _BlockEntry] = {}
        self._selected: set[str] = set()
        self._stale: set[Callable[[], None]] = set()
        self._write_visible()
        session.set_property(rep, "SelectionColor", list(SELECTED_AMBIENT_RGB))
        session.set_property(rep, "SelectionOpacity", SELECTED_BLOCK_OPACITY)

    def flush(self) -> None:
        """Write every stale list once."""
        stale, self._stale = self._stale, set()
        for write in (
            self._write_visible,
            self._write_opacities,
            self._write_colors,
            self._write_color_maps,
            self._write_selected,
        ):
            if write in stale:
                write()

    def add(self, selector: str) -> None:
        """Show the block at selector."""
        self._entries[selector] = _BlockEntry()
        self._stale.add(self._write_visible)

    def remove(self, selector: str) -> None:
        """Hide the block at selector and drop every value written for it."""
        self._entries.pop(selector)
        self._stale.update((self._write_visible, self._write_opacities, self._write_colors, self._write_color_maps))
        if selector in self._selected:
            self._selected.discard(selector)
            self._stale.add(self._write_selected)

    def set_visible(self, selector: str, visible: bool) -> None:
        """Show or hide the block, and its selection with it."""
        self._entries[selector].visible = visible
        self._stale.add(self._write_visible)
        if selector in self._selected:
            self._stale.add(self._write_selected)

    def set_opacity(self, selector: str, opacity: float) -> None:
        """Set the block's opacity."""
        self._entries[selector].opacity = opacity
        self._stale.add(self._write_opacities)

    def set_diffuse(self, selector: str, rgb: list[float]) -> None:
        """Set the block's solid colour."""
        self._entries[selector].rgb = list(rgb)
        self._stale.add(self._write_colors)

    def set_selected(self, selector: str, selected: bool) -> None:
        """Add the block to, or remove it from, the source's selection."""
        if selected:
            self._selected.add(selector)
        else:
            self._selected.discard(selector)
        self._stale.add(self._write_selected)

    def color_by(self, selector: str, key: ColorMapKey, lut: PvLookupTable) -> None:
        """Colour the block by key's array through lut."""
        self._entries[selector].color = (key, lut)
        self._stale.add(self._write_color_maps)

    def clear_color(self, selector: str) -> None:
        """Colour the block solid."""
        self._entries[selector].color = None
        self._stale.add(self._write_color_maps)

    def _write_visible(self) -> None:
        self._session.set_property(
            self._rep, "BlockSelectors", [s for s, e in self._entries.items() if e.visible]
        )

    def _write_opacities(self) -> None:
        values: list[str] = []
        for selector, entry in self._entries.items():
            if entry.opacity is not None:
                values += [selector, str(entry.opacity)]
        self._session.set_property(self._rep, "BlockOpacities", values)

    def _write_colors(self) -> None:
        values: list[str] = []
        for selector, entry in self._entries.items():
            if entry.rgb is not None:
                values += [selector, *(str(c) for c in entry.rgb)]
        self._session.set_property(self._rep, "BlockColors", values)

    def _write_color_maps(self) -> None:
        """Write the per-block colour arrays and maps, one aligned entry per block.

        ParaView colours blocks only while the representation itself names
        an array, and a block with no entry then takes the representation's
        colouring; so while any block is coloured, every block has an entry,
        a solid one naming no array, and every entry has a map.  A solid
        entry reuses the first coloured block's map, which adds no map.
        """
        coloured = [entry.color for entry in self._entries.values() if entry.color is not None]
        if not coloured:
            self._session.set_property(self._rep, "BlockColorArrayNames", [])
            self._session.set_property(self._rep, "BlockUseSeparateColorMaps", [])
            self._session.set_property(self._rep, "BlockLookupTables", [])
            self._session.clear_color(self._rep)
            return
        first_key, first_lut = coloured[0]
        names: list[str] = []
        separate: list[str] = []
        luts: list[PvLookupTable] = []
        for selector, entry in self._entries.items():
            if entry.color is None:
                names += [selector, _BLOCK_ASSOCIATIONS[first_key.association], ""]
                luts.append(first_lut)
            else:
                key, lut = entry.color
                names += [selector, _BLOCK_ASSOCIATIONS[key.association], key.array_name]
                luts.append(lut)
            separate += [selector, "1"]
        self._session.set_property(self._rep, "ColorArrayName", [first_key.association, first_key.array_name])
        self._session.set_property(self._rep, "BlockLookupTables", luts)
        self._session.set_property(self._rep, "BlockUseSeparateColorMaps", separate)
        self._session.set_property(self._rep, "BlockColorArrayNames", names)

    def _write_selected(self) -> None:
        """Write the selected blocks that are visible: the selection is drawn from the source, not through BlockSelectors."""
        self._session.set_selected_blocks(
            self._source, sorted(s for s in self._selected if self._entries[s].visible)
        )


class _PartWriter(Protocol):
    """Writes one part's properties; the renderer owns its colour map."""

    dataset: vtkDataObject
    color_key: ColorMapKey | None

    def set_visible(self, visible: bool) -> None: ...

    def set_opacity(self, opacity: float) -> None: ...

    def set_diffuse(self, rgb: list[float]) -> None: ...

    def set_selected(self, selected: bool, diffuse_rgb: list) -> None: ...

    def color_by(self, key: ColorMapKey, lut: PvLookupTable) -> None: ...

    def clear_color(self) -> None: ...

    def hide(self) -> None: ...


class _WholePart:
    """A part that is a whole representation, written through the representation's own properties."""

    def __init__(self, session: ParaviewSession, rep: PvRepresentation, dataset: vtkDataObject) -> None:
        """Write nothing; the representation is already shown."""
        self._session = session
        self._rep = rep
        self.dataset = dataset
        self.color_key: ColorMapKey | None = None

    def set_visible(self, visible: bool) -> None:
        self._session.set_property(self._rep, "Visibility", 1 if visible else 0)

    def set_opacity(self, opacity: float) -> None:
        self._session.set_property(self._rep, "Opacity", opacity)

    def set_diffuse(self, rgb: list[float]) -> None:
        self._session.set_property(self._rep, "DiffuseColor", list(rgb))

    def set_selected(self, selected: bool, diffuse_rgb: list) -> None:
        """Write AmbientColor, Ambient and Diffuse as the pipeline renderer does, and DiffuseColor."""
        if selected:
            self._session.set_property(self._rep, "AmbientColor", list(SELECTED_AMBIENT_RGB))
            self._session.set_property(self._rep, "Diffuse", 0.5)
            self._session.set_property(self._rep, "Ambient", 0.5)
        else:
            self._session.set_property(self._rep, "Diffuse", 1.0)
            self._session.set_property(self._rep, "Ambient", 0.0)
        self._session.set_property(self._rep, "DiffuseColor", list(diffuse_rgb))

    def color_by(self, key: ColorMapKey, lut: PvLookupTable) -> None:
        """Colour the representation by key's array through lut, which no ColorBy replaces."""
        self.color_key = key
        self._session.set_property(self._rep, "UseSeparateColorMap", 1)
        self._session.set_property(self._rep, "LookupTable", lut)
        self._session.set_property(self._rep, "ColorArrayName", [key.association, key.array_name])

    def clear_color(self) -> None:
        """Colour the representation solid and let go of its map."""
        self.color_key = None
        self._session.clear_color(self._rep)
        self._session.set_property(self._rep, "LookupTable", None)

    def hide(self) -> None:
        """Hide the representation, solid."""
        if self.color_key is not None:
            self.clear_color()
        self.set_visible(False)


class _BlockPart:
    """A part that is one block of a composite representation, written through its block table."""

    def __init__(self, table: BlockTable, selector: str, dataset: vtkDataObject) -> None:
        """Show the block."""
        self._table = table
        self._selector = selector
        self.dataset = dataset
        self.color_key: ColorMapKey | None = None
        table.add(selector)

    def set_visible(self, visible: bool) -> None:
        self._table.set_visible(self._selector, visible)

    def set_opacity(self, opacity: float) -> None:
        self._table.set_opacity(self._selector, opacity)

    def set_diffuse(self, rgb: list[float]) -> None:
        self._table.set_diffuse(self._selector, rgb)

    def set_selected(self, selected: bool, diffuse_rgb: list) -> None:
        """Select the block in the source's block selection, and write its colour."""
        self._table.set_selected(self._selector, selected)
        self._table.set_diffuse(self._selector, diffuse_rgb)

    def color_by(self, key: ColorMapKey, lut: PvLookupTable) -> None:
        self.color_key = key
        self._table.color_by(self._selector, key, lut)

    def clear_color(self) -> None:
        self.color_key = None
        self._table.clear_color(self._selector)

    def hide(self) -> None:
        """Remove the block from the table, which hides it."""
        self.color_key = None
        self._table.remove(self._selector)


@dataclass
class _OpenedSource:
    """One opened pvserver source, its one representation, and its block table when it is composite."""

    source: PvSource
    rep: PvRepresentation
    blocks: BlockTable | None
    node_ids: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class _Leaf:
    """A leaf of one opened source and the selector that addresses its block; None for the whole source."""

    source_key: str
    dataset: vtkDataObject
    selector: str | None


@dataclass(frozen=True)
class BlockLeaf:
    """One non-empty leaf of a local composite dataset, its block name and the pvserver selectors that address it."""

    dataset: vtkDataObject
    name: str
    selectors: tuple[str, ...]


class CompositeBlocks:
    """The non-empty leaves of a local composite dataset, in traversal order, with their pvserver block selectors."""

    def __init__(self, leaves: list[BlockLeaf]) -> None:
        """Hold leaves in the order given."""
        self._leaves = tuple(leaves)

    @classmethod
    def from_composite(cls, root: vtkDataObjectTree) -> CompositeBlocks:
        """Walk root's non-empty leaves and give each the selectors its flat index maps to.

        A leaf whose name repeats a sibling's can map to no selector, or to
        the selector of that sibling; :meth:`check_unique` refuses both.
        """
        hierarchy = vtkDataAssembly()
        mapped = vtkDataAssemblyUtilities.GenerateHierarchy(root, hierarchy)
        leaves: list[BlockLeaf] = []
        iterator = root.NewIterator()
        iterator.SkipEmptyNodesOn()
        iterator.InitTraversal()
        while not iterator.IsDoneWithTraversal():
            name = ""
            if iterator.HasCurrentMetaData():
                name = iterator.GetCurrentMetaData().Get(vtkCompositeDataSet.NAME()) or ""
            selectors: tuple[str, ...] = ()
            if mapped:
                selectors = tuple(
                    vtkDataAssemblyUtilities.GetSelectorsForCompositeIds([iterator.GetCurrentFlatIndex()], hierarchy)
                )
            leaves.append(BlockLeaf(iterator.GetCurrentDataObject(), name, selectors))
            iterator.GoToNextItem()
        return cls(leaves)

    @property
    def leaves(self) -> tuple[BlockLeaf, ...]:
        """The leaves in traversal order."""
        return self._leaves

    def check_unique(self) -> None:
        """Raise VisorAddDatasetError unless every leaf has exactly one selector and no two leaves share one."""
        owners: dict[str, BlockLeaf] = {}
        for leaf in self._leaves:
            if len(leaf.selectors) != 1:
                raise VisorAddDatasetError(
                    f"Block {leaf.name!r} maps to {len(leaf.selectors)} pvserver selectors, not one; "
                    "sibling blocks may share its name"
                )
            selector = leaf.selectors[0]
            owner = owners.get(selector)
            if owner is not None:
                raise VisorAddDatasetError(
                    f"Blocks {owner.name!r} and {leaf.name!r} share pvserver selector {selector!r}; "
                    "either would show both"
                )
            owners[selector] = leaf


class ParaviewRenderer(IRenderer):
    """IRenderer over a ParaView render view; one representation per opened dataset."""

    def __init__(
        self,
        session: ParaviewSession,
        background_rgb: tuple[float, float, float],
        frame_requester: FrameRequester,
        view_record_publisher: ViewRecordPublisher,
    ) -> None:
        """Hold the session; every write ends in a frame request, every camera write also publishes the record."""
        super().__init__()
        self._session = session
        self._frame_requester = frame_requester
        self._view_record_publisher = view_record_publisher
        self._sources: dict[str, _OpenedSource] = {}
        # id() of each local leaf dataset -> its entry.  The entry holds the
        # leaf so its id cannot be reused while the entry exists.
        self._leaf_index: dict[int, _Leaf] = {}
        self._parts: dict[int, _PartWriter] = {}
        self._color_maps = _ColorMaps(session)
        self._bounds: list[float] | None = None
        self._actor_count = 0
        self._background_rgb = background_rgb
        self._session.set_background(background_rgb)

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def open_source(self, dataset_key: str, server_path: str, local_root: VisorDatasetType) -> None:
        """Index local_root's leaves to block selectors, open server_path, check every leaf's point count, then show it.

        A non-composite root is its own single leaf, the whole source.  A
        composite source is shown with no block visible; registering a leaf
        shows its block.  Raises :class:`VisorAddDatasetError` having opened
        nothing when a leaf of a composite root has no single selector or
        shares one, and having deleted the source when pvserver's point
        count for a leaf differs from the local leaf's: either means a part
        would show the wrong geometry.
        """
        if is_composite_dataset(local_root):
            blocks = CompositeBlocks.from_composite(local_root)
            blocks.check_unique()
            entries = [_Leaf(dataset_key, leaf.dataset, leaf.selectors[0]) for leaf in blocks.leaves]
        else:
            entries = [_Leaf(dataset_key, local_root, None)]
        source = self._session.open(server_path)
        for entry in entries:
            if entry.selector is None:
                server_points = self._session.point_count(source)
                where = "The dataset"
            else:
                server_points = self._session.block_point_count(source, entry.selector)
                where = f"Block {entry.selector!r}"
            local_points = entry.dataset.GetNumberOfPoints()
            if server_points != local_points:
                self._session.delete(source)
                raise VisorAddDatasetError(
                    f"{where}: pvserver reports {server_points} points, the local dataset has {local_points}"
                )
        rep = self._session.show(source)
        table = BlockTable(self._session, source, rep) if entries[0].selector is not None else None
        self._sources[dataset_key] = _OpenedSource(source, rep, table)
        for entry in entries:
            self._leaf_index[id(entry.dataset)] = entry

    def close_source(self, dataset_key: str) -> None:
        """Delete the source, which takes its representation, then release the maps its parts used."""
        opened = self._sources.pop(dataset_key, None)
        if opened is None:
            logger.debug("close_source: no source for %s; skipping.", dataset_key)
            return
        parts = [self._parts.pop(node_id) for node_id in opened.node_ids]
        keys = [part.color_key for part in parts if part.color_key is not None]
        self._leaf_index = {k: v for k, v in self._leaf_index.items() if v.source_key != dataset_key}
        self._session.delete(opened.source)
        for key in keys:
            self._color_maps.release(key)

    # ------------------------------------------------------------------
    # IRenderer: wire contract
    # ------------------------------------------------------------------

    def build_renderer_annotation(self) -> None:
        """None: no client-side handles."""
        return None

    # ------------------------------------------------------------------
    # IRenderer: node lifecycle
    # ------------------------------------------------------------------

    def register_node(self, node: VisorSceneGraphPartNode, dataset: vtkDataObject) -> None:
        """Show the leaf's block, or take the whole source for non-composite input; idempotent.

        Raises :class:`VisorAddDatasetError` when no opened source holds
        *dataset*.
        """
        if node.id in self._parts:
            return
        entry = self._leaf_index.get(id(dataset))
        if entry is None:
            raise VisorAddDatasetError(f"No pvserver source holds part {node.name!r}")
        opened = self._sources[entry.source_key]
        if entry.selector is None:
            part: _PartWriter = _WholePart(self._session, opened.rep, dataset)
        else:
            part = _BlockPart(opened.blocks, entry.selector, dataset)
        self._parts[node.id] = part
        opened.node_ids.add(node.id)

    def deregister_node(self, node_id: int) -> None:
        """Hide the node's block or representation and release its map; silent if unknown."""
        part = self._parts.pop(node_id, None)
        if part is None:
            logger.debug("deregister_node: no part for node %s; skipping.", node_id)
            return
        for opened in self._sources.values():
            opened.node_ids.discard(node_id)
        key = part.color_key
        part.hide()
        if key is not None:
            self._color_maps.release(key)

    def deregister_all(self) -> None:
        """Delete every source, then every colour map."""
        self._parts.clear()
        for opened in self._sources.values():
            self._session.delete(opened.source)
        self._sources.clear()
        self._leaf_index.clear()
        self._color_maps.release_all()

    def flush_writes(self) -> None:
        """Write every representation's stale per-block lists and selection, then delete the maps no part uses."""
        for opened in self._sources.values():
            if opened.blocks is not None:
                opened.blocks.flush()
        self._color_maps.delete_retired()

    # ------------------------------------------------------------------
    # IRenderer: per-part visual mutations
    # ------------------------------------------------------------------

    def _part(self, node_id: int, operation: str) -> _PartWriter | None:
        """The registered part for node_id, or None after a debug log."""
        part = self._parts.get(node_id)
        if part is None:
            logger.debug("%s: no part for node %s; skipping.", operation, node_id)
        return part

    def apply_visibility(self, node_id: int, visible: bool) -> None:
        """Show or hide the part, then request a frame."""
        part = self._part(node_id, "apply_visibility")
        if part is None:
            return
        part.set_visible(visible)
        self._frame_requester.request_frame()

    def apply_opacity(self, node_id: int, opacity: float) -> None:
        """Write the part's opacity, then request a frame."""
        part = self._part(node_id, "apply_opacity")
        if part is None:
            return
        part.set_opacity(opacity)
        self._frame_requester.request_frame()

    def apply_diffuse_color(self, node_id: int, r: float, g: float, b: float) -> None:
        """Write the part's solid colour, then request a frame."""
        part = self._part(node_id, "apply_diffuse_color")
        if part is None:
            return
        part.set_diffuse([r, g, b])
        self._frame_requester.request_frame()

    def apply_selected(self, node_id: int, selected: bool, diffuse_rgb: list) -> None:
        """Show the part selected or not, writing its colour on both branches; then request a frame.

        A whole representation is tinted with AmbientColor, Ambient and
        Diffuse, as the pipeline renderer tints an actor.  ParaView has no
        per-block lighting terms, so a block is instead put in the source's
        block selection, which ParaView outlines as a wireframe in the
        selection colour; this renderer owns that selection.
        """
        part = self._part(node_id, "apply_selected")
        if part is None:
            return
        part.set_selected(selected, diffuse_rgb)
        self._frame_requester.request_frame()

    def apply_color_variable(
        self,
        node_id: int,
        array_type: VisorVtkVariableType,
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> bool:
        """Colour the part through the shared map for its key, then request a frame; False when refused.

        The part moves to the map for (association, array, component, range),
        creating it when no part uses that key yet, and its previous map is
        released.  Refused, writing nothing, with one WARNING, when that would
        put more than :data:`MAX_COLOR_MAPS` maps in use.  An association that
        is not a :class:`VisorVtkVariableType`, and an array the part's
        dataset does not have, are logged no-ops, as in the pipeline renderer.
        """
        part = self._part(node_id, "apply_color_variable")
        if part is None:
            return True
        association = _ASSOCIATIONS.get(array_type) if isinstance(array_type, VisorVtkVariableType) else None
        if association is None:
            logger.warning(
                "apply_color_variable: association %r is not a VisorVtkVariableType; skipping.", array_type
            )
            return True
        data = part.dataset.GetPointData() if association == "POINTS" else part.dataset.GetCellData()
        if data.GetArray(array_name) is None:
            logger.warning(
                "apply_color_variable: array %r not found for association %s; skipping.", array_name, array_type
            )
            return True
        key = ColorMapKey(association, array_name, component, min_val, max_val)
        previous = part.color_key
        if key == previous:
            return True
        lut = self._color_maps.acquire(key, releasing=previous)
        if lut is None:
            logger.warning(
                "colour map limit (%d) reached; part %r not coloured by %r", MAX_COLOR_MAPS, node_id, array_name
            )
            return False
        part.color_by(key, lut)
        if previous is not None:
            self._color_maps.release(previous)
        self._frame_requester.request_frame()
        return True

    def clear_color_variable(self, node_id: int) -> None:
        """Colour the part solid and release its map, then request a frame; a solid part is not rewritten."""
        part = self._part(node_id, "clear_color_variable")
        if part is None:
            return
        previous = part.color_key
        if previous is not None:
            part.clear_color()
            self._color_maps.release(previous)
        self._frame_requester.request_frame()

    # ------------------------------------------------------------------
    # IRenderer: camera
    # ------------------------------------------------------------------

    def reset_camera(self, bounds: list[float]) -> None:
        """Reset the view camera to bounds and record it; publish, then request a frame."""
        self._session.reset_camera(bounds)
        self._last_camera_state = self._session.read_camera()
        self._publish_camera_record()
        self._frame_requester.request_frame()

    def sync_camera(self, camera_state: VisorCameraState) -> None:
        """Record, then write the view camera; publish, then request a frame."""
        super().sync_camera(camera_state)
        self._session.write_camera(camera_state)
        self._publish_camera_record()
        self._frame_requester.request_frame()

    def set_projection(self, parallel: bool) -> None:
        """Record, then write CameraParallelProjection; publish, then request a frame.

        The view write is unconditional, with or without a record, as in the
        pipeline renderer.
        """
        super().set_projection(parallel)
        camera = self._session.read_camera()
        camera.parallel_projection = parallel
        self._session.write_camera(camera)
        self._publish_camera_record()
        self._frame_requester.request_frame()

    def _publish_camera_record(self) -> None:
        """Hand the camera record to the record publisher; requests no frame."""
        self._view_record_publisher.publish_camera(self.get_camera_state())

    # ------------------------------------------------------------------
    # IRenderer: widget control and fan-out
    # ------------------------------------------------------------------

    def set_edges_visible(self, visible: bool) -> None:
        """Write the edges representation on every opened source's representation, then request a frame."""
        representation = "Surface With Edges" if visible else "Surface"
        for opened in self._sources.values():
            self._session.set_property(opened.rep, "Representation", representation)
        self._frame_requester.request_frame()

    def set_cross_section_visibility(self, visible: bool) -> None:
        """Log WARNING: not supported in PARAVIEW mode."""
        logger.warning("cross-section is not supported in PARAVIEW mode")

    def set_bounding_box_visibility(self, visible: bool) -> None:
        """Log WARNING: not supported in PARAVIEW mode."""
        logger.warning("bounding box is not supported in PARAVIEW mode")

    def update_bounds(self, bounds: list[float]) -> None:
        """Record bounds."""
        self._bounds = list(bounds)

    def update_actor_count(self, count: int) -> None:
        """Record the part count."""
        self._actor_count = count

    def show_geometry_highlight(self, pick: GeometryPick) -> None:
        """Log WARNING: not supported in PARAVIEW mode."""
        logger.warning("geometry highlight is not supported in PARAVIEW mode")

    # ------------------------------------------------------------------
    # IRenderer: render
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Request a frame; never renders on the calling thread."""
        self._frame_requester.request_frame()

    # ------------------------------------------------------------------
    # RCA render-target surface
    # ------------------------------------------------------------------

    @property
    def render_window(self) -> vtkRenderWindow:
        """The window the RCA capture reads."""
        return self._session.render_window

    def set_viewport_size(self, width: int, height: int) -> None:
        """Resize the view; requests no frame."""
        self._session.set_viewport_size(width, height)

    def set_pixel_scale(self, pixel_scale: float) -> None:
        """Accept and ignore: no highlight to rescale."""

    def set_background_rgb(self, background_rgb: tuple[float, float, float]) -> None:
        """Clear to this colour from the next frame; requests no frame."""
        self._background_rgb = background_rgb
        self._session.set_background(background_rgb)

    def record_pipeline_camera(self) -> None:
        """Read the view camera, record it, rotate about its focal point and publish it; requests no frame.

        A pan moves the focal point but not ParaView's centre of rotation, so
        the centre is moved to the focal point after each gesture.
        """
        camera = self._session.read_camera()
        super().sync_camera(camera)
        self._session.set_center_of_rotation(camera.focal_point)
        self._publish_camera_record()

    def record_cross_section_plane(self) -> None:
        """Nothing: no plane widget."""

    @property
    def background_rgb(self) -> tuple[float, float, float]:
        """The colour the view clears to."""
        return self._background_rgb
