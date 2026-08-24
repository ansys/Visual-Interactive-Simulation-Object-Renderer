"""Class to represent node in Visor's scene graph"""

import json
from abc import ABC, abstractmethod
from typing import (
    Callable,
    Optional,
    Union,
)

from typing_extensions import Self
from vtkmodules.vtkCommonCore import (
    vtkInformation,
    vtkInformationStringVectorKey,
)
from vtkmodules.vtkCommonDataModel import (
    vtkCompositeDataSet,
)

from ansys.visor.viewer.core.visor_enums import VisorNodeType
from ansys.visor.viewer.core.visor_helpers import get_random_javascript_safe_id, is_composite_dataset
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.core.visor_types import VisorDatasetType
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo

logger = VisorDefaultLogger(__name__)

class NodeCache:
    """
    A simple cache for storing descendant nodes to avoid recomputation.
    """
    def __init__(self):
        """Initialize a cache for descendant nodes."""
        self._cache = {}

    def make_key(self, kind, include_self, filter_func):
        """Create a cache key for descendant nodes."""
        filter_key = self._filter_func_cache_key(filter_func)
        return (kind, include_self, filter_key)

    def get(self, key):
        """Return a descendant node for the given key."""
        return self._cache.get(key)

    def set(self, key, value):
        """Set a descendant node for the given key."""
        self._cache[key] = value

    def clear(self):
        """Clear the cache."""
        self._cache.clear()

    @staticmethod
    def _filter_func_cache_key(filter_func):
        """Function to generate a cache key for a filter function."""
        if filter_func is None:
            return None
        if hasattr(filter_func, "__code__"):
            code = filter_func.__code__
            return code.co_names
        if hasattr(filter_func, "__qualname__"):
            return (filter_func.__module__, filter_func.__qualname__)
        return repr(filter_func)


