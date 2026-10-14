"""Normalize platform-width VTK arrays before a dataset is served to the wasm client.

WORKAROUND for an upstream VTK serialization defect: ``vtkObjectManager``
serializes ``vtkLongArray`` / ``vtkUnsignedLongArray`` by class name only.
On an LP64 server (Linux, macOS) ``long`` is 8 bytes; in the wasm32
vtkWebAssembly client it is 4 bytes, so the client rebuilds those arrays
with the wrong element width and reads every 64-bit value as two 32-bit
halves.  ``vtkHDFReader`` returns 64-bit integer data, including cell
connectivity and offsets, as ``vtkLongArray`` on LP64 hosts, so a dataset
read back from VTKHDF (for example a ``load_state`` snapshot) renders empty
or crashes the client with ``std::bad_alloc``.

Scope: applied only to datasets Visor itself reads from VTKHDF, in
``file_to_dataset``.  Those objects are owned by Visor, so they are converted
in place.  In-memory datasets supplied by a caller are deliberately not
converted (that would mutate objects the caller still holds); long-backed
in-memory data remains affected by the upstream defect.

Upstream issue: https://gitlab.kitware.com/vtk/vtk/-/issues/XXXXX (placeholder)

Remove this module, and its call in ``file_to_dataset``, once the VTK version
Visor depends on serializes platform-width arrays with a fixed element width.
"""

from vtkmodules.vtkCommonCore import (
    vtkAbstractArray,
    vtkDataArray,
    vtkTypeInt64Array,
    vtkTypeUInt64Array,
)
from vtkmodules.vtkCommonDataModel import (
    vtkCellArray,
    vtkCompositeDataSet,
    vtkDataObject,
    vtkDataSet,
    vtkDataSetAttributes,
    vtkFieldData,
    vtkPolyData,
    vtkUnstructuredGrid,
)

# Matched by exact class name, not isinstance: whether the fixed-width
# classes derive from the platform-width ones depends on the VTK build.
_FIXED_WIDTH_REPLACEMENTS = {
    "vtkLongArray": vtkTypeInt64Array,
    "vtkUnsignedLongArray": vtkTypeUInt64Array,
}


class ClientDatasetNormalizer:
    """Rewrites platform-width VTK array classes into fixed-width ones before a dataset reaches the wasm client.

    Temporary workaround for the upstream VTK serialization defect described
    in this module's docstring; remove once that defect is fixed upstream.
    """

    @staticmethod
    def normalize_dataset_for_client(dataset: vtkDataObject) -> int:
        """Normalize every leaf of *dataset* in place; return the number of arrays replaced (0 means nothing changed).

        Values, array names, array order and active-attribute roles are
        preserved; only the array classes change.  Objects that are neither a
        ``vtkDataSet`` nor a ``vtkCompositeDataSet`` are left untouched.
        """
        if isinstance(dataset, vtkCompositeDataSet):
            replaced = ClientDatasetNormalizer._normalize_field_data(dataset.GetFieldData())
            iterator = dataset.NewIterator()
            iterator.SkipEmptyNodesOn()
            iterator.InitTraversal()
            while not iterator.IsDoneWithTraversal():
                leaf = iterator.GetCurrentDataObject()
                if isinstance(leaf, vtkDataSet):
                    replaced += ClientDatasetNormalizer._normalize_leaf(leaf)
                iterator.GoToNextItem()
            return replaced
        if isinstance(dataset, vtkDataSet):
            return ClientDatasetNormalizer._normalize_leaf(dataset)
        return 0

    @staticmethod
    def _normalize_leaf(leaf: vtkDataSet) -> int:
        """Normalize one non-composite dataset's cell arrays and its point, cell and field data."""
        replaced = sum(
            ClientDatasetNormalizer._normalize_cell_array(cells)
            for cells in ClientDatasetNormalizer._cell_arrays_of(leaf)
        )
        for field_data in (leaf.GetPointData(), leaf.GetCellData(), leaf.GetFieldData()):
            replaced += ClientDatasetNormalizer._normalize_field_data(field_data)
        if replaced:
            leaf.Modified()
        return replaced

    @staticmethod
    def _cell_arrays_of(leaf: vtkDataSet) -> list[vtkCellArray]:
        """Return the cell arrays a leaf carries: verts/lines/polys/strips for polydata, cells for an unstructured grid."""
        if isinstance(leaf, vtkPolyData):
            candidates = [leaf.GetVerts(), leaf.GetLines(), leaf.GetPolys(), leaf.GetStrips()]
        elif isinstance(leaf, vtkUnstructuredGrid):
            candidates = [leaf.GetCells()]
        else:
            candidates = []
        return [cells for cells in candidates if cells is not None]

    @staticmethod
    def _normalize_cell_array(cells: vtkCellArray) -> bool:
        """Re-seat generic-storage offsets and connectivity as vtkTypeInt64Array; True if changed."""
        if not cells.IsStorageGeneric():
            return False
        offsets = vtkTypeInt64Array()
        offsets.DeepCopy(cells.GetOffsetsArray())
        connectivity = vtkTypeInt64Array()
        connectivity.DeepCopy(cells.GetConnectivityArray())
        cells.SetData(offsets, connectivity)
        return True

    @staticmethod
    def _normalize_field_data(field_data: vtkFieldData | None) -> int:
        """Replace vtkLongArray/vtkUnsignedLongArray with fixed-width copies, keeping array order, names and active-attribute roles."""
        if field_data is None:
            return 0
        arrays = [field_data.GetAbstractArray(i) for i in range(field_data.GetNumberOfArrays())]
        replacements = [ClientDatasetNormalizer._fixed_width_copy(array) for array in arrays]
        changed = [i for i, replacement in enumerate(replacements) if replacement is not None]
        if not changed:
            return 0

        # Active-attribute roles, as (attribute type, array position).
        roles: list[tuple[int, int]] = []
        if isinstance(field_data, vtkDataSetAttributes):
            for attribute_type in range(vtkDataSetAttributes.NUM_ATTRIBUTES):
                active = field_data.GetAbstractAttribute(attribute_type)
                for position, array in enumerate(arrays):
                    if active is not None and active is array:
                        roles.append((attribute_type, position))

        # vtkFieldData cannot replace an array in place, so the tail from the
        # first changed position is removed and re-appended in order.
        first = changed[0]
        for position in reversed(range(first, len(arrays))):
            field_data.RemoveArray(position)
        for position in range(first, len(arrays)):
            replacement = replacements[position]
            field_data.AddArray(replacement if replacement is not None else arrays[position])
        for attribute_type, position in roles:
            field_data.SetActiveAttribute(position, attribute_type)
        return len(changed)

    @staticmethod
    def _fixed_width_copy(array: vtkAbstractArray | None) -> vtkDataArray | None:
        """Return a vtkTypeInt64Array/vtkTypeUInt64Array deep copy of a long array, or None if no conversion is needed."""
        if array is None:
            return None
        replacement_class = _FIXED_WIDTH_REPLACEMENTS.get(array.GetClassName())
        if replacement_class is None:
            return None
        replacement = replacement_class()
        replacement.DeepCopy(array)
        replacement.SetName(array.GetName())
        return replacement

