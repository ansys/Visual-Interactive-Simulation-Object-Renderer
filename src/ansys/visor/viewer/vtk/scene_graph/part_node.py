"""Scene-graph leaf node that owns a raw VTK dataset and scene metadata."""

from typing import List

from typing_extensions import Self
from vtkmodules.util.data_model import PolyData, UnstructuredGrid
from vtkmodules.vtkCommonCore import vtkInformation
from vtkmodules.vtkCommonDataModel import vtkDataObject, vtkPolyData, vtkUnstructuredGrid

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.core.visor_enums import VisorNodeType
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger
from ansys.visor.viewer.models.runtime.vtk.scene_graph_node_info import SceneGraphNodeInfo
from ansys.visor.viewer.vtk.scene_graph.base_node import VisorSceneGraphNode
from ansys.visor.viewer.vtk.variables.visor_variables import VisorVariables

logger = VisorDefaultLogger(__name__)


class VisorSceneGraphPartNode(VisorSceneGraphNode):
    """Leaf scene-graph node holding a single renderable dataset.

    Owns:
      * the raw ``vtkDataObject``
      * scene-description metadata (name, VTK dataset type, bounds,
        variable-array metadata)

    Does NOT own any VTK pipeline objects. The renderer looks up the
    matching :class:`VtkNodePipeline` by :attr:`id`.
    """

    def __init__(
        self,
        parent: Self,
        node_metadata: vtkInformation | None = None,
        dataset: vtkDataObject | vtkUnstructuredGrid | vtkPolyData | None = None,
        root_node: Self | None = None,
    ):
        """Initialize the part node."""
        super().__init__(parent, node_metadata, dataset, root_node)

    def _post_init(
        self,
        parent: Self,
        node_metadata: vtkInformation | None = None,
        dataset: vtkDataObject | vtkUnstructuredGrid | vtkPolyData | None = None,
        root_node: Self | None = None,
    ):
        """Custom initialization for the part node."""
        self._set_name(node_metadata)
        self._node_type = VisorNodeType.PART

        # Raw dataset -- owned here. Pipeline objects live in VtkNodePipeline.
        self._dataset: vtkDataObject = dataset

        self._vtk_dataset_type: str = self._get_vtk_dataset_type(dataset)
        self._bounds: list[float] = self._get_bounds(dataset)
        self._variable_metadata: VisorVariables = self._get_variable_metadata(dataset)

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def dataset(self) -> vtkDataObject:
        """Return the raw VTK dataset."""
        return self._dataset

    @property
    def data_arrays(self) -> List[dict]:
        """Return the variable-array metadata for this part."""
        return self._variable_metadata.list_info()

    @property
    def state(self) -> SceneGraphNodeInfo:
        """Return the scene-graph node info for this part.

        Structural fields only. The base ``state`` derives ``isActorNode``
        from :attr:`is_part_node`, which is True for a part node -- the wire
        payload stays byte-identical to what the legacy actor node produced.
        """
        state_obj = super().state
        state_obj.data_arrays = self.data_arrays
        state_obj.diffuse_color = VisorColors.DefaultMeshColor
        return state_obj

    # ------------------------------------------------------------------
    # Variable metadata refresh
    # ------------------------------------------------------------------

    def refresh_variable_metadata(self) -> None:
        """Refresh cached variable metadata from the current dataset.

        Does not touch any VTK pipeline object. Use after an in-place
        variable data update where the pipeline topology has not changed.
        """
        self._variable_metadata = self._get_variable_metadata(self._dataset)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_vtk_dataset_type(self, dataset: vtkDataObject) -> str:
        if isinstance(dataset, (UnstructuredGrid, vtkUnstructuredGrid)):
            return "vtkUnstructuredGrid"
        elif isinstance(dataset, (PolyData, vtkPolyData)):
            return "vtkPolyData"
        else:
            msg = f"node type not yet supported: {type(dataset)}"
            logger.error(msg)
            raise RuntimeError(msg)

    def _get_bounds(self, dataset: vtkDataObject) -> list[float]:
        return list(dataset.GetBounds())

    def _get_variable_metadata(self, dataset: vtkDataObject) -> VisorVariables:
        return VisorVariables(dataset)