class VisorSceneGraphNode(ABC):
    """
    Abstract base class representing a node in the Visor scene graph.

    Each node corresponds to either a dataset or a group of datasets in the scene graph.
    This class defines the common interface and properties for all scene graph nodes,
    including methods for initialization, serialization, and actor management.

    Subclasses must implement methods for post-initialization and updating descendant or self actors.

    Attributes:
        METADATA_NAME_KEY: Key used to retrieve the node's name from VTK metadata.
        _id: Unique identifier for the node.
        _node_type: Type of the node (e.g., group or actor).
        _name: name of the node.
        _vtk_dataset_type: String representing the VTK dataset type.
        _root_node: Reference to the root node of the scene graph.
        _bounds: Bounding box of the node.
        _cache: Cache for descendant nodes to avoid recomputation.
    """
    METADATA_NAME_KEY: vtkInformationStringVectorKey = vtkCompositeDataSet.NAME()

    def __init__(
            self,
            # parent should be None if this is the root node
            parent: Self | None,
            # node_metadata should be None if this is the root node
            node_metadata: vtkInformation | None = None,
            # node should be a vtkDataObject or a subclass of it,
            # or None if this is the root node
            dataset: VisorDatasetType | None = None,
            root_node: Self | None = None
    ):
        """Initialize a VisorSceneGraphNode instance."""
        self._id: int = get_random_javascript_safe_id()
        self._node_type: VisorNodeType
        self._name: str = ""
        self._vtk_dataset_type: str
        self._root_node: VisorSceneGraphNode = root_node
        self._bounds: list[float]
        self._cache = NodeCache()

        # Post-initialization method to set up the node.
        self._post_init(parent, node_metadata, dataset, root_node)

    @abstractmethod
    def _post_init(
            self,
            parent: Self | None,
            metadata: vtkInformation | None = None,
            dataset: VisorDatasetType | None = None,
            root_node: Self | None = None
    ):
        """
        Abstract method for performing post-initialization logic specific to the node type.

        This method should be implemented by subclasses to handle additional setup after
        the base class constructor has initialized common attributes. Typical tasks include
        setting node-specific properties, processing the dataset, and updating collections.

        Args:
            parent (Self | None): The parent node, or None if this is the root node.
            node_metadata (vtkInformation | None): Optional VTK metadata for the node.
            dataset (vtk_dataset_type | None): The VTK dataset associated with this node.
            root_node (Self | None): Reference to the root node of the scene graph.

        Raises:
            NotImplementedError: If not implemented in a subclass.
        """
        raise NotImplementedError

    def get_descendant_nodes(
            self,
            include_self: bool = False,
            filter_func: Optional[Callable[['VisorSceneGraphNode'], bool]] = None
    ) -> list['VisorSceneGraphNode']:
        """Return a list of descendant nodes."""
        nodes = []
        for node in self._get_descendant_node_dict(include_self, filter_func).values():
            nodes.append(node)
        return nodes

    def get_descendant_node(self, node_id: int, include_self=False) -> Optional['VisorSceneGraphNode']:
        """ Return a descendant node by its ID."""
        return self._get_descendant_node_dict(include_self=include_self).get(node_id, None)

    def get_descendant_part_node(self, node_id: int, include_self=False) -> Optional['VisorSceneGraphNode']:
        """Return a descendant leaf (part) node by its ID."""
        return self._get_descendant_node_dict(
            include_self=include_self,
            filter_func=lambda node: node.is_part_node
        ).get(node_id, None)

    def get_descendant_part_nodes(self,
                                  include_self: bool = False
                                  ) -> list['VisorSceneGraphNode']:
        """Return descendant nodes that are leaf (part) nodes."""
        return self.get_descendant_nodes(
            include_self=include_self,
            filter_func=lambda node: node.is_part_node
        )

    def refresh_descendant_variable_metadata(self, include_self=False) -> None:
        """
        Refresh the cached variable metadata on all descendant part nodes without
        re-connecting the VTK pipeline (i.e. without calling SetInputConnection or
        marking the mapper Modified). Use this after an in-place variable data update
        where the pipeline topology has not changed.
        """
        for node in self.get_descendant_part_nodes(include_self=include_self):
            node.refresh_variable_metadata()

    def descendant_part_count(self, include_self=False) -> int:
        """Return the number of descendant part nodes (optionally including self)."""
        return len(self.get_descendant_part_nodes(include_self=include_self))

    def get_descendant_node_name_to_id_map(self) -> dict[str, int]:
        """
        Get a mapping of part names to their corresponding node IDs
        for a specific dataset.

        Returns:
            dict[str, int]: A dictionary mapping part names to node IDs.
        """
        return {node.name: id for id, node in self._get_descendant_node_dict(include_self=True).items() if node.name is not None}

    @staticmethod
    def get_node(
            parent: 'VisorSceneGraphNode',
            node_metadata: vtkInformation | None = None,
            dataset: VisorDatasetType | None = None,
            root_node: Union['VisorSceneGraphNode', None] = None
    ) -> 'VisorSceneGraphNode':
        """
        Create and return an appropriate VisorSceneGraphNode subclass instance based
        on the provided VTK dataset type.

        This factory method inspects the type of the given `dataset` and instantiates
        either a group node (`VisorSceneGraphGroupNode`) or a leaf part node
        (`VisorSceneGraphPartNode`). If the dataset type is not supported,
        a RuntimeError is raised.

        Args:
            parent (VisorSceneGraphNode): The parent node in the scene graph.
            node_metadata (vtkInformation | None): Optional VTK metadata for the node.
            dataset (vtk_dataset_type | None): The VTK dataset associated with this node.
            root_node (VisorSceneGraphNode | None): Ref to the root node of the scene graph.

        Returns:
            VisorSceneGraphNode: An instance of the appropriate subclass for the dataset type.

        Raises:
            RuntimeError: If the dataset type is not supported.
        """
        from ansys.visor.viewer.vtk.scene_graph import VisorSceneGraphGroupNode, VisorSceneGraphPartNode

        subclass_map = {VisorNodeType.GROUP: VisorSceneGraphGroupNode,
                        VisorNodeType.PART: VisorSceneGraphPartNode}
        try:
            node_type = VisorSceneGraphNode.get_node_type_from_dataset(dataset)
            subclass = subclass_map[node_type]
            return subclass(parent, node_metadata, dataset, root_node)
        except RuntimeError as e:
            msg = f"could not create scene graph node: {e}"
            logger.error(msg)
            raise RuntimeError(msg)

    @staticmethod
    def get_node_type_from_dataset(dataset) -> VisorNodeType | None:
        """ Determine the node type based on the dataset type."""
        # Determine if the dataset is composite
        # Raises RuntimeError if dataset is unsupported
        is_composite = is_composite_dataset(dataset)
        if is_composite:
            return VisorNodeType.GROUP
        else:
            return VisorNodeType.PART

    def remove_node(self, node_id: int) -> bool:
        """
        Remove a child node and its children from this node by its ID.
        """
        if not self.is_group_node:
            logger.warning("Cannot remove a node from an actor node.")
            return False

        children = self._children
        for i, child in enumerate(children):
            if child.id == node_id:
                # Remove the child and its descendants
                child._cleanup_descendants()
                del children[i]
                self._clear_cache()
                return True
            if child.remove_node(node_id):
                self._clear_cache()
                return True
        return False

    def _cleanup_descendants(self):
        """Recursively clean up all descendants."""
        if not self.is_group_node:
            return
        for child in self._children:
            child._cleanup_descendants()
        self._children = []

    def get_json(self) -> str:
        """
        Return a cached JSON string representation of the node.

        Returns:
            str: The JSON string representation of the node.
        """
        return json.dumps(self.state.model_dump())

    @property
    def id(self):
        """Return the node ID."""
        return self._id

    @property
    def name(self):
        """Return the node name."""
        return self._name

    @property
    def vtk_dataset_type(self):
        """Return the node VTK dataset type."""
        return self._vtk_dataset_type


    @property
    def is_part_node(self) -> bool:
        """Return whether the node is a leaf (renderable) part node."""
        return self._node_type == VisorNodeType.PART

    @property
    def is_group_node(self) -> bool:
        """Return whether the node is a group node."""
        return self._node_type in [VisorNodeType.GROUP, VisorNodeType.ROOT]

    @property
    def bounds(self) -> list[float]:
        """Return the bounds of the node."""
        return self._bounds

    @property
    def state(self) -> SceneGraphNodeInfo:
        """Return the scene graph node info"""
        return SceneGraphNodeInfo(
            id=self.id,
            name=self.name,
            isActorNode=self.is_part_node,
            isGroupNode=self.is_group_node,
            nodeType=self._vtk_dataset_type,
            bounds=self.bounds,
        )

    def _set_name(self, node_metadata: vtkInformation | None = None):
        """
        Set the name of the node.
        This method is called during initialization to set the name of the node.
        If the name is not set in the metadata, it defaults to "untitled".
        """
        if node_metadata is None:
            msg = "node_metadata should not be null here"
            logger.error(msg)
            raise RuntimeError(msg)
        elif node_metadata.Has(self.METADATA_NAME_KEY):
            self._name = node_metadata.Get(self.METADATA_NAME_KEY)
        if not self._name:
            self._name = "untitled"

    def _get_descendant_node_dict(
            self,
            include_self: bool = False,
            filter_func: Optional[Callable[['VisorSceneGraphNode'], bool]] = None
    ) -> dict[int, 'VisorSceneGraphNode']:
        """Return the descendant node dictionary."""
        cache_key = self._cache.make_key("node_dict", include_self, filter_func)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        node_dict = {}
        if include_self:
            if filter_func is None or filter_func(self):
                node_dict[self.id] = self
        for child in getattr(self, "_children", []):
            child_dict = child._get_descendant_node_dict(include_self=True, filter_func=filter_func)
            node_dict.update(child_dict)

        self._cache.set(cache_key, node_dict)
        return node_dict

    def _clear_cache(self):
        """ Clear the cache for this node and all its children."""
        self._cache.clear()
        for child in getattr(self, "_children", []):
            child._clear_cache()




