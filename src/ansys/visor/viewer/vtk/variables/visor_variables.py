"""Class representing metadata for point and cell variables in a VTK dataset."""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from vtkmodules.vtkCommonCore import vtkDataArray
from vtkmodules.vtkCommonDataModel import vtkDataObject, vtkFieldData

from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.info.visor_variable_info import VisorVariableInfo
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate

logger = VisorDefaultLogger(__name__)


@dataclass(frozen=True)
class VisorVariable:
    """
    Metadata for a VTK variable array.

    Note: This class does not manage the actual data array, only its metadata.

    Attributes:
        index (int): Index of the variable within its type (point or cell).
        type (VisorVtkVariableType): Type of the variable (e.g., POINT
              or CELL).
        name (str): Name of the variable.
        num_components (int): Number of components in the variable array.
        num_points (int): Number of points/cells in the variable array.
        ranges (List[Tuple[float, float]]): List of ranges for each component.
        magnitude_range (Tuple[float, float] | None): Range of magnitudes if applicable
    """
    index: int
    type: VisorVtkVariableType
    name: str
    num_components: int
    num_points: int
    ranges: List[Tuple[float, float]]
    ranges: List[Tuple[float, float]]
    magnitude_range: Tuple[float, float] | None = None

    @classmethod
    def from_array(cls, index: int, arr: vtkDataArray, variable_type: VisorVtkVariableType) -> "VisorVariable":
        """Construct a VisorVariable from the given array and variable_type."""
        name = arr.GetName()
        num_components = int(arr.GetNumberOfComponents())
        num_points = int(arr.GetNumberOfTuples())
        ranges = [tuple(arr.GetRange(i)) for i in range(num_components)]
        magnitude_range = tuple(arr.GetRange(-1)) if hasattr(arr, "GetRange") else None

        cls._validate_name(name)

        return cls(
            index=int(index),
            type=variable_type,
            name=name,
            num_components=num_components,
            num_points=num_points,
            ranges=ranges,
            magnitude_range=magnitude_range,
        )

    def to_info(self):
        """Return a VisorVariableInfo object from the current VisorVariable instance."""
        return VisorVariableInfo(
            index_for_type=self.index,
            type=self.type,
            name=self.name,
            num_components=self.num_components,
            ranges=self.ranges,
            magnitude_range=self.magnitude_range
        )

    def to_dict(self):
        """Return a dictionary representation of the VisorVariable instance."""
        return {
            "index": self.index,
            "type": getattr(self.type, "name", str(self.type)),
            "name": self.name,
            "num_components": self.num_components,
            "num_points": self.num_points,
            "ranges": self.ranges,
            "magnitude_range": self.magnitude_range,
        }

    @staticmethod
    def _validate_name(name: str):
        """
        Validate the variable name against VTK constraints.

        Currently only validates name length, as VTK does not have strict constraints on variable names,
        as the name is currently used as part of the unique identifier for the variable.

        Additional validation can be added if needed (eg. restrictions on characters etc)
        """
        if name is None:
            logger.warning("Variable name is None.")
            return
        if len(name) > 128:
            logger.warning(f"Variable name '{name}' is longer than 128 chars.")


