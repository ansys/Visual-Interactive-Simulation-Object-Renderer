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
from ansys.visor.viewer.core.visor_enums import VisorVtkVariableType
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
    # Per-part visual mutations
    #
    # These bodies live here rather than on the renderer because each is
    # more than one VTK call, and the colour-variable body additionally
    # reads a pipeline-internal object (``base_algorithm``).  Identity
    # resolution (node id -> pipeline) and the miss branch stay on the
    # renderer, which is the only holder of the id -> pipeline map.
    # ------------------------------------------------------------------

    def set_selected(self, selected: bool, diffuse_rgb: list[float]) -> None:
        """Apply or remove the selection highlight on this part.

        Parameters
        ----------
        selected:
            Target state.  Absolute, never a toggle.
        diffuse_rgb:
            The part's diffuse colour, re-applied unconditionally on both
            branches -- selection changes the ambient/diffuse lighting
            terms, it does not replace the part's colour.
        """
        prop = self.actor.GetProperty()
        if selected:
            prop.SetAmbientColor(0 / 255, 62 / 255, 111 / 255)
            prop.SetDiffuse(0.5)
            prop.SetAmbient(0.5)
        else:
            prop.SetDiffuse(1.0)
            prop.SetAmbient(0.0)
        prop.SetDiffuseColor(*diffuse_rgb)

    def set_color_variable(
        self,
        association: VisorVtkVariableType,
        array_name: str,
        component: int,
        min_val: float,
        max_val: float,
    ) -> None:
        """Colour this part by a scalar array, over an explicit range.

        Configures the mapper only.  No lookup table is authored here: the
        table belongs to a later story, and until then a reference resolves
        against the client-held default table.

        ``association`` is compared by identity against
        :class:`VisorVtkVariableType`; it is never parsed, upper-cased or
        string-compared.  A value that is neither member, and an array name
        that does not exist on the input, are both logged no-ops that
        mutate nothing.
        """
        in_data = self.base_algorithm.GetInput()
        if association is VisorVtkVariableType.POINT:
            field = in_data.GetPointData()
        elif association is VisorVtkVariableType.CELL:
            field = in_data.GetCellData()
        else:
            logger.warning(
                "set_color_variable: association %r is not a VisorVtkVariableType; "
                "skipping.",
                association,
            )
            return

        if field.GetArray(array_name) is None:
            logger.warning(
                "set_color_variable: array %r not found for association %s; skipping.",
                array_name,
                association,
            )
            return

        mapper = self.mapper
        if association is VisorVtkVariableType.POINT:
            mapper.SetScalarModeToUsePointFieldData()
        else:
            mapper.SetScalarModeToUseCellFieldData()
        mapper.SelectColorArray(array_name)
        mapper.SetArrayComponent(component)
        mapper.SetScalarRange(min_val, max_val)
        mapper.SetColorModeToMapScalars()
        mapper.SetScalarVisibility(True)
        # Makes the mapper honour the range set above rather than the
        # lookup table's own range.
        mapper.SetUseLookupTableScalarRange(0)

    def clear_color_variable(self) -> None:
        """Stop colouring this part by a scalar array.

        One call.  Does not touch a lookup table and does not restore a
        diffuse colour -- the part's colour is whatever was last applied
        to it.
        """
        self.mapper.SetScalarVisibility(False)

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

