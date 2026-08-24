"""Registry for managing multiple Visor datasets within a scene."""

import re
from typing import Dict, List

from ansys.visor.viewer.core.metadata import ExtendedMetadata
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.runtime.dataset.runtime_dataset_state import RuntimeDatasetState
from ansys.visor.viewer.vtk.datasets.visor_dataset import VisorDataset
from ansys.visor.viewer.vtk.variables.visor_part_variables import VisorPartVariables
from ansys.visor.viewer.vtk.variables.visor_variable_update import VisorVariableUpdate

logger = VisorDefaultLogger(__name__)



class VisorDatasetRegistry:
    """
    Registry for managing multiple Visor datasets within a scene.

    It allows adding, removing, and retrieving datasets, as well as managing their states and variables
    collectively.

    Attributes:
        datasets (Dict[int, VisorDataset]): A dictionary mapping dataset IDs to VisorDataset instances.
        unit (str): The unit associated with the datasets in the registry.
    """
    def __init__(self):
        """Initialize the registry."""
        self.datasets: Dict[int, VisorDataset] = {}
        self.unit: str = ""

    @property
    def runtime_state_dict(self) -> Dict[int, RuntimeDatasetState]:
        """
        Get the combined state of all datasets in the registry.

        Returns:
            Dict[str, Dict[int, PartProperties]]: A dict with a single key 'parts' mapping
            to a flat dict of all parts across all dataset states.

        Note:
            The structure is flat to mirror the current JSON schema used by the frontend.
        """
        return {id:dataset.state for id, dataset in self.datasets.items()}

    @property
    def count(self) -> int:
        """
        Get the number of datasets in the registry.

        Returns:
            int: The count of datasets.
        """
        return len(self.datasets)

    def list_info(self) -> Dict[int, dict]:
        """
        Get the state information for all datasets in the registry.

        Returns a dictionary mapping dataset IDs to their respective state information.
        """
        return {k: dataset.info_dict for k, dataset in self.datasets.items()}

    def get_by_name(self, name: str) -> VisorDataset | None:
        """
        Retrieve a dataset by its name.

        Args:
            name (str): The name of the dataset to retrieve.

        Returns:
            VisorDataset | None: The dataset with the specified name, or None if not found.
        """
        for dataset in self.datasets.values():
            if dataset.name == name:
                return dataset
        return None

    def add(self,
            dataset_id: int,
            dataset_name: str,
            input: VisorDatasetType,
            part_name_to_id: Dict[str, int],
            metadata: ExtendedMetadata,
            ) -> VisorDataset:
        """
        Add a new dataset to the registry with associated metadata.
        """
        self._update_unit(metadata)

        # VisorDataset builds its own PartIndex directly from the VTK data object,
        # seeded with the scene-graph node IDs so part_id == scene-graph node ID.
        dataset = VisorDataset(dataset_id, dataset_name, input, part_name_to_id, metadata)

        # Store the dataset in the registry
        self.datasets[dataset_id] = dataset

        return dataset

    def remove(self, dataset_id: int) -> None:
        """
        Remove a dataset from the registry by its ID.
        """
        if dataset_id in self.datasets:
            self.datasets.pop(dataset_id)

    def _get_unique_dataset_name(self, name: str) -> str:
        """
        Rename the dataset by appending a suffix to ensure uniqueness.

        @return
        A unique dataset name. If the original name is unique, it is returned as is.
        """
        # Get existing dataset names
        dataset_names = [dataset.name for dataset in self.datasets.values()]

        # If the name is unique, return it as is
        if name not in dataset_names:
            return name

        # Extract base name and suffix if present
        match = re.match(r"^(.*?)(?:_(\d+))?$", name)
        base_name = match.group(1)
        suffix = int(match.group(2)) if match.group(2) else 1

        # Generate new name with incremented suffix until unique
        new_name = f"{base_name}_{suffix}"
        while new_name in dataset_names:
            suffix += 1
            new_name = f"{base_name}_{suffix}"
        return new_name

    def get_sanitized_metadata_name(self, metadata: ExtendedMetadata) -> str:
        """
        Normalize the metadata by ensuring unique dataset names.
        """
        # TODO: move to protected after composite dataset support is added
        # and Scene.add_dataset delegates more cleanly to DatasetRegistry

        if metadata is None:
            raise ValueError("Metadata cannot be None.")

        new_name = self._get_unique_dataset_name(metadata.name)
        if new_name != metadata.name:
            logger.warning(f"Dataset name '{metadata.name}' already exists. Renaming to '{new_name}'.")

        return new_name

    def clear(self):
        """
        Clear all datasets from the registry.
        """
        self.datasets.clear()
        self._reset_unit()

    def list_variables(self, dataset_id: int) -> List[VisorPartVariables]:
        """
        Get the variable information from the scene graph.
        """
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            msg = f"Dataset with id {dataset_id} not found."
            logger.error(msg)
            raise ValueError(msg)
        return dataset.list_variables()

    def update_variables(self, dataset_id: int, variables: List[VisorVariableUpdate]) -> None:
        """
        Update the variables in the scene graph.
        """
        dataset = self.datasets.get(dataset_id)
        if dataset is None:
            msg = f"Dataset with id {dataset_id} not found."
            logger.error(msg)
            raise ValueError(msg)
        dataset.update_variables(variables)

    def _validate_unit(self, metadata: ExtendedMetadata) -> bool:
        """
        Validate that the unit of the new metadata matches the existing unit.

        @return
        True if the units match or if the existing unit is empty, False otherwise.
        """
        # TODO: move to protected after composite dataset support is added
        # and Scene.add_dataset delegates more cleanly to DatasetRegistry

        if metadata is None:
            return False

        if len(self.datasets) == 0:
            # if this is the first dataset being added into a blank scene, accept any unit
            return True

        if metadata.unit != self.unit:
            msg = (f"Unit mismatch: existing ('{self.unit}') vs new ('{metadata.unit}')."
                   f" Setting unit to null.")
            logger.warning(msg)
            return False

        return True

    def _update_unit(self, metadata: ExtendedMetadata):
        """
        Update the unit to the specified value.
        """
        if self._validate_unit(metadata):
            # store unit to this class
            self.unit = metadata.unit
        else:
            # reset unit to empty string
            self._reset_unit()

    def _reset_unit(self):
        """
        Reset the unit to an empty string.
        """
        self.unit = ""