class VisorVariables:
    """
    Metadata for point and cell variables in a VTK dataset.
    This class does not manage the actual data arrays, only their metadata.

    This class only currently supports non-composite datasets, as composite datasets
       require more complex handling.

    Attributes:
        _point (List[VisorVariable]): List of point variable metadata.
        _cell (List[VisorVariable]): List of cell variable metadata.
    Methods:
        reload(dataset: vtkDataObject) -> None:
            Reload variable metadata from the given VTK dataset.
        list_info() -> List[VisorVariableInfo]:
            List metadata for all variables as VisorVariableInfo objects.
        list() -> List[VisorVariable]:
            List all variables as VisorVariable objects.
        validate_new_variables(variables: List[VisorVariableUpdate]) -> bool:
            Validate point and cell variables against existing metadata.
    """
    def __init__(self, dataset: vtkDataObject):
        """Initialize the variables metadata."""
        if dataset is None:
            raise ValueError("Dataset cannot be None")

        # Initialize empty lists for point and cell variables
        self._point: List[VisorVariable] = []
        self._cell: List[VisorVariable] = []

        # Populate the variable metadata from the dataset
        self._populate_from_dataset(dataset)

    def reload(self, dataset: vtkDataObject) -> None:
        """
        Reload variable metadata from the given VTK dataset.
        - `dataset` is expected to expose GetPointData() and GetCellData() methods.
        """
        if dataset is None:
            raise ValueError("Dataset cannot be None")
        self._populate_from_dataset(dataset)

    def list_info(self) -> List[VisorVariableInfo]:
        """List all variables as VisorVariableInfo objects."""
        return [var.to_info() for var in self._point + self._cell]

    def list(self) -> List[VisorVariable]:
        """List all variables as VisorVariable objects."""
        return self._point + self._cell

    def validate_new_variables(self, variables: List[VisorVariableUpdate]) -> bool:
        """
        Validate point and cell variables against existing metadata.
        - `variables` is expected to be a mapping with optional "point" and "cell" keys,
          each mapping variable names to array-like data.

        Returns True if all variables are valid, and False if any are invalid.
        """
        by_type = self._group_by_type(variables)

        # Keys are (name, num_components) tuples for uniqueness
        point_map: Dict[Tuple[str, int]: VisorVariable] = {(v.name, v.num_components):v for v in self._point}
        cell_map: Dict[Tuple[str, int]: VisorVariable] = {(v.name, v.num_components):v for v in self._cell}

        # Validate point and cell variables separately
        new_point_data = by_type.get(VisorVtkVariableType.POINT, [])
        if not self._validate_for_type(point_map, new_point_data):
            return False
        new_cell_data = by_type.get(VisorVtkVariableType.CELL, [])
        if not self._validate_for_type(cell_map, new_cell_data):
            return False

        return True

    def _validate_for_type(
            self,
            existing_var_map: Dict[Tuple[str, int], VisorVariable],
            variables_to_validate: List[VisorVariableUpdate]
    ) -> bool:
        """
        Validate new variables of a specific type against existing metadata.
        - `new_var_dict` maps variable names to array-like data.
        - `existing_metadata` is a list of VisorVariable for the variable type.
        Returns True if all variables are valid, and False if any are invalid.
        """
        for new_var in variables_to_validate:
            if (new_var.name, new_var.num_components) not in existing_var_map:
                return False  # Variable name not found.

            # TODO: add check for data shape matching original data shape.
        return True

    def _group_by_type(
            self,
            variables: List[VisorVariableUpdate]
        ) -> Dict[VisorVtkVariableType, List[VisorVariableUpdate]]:
        """
        Group variables by their VisorVtkVariableType.
        - `variables` is a list of VisorVariableUpdate instances.
        Returns a dictionary mapping VisorVtkVariableType to lists of VisorVariableUpdate.
        """
        by_type: Dict[VisorVtkVariableType, List[VisorVariableUpdate]] = {}
        for variable in variables:
            by_type.setdefault(variable.type, []).append(variable)
        return by_type

    def _populate_from_dataset(self, dataset: vtkDataObject) -> None:
        """
        Populate point and cell variable metadata from a VTK dataset.
        - `dataset` is expected to expose GetPointData() and GetCellData() methods.
        """

        # Clear existing metadata before repopulating
        self._point.clear()
        self._cell.clear()

        point_data = dataset.GetPointData()
        cell_data = dataset.GetCellData()

        self._point = self._collect_variables_for_type(point_data, VisorVtkVariableType.POINT)
        self._cell = self._collect_variables_for_type(cell_data, VisorVtkVariableType.CELL)

    def _collect_variables_for_type(self, data: vtkFieldData, var_type: VisorVtkVariableType) -> List[VisorVariable]:
        """
        Get the list of VisorVariable metadata for the specified variable type.
        - `data` is the result of GetPointData() or GetCellData() from a VTK dataset.
           (vtkFieldData is the base class for both vtkPointData and vtkCellData)
        - `var_type` specifies whether to get POINT or CELL variable metadata.
        Returns a list of VisorVariable instances.
        """
        result: List[VisorVariable] = []
        for i in range(data.GetNumberOfArrays()):
            array: vtkDataArray = data.GetArray(i)
            if array is None:
                continue # Defensive check, should not happen
            result.append(VisorVariable.from_array(i, array, var_type))
        return result

