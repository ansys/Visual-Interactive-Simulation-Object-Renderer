"""Class for representing a group node in the scene graph."""

from typing_extensions import Self
from vtkmodules.vtkCommonCore import (
    vtkInformation,
)
from vtkmodules.vtkCommonDataModel import vtkDataObject, vtkMultiBlockDataSet, vtkMultiPieceDataSet

from ansys.visor.viewer.core.visor_enums import VisorNodeType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphNode

logger = VisorDefaultLogger(__name__)


class VisorSceneGraphGroupNode(VisorSceneGraphNode):
    """
    Represents a group node in the Visor scene graph.

    This node organizes and manages child nodes, which can be either group nodes or actor nodes.
    Group nodes do not have associated VTK actors but serve as containers for hierarchical scene structure.
    """
    def __init__(self,
                 # parent should be None if this is the root node
                 parent: Self | None,
                 # node_metadata should be None if this is the root node
                 node_metadata: vtkInformation | None = None,
                 # node should be a vtkDataObject or a subclass of it, or None if this is the root node
                 dataset: vtkDataObject | vtkMultiBlockDataSet | vtkMultiPieceDataSet | None = None,
                 root_node: Self | None = None
                 ):
        self._children: list[VisorSceneGraphNode] = []
        super().__init__(parent, node_metadata, dataset, root_node)

    def add_child(self, child: VisorSceneGraphNode):
        """
        Add a child node to this group node.

        Args:
            child (VisorSceneGraphNode): The child node to add.
        """
        self._children.append(child)
        child.Parent = self
        self._clear_cache()

    def _post_init(self,
               parent: Self | None,
               node_metadata: vtkInformation | None = None,
               dataset: vtkDataObject | vtkMultiBlockDataSet | vtkMultiPieceDataSet | None = None,
               root_node: Self | None = None
               ):
        """
        Initialize the group node with the given parameters.
        """
        self._node_type = VisorNodeType.GROUP
        self._set_name(node_metadata)

        num: int = 0
        if isinstance(dataset, vtkMultiBlockDataSet):
            """"""
            self._vtk_dataset_type = "vtkMultiBlockDataSet"
            num = dataset.GetNumberOfBlocks()
        elif isinstance(dataset, vtkMultiPieceDataSet):
            """"""
            self._vtk_dataset_type = "vtkMultiPieceDataSet"
            num = dataset.GetNumberOfPieces()
        else:
            """"""
            msg = f"node type not yet supported: {type(dataset)}"
            logger.error(msg)
            raise RuntimeError(msg)

        self._bounds = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        dataset.GetBounds(self._bounds)

        for i in range(num):
            child = dataset.GetBlock(i)
            child_metadata: vtkInformation = dataset.GetMetaData(i)
            item = VisorSceneGraphNode.get_node(self, child_metadata, child, root_node)
            # register the item in the node's collections
            self.add_child(item)

    @property
    def children(self):
        """Return the children of this node."""
        return self._children

    @property
    def state(self):
        """Return the state of this node."""
        state_obj = super().state
        state_obj.children =  [child.state for child in self.children]
        return state_obj

