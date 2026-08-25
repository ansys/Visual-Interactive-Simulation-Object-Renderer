"""Helper function to read a VTK dataset from a file and return it as a vtkDataSet or vtkCompositeDataSet."""

import os

from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet, vtkDataObject, vtkDataSet
from vtkmodules.vtkIOHDF import vtkHDFReader
from vtkmodules.vtkIOXML import (
    vtkXMLMultiBlockDataReader,
    vtkXMLPolyDataReader,
    vtkXMLReader,
    vtkXMLUnstructuredGridReader,
)

from ansys.visor.viewer.core.visor_logging import VisorDefaultLogger

"""Logging configuration"""
logger = VisorDefaultLogger(__name__)


def file_to_dataset(file_path: str) -> vtkDataSet | vtkCompositeDataSet:
    """"""
    try:
        logger.debug(f"Beginning creating dataset from file: {file_path}")
        if not os.path.exists(file_path):
            msg = f"file does not exist: {file_path}"
            logger.error(msg)
            raise RuntimeError(msg)
        # make file_path lowercase so extension testing is case-insensitive
        filename: str = os.path.basename(file_path).lower()
        extension: str = os.path.splitext(filename)[1][1:]
        reader: vtkXMLReader | vtkHDFReader
        is_hdf = False
        if extension == "vtu":
            """"""
            logger.debug(f"vtkUnstructuredGrid detected: {file_path}")
            reader = vtkXMLUnstructuredGridReader()
            reader.SetFileName(file_path)
        elif extension == "vtp":
            """"""
            logger.debug(f"vtkPolyData detected: {file_path}")
            reader = vtkXMLPolyDataReader()
            reader.SetFileName(file_path)
        elif extension == "vtm":
            """"""
            logger.debug(f"vtkMultiBlockDataSet detected: {file_path}")
            reader = vtkXMLMultiBlockDataReader()
            reader.SetFileName(file_path)
        elif extension == "vtkhdf":
            """"""
            logger.debug(f"VTKHDF dataset detected: {file_path}")
            reader = vtkHDFReader()
            reader.SetFileName(file_path)
            is_hdf = True
        else:
            """"""
            msg = f"Unsupported file: {file_path}"
            logger.error(msg)
            raise RuntimeError(msg)
        reader.Update()
        output: vtkDataSet | vtkCompositeDataSet = reader.GetOutput()
        if is_hdf and not isinstance(output, (vtkDataSet, vtkCompositeDataSet)):
            msg = f"VTKHDF file contains an unsupported dataset type ({type(output).__name__}): {file_path}"
            logger.error(msg)
            raise RuntimeError(msg)

        # Deep-copy so we own the data independently of the reader.
        copy: vtkDataObject = output.NewInstance()
        copy.DeepCopy(output)

        # Release the reader and its file handle
        del reader

        logger.debug(f"Finished creating dataset from file: {file_path}")
        return copy
    except RuntimeError as e:
        msg = f"could not create dataset from file: {e}"
        logger.error(msg)
        raise RuntimeError(msg)
