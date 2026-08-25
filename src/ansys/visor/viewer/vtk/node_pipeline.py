"""
VtkNodePipeline
===============

A self-contained VTK rendering pipeline for a single scene-graph leaf node.

Owns the three VTK objects that turn a raw dataset into something the
renderer can display:

* ``base_algorithm`` -- geometry extraction (``vtkGeometryFilter`` for
  unstructured grids; ``vtkAppendPolyData`` for poly data).
* ``mapper``         -- ``vtkPolyDataMapper`` connected to the algorithm output.
* ``actor``          -- ``vtkActor`` connected to the mapper.

Created when a leaf node is registered with the renderer and destroyed when
that node is deregistered. The scene-graph node itself owns only the raw
dataset and metadata; no VTK pipeline objects live on it.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from vtkmodules.vtkCommonDataModel import vtkDataObject, vtkPlane, vtkPolyData, vtkUnstructuredGrid
from vtkmodules.vtkCommonExecutionModel import vtkPolyDataAlgorithm
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

from ansys.visor.viewer.core.visor_colors import VisorColors
from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)


@dataclass
class VtkNodePipeline:
    """The VTK rendering pipeline for one scene-graph leaf (part) node.

    Attributes
    ----------
    actor:
        The ``vtkActor`` added to the renderer.
    mapper:
        The ``vtkPolyDataMapper`` driving the actor.
    base_algorithm:
        The geometry-extraction algorithm whose output feeds the mapper.
    """

    actor: vtkActor
    mapper: vtkPolyDataMapper
    base_algorithm: vtkPolyDataAlgorithm

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_dataset(cls, dataset: vtkDataObject) -> "VtkNodePipeline":
        """Build a complete pipeline from ``dataset``.

        Parameters
        ----------
        dataset:
            A ``vtkUnstructuredGrid`` or ``vtkPolyData`` -- the raw dataset
            owned by the scene-graph leaf node.
        """
        base_algorithm = cls._create_base_algorithm(dataset)

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(base_algorithm.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetDiffuseColor(VisorColors.DefaultMeshColor)
        actor.GetProperty().SetInterpolation(0)  # flat shading

        return cls(actor=actor, mapper=mapper, base_algorithm=base_algorithm)


    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def set_clipping_plane(self, plane: Optional[vtkPlane]) -> None:
        """Replace the mapper's clipping plane with ``plane`` (clear if ``None``)."""
        self.mapper.RemoveAllClippingPlanes()
        if plane is not None:
            self.mapper.AddClippingPlane(plane)

    def update_input(
        self,
        algorithm_filter: Optional[Callable[[vtkPolyDataAlgorithm], vtkPolyDataAlgorithm]] = None,
    ) -> None:
        """Reconnect the mapper to a new algorithm output.

        Parameters
        ----------
        algorithm_filter:
            Optional callable that wraps ``base_algorithm`` in an additional
            filter and returns the new downstream algorithm. When ``None``,
            the mapper is reconnected directly to ``base_algorithm``.
        """
        algorithm = self.base_algorithm
        if algorithm_filter is not None:
            algorithm = algorithm_filter(algorithm)
        self.mapper.SetInputConnection(algorithm.GetOutputPort())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _create_base_algorithm(dataset: vtkDataObject) -> vtkPolyDataAlgorithm:
        if isinstance(dataset, vtkUnstructuredGrid):
            f = vtkGeometryFilter()
            f.SetNonlinearSubdivisionLevel(0)
            f.SetInputData(dataset)
            return f
        elif isinstance(dataset, vtkPolyData):
            f = vtkAppendPolyData()
            f.SetInputData(dataset)
            return f
        else:
            msg = f"node type not yet supported: {type(dataset)}"
            logger.error(msg)
            raise RuntimeError(msg)

