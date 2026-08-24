"""Helper function to write a VTK dataset to a file."""

from pathlib import Path

from vtkmodules.vtkCommonDataModel import vtkDataObject
from vtkmodules.vtkIOHDF import vtkHDFWriter

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

logger = VisorDefaultLogger(__name__)


def dataset_to_file(path: str | Path, dataset: vtkDataObject) -> Path:
    """Write *dataset* to disk as a VTKHDF file at *path*.

    The parent directory is created if it does not already exist.

    Args:
        path: Destination file path (should end with ``.vtkhdf``).
        dataset: The VTK data object to serialise.

    Returns:
        The :class:`pathlib.Path` of the file that was written.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    writer = vtkHDFWriter()
    writer.SetFileName(str(dest))
    writer.SetInputData(dataset)
    writer.Write()


    logger.debug(f"Dataset written to {dest}")
    return dest
