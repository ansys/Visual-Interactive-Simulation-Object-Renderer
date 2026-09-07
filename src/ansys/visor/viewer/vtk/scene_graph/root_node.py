"""Class representing the scene graph root node."""

from typing_extensions import Self
from vtkmodules.vtkCommonCore import (
    vtkInformation,
)
from vtkmodules.vtkCommonDataModel import (
    vtkDataObject,
    vtkMultiBlockDataSet,
    vtkMultiPieceDataSet,
)

from ansys.visor.viewer.core.visor_enums import VisorNodeType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphGroupNode, VisorSceneGraphNode

logger = VisorDefaultLogger(__name__)

class VisorBounds:
    """
    A class representing the bounds of a scene graph node.
    """
    def __init__(self):
        """Initialize the bounds."""
        self.bounds = {}

    def set(self, node_id: int, bounds: list[float]):
        """Set the bounds of a scene graph node."""
        self.bounds[node_id] = bounds

    def remove(self, node_id: int):
        """Remove the bounds of a scene graph node."""
        self.bounds.pop(node_id, None)

    def compute_bounds(self) -> list[float]:
        """Compute the bounds of the scene graph node."""
        if not self.bounds:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # Note: used list comprehension for clarity.
        # For many datasets, a single-pass loop would be more efficient.
        min_x = min(bounds[0] for bounds in self.bounds.values())
        max_x = max(bounds[1] for bounds in self.bounds.values())
        min_y = min(bounds[2] for bounds in self.bounds.values())
        max_y = max(bounds[3] for bounds in self.bounds.values())
        min_z = min(bounds[4] for bounds in self.bounds.values())
        max_z = max(bounds[5] for bounds in self.bounds.values())
        return [min_x, max_x, min_y, max_y, min_z, max_z]


class VisorSceneGraph(VisorSceneGraphGroupNode):
    """
    A root node for the scene graph that contains all other nodes.
    This node serves as the entry point for the scene graph and contains all
    other nodes as descendants.
    """

    def __init__(self):
        """Initialize the scene graph node."""
        super().__init__(None, None, None, self)

    def _post_init(self,
                   parent: Self | None,
                   node_metadata: vtkInformation | None = None,
                   dataset: vtkDataObject | vtkMultiBlockDataSet | vtkMultiPieceDataSet | None = None,
                   root_node: Self | None = None
                   ):
        """Custom initialization for scene graph root node."""
        self._node_type = VisorNodeType.ROOT
        self._name = self._vtk_dataset_type = "root"
        self._dataset_bounds: VisorBounds = VisorBounds()

    @property
    def bounds(self) -> list[float]:
        """
        For the root node, return the overall scene bounds computed across
        all loaded datasets.
        """
        return self._dataset_bounds.compute_bounds()

    def load_dataset(
            self,
            dataset: VisorDatasetType,
            name: str | None = None,
    ):
        """
        Populate the scene graph with the hierarchy found in a
        path to a VTK file or a pre-existing VTK dataset object.

        Args:
            dataset (VisorDatasetType): The dataset object to load.
        """

        logger.debug(f"Beginning scene graph node construction from dataset: {type(dataset)}")

        info = vtkInformation()
        name = "n/a" if name is None else name
        info.Set(self.METADATA_NAME_KEY, name)
        item = VisorSceneGraphNode.get_node(self, info, dataset, self)
        # update the bounds
        self._dataset_bounds.set(item.id, item.bounds)
        # register the item in the node's children
        self.add_child(item)

        logger.debug(f"Finished scene graph node construction from dataset: {type(dataset)}")
        return item.id

    def remove_dataset(self, dataset_id: int):
        """
        Remove a dataset from the scene graph by its ID.

        Args:
            dataset_id (int): The ID of the dataset to remove.
        """
        self.remove_node(dataset_id)
        # update the bounds
        self._dataset_bounds.remove(dataset_id)
        logger.debug(f"Removed dataset with ID: {dataset_id}")

