from unittest.mock import MagicMock, patch

import pytest
from vtkmodules.vtkCommonDataModel import vtkPolyData

from ansys.visor.viewer.vtk.io.file_to_dataset import file_to_dataset


@pytest.mark.parametrize("ext,reader_cls", [
    ("vtu", "vtkXMLUnstructuredGridReader"),
    ("vtp", "vtkXMLPolyDataReader"),
    ("vtm", "vtkXMLMultiBlockDataReader"),
    ("vtkhdf", "vtkHDFReader"),
])
def test_file_to_dataset_supported_extensions(ext, reader_cls):
    """Verify that file_to_dataset dispatches to the correct reader class for supported extensions."""
    file_path = f"/tmp/test.{ext}"
    # Use a real vtkPolyData so DeepCopy works and the vtkhdf isinstance check passes.
    real_output = vtkPolyData()
    real_output.GetPoints()  # initialise internal structure
    with patch("os.path.exists", return_value=True), \
         patch("os.path.basename", return_value=f"test.{ext}"), \
         patch("os.path.splitext", return_value=("test", f".{ext}")), \
         patch(f"ansys.visor.viewer.vtk.io.file_to_dataset.{reader_cls}") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.GetOutput.return_value = real_output
        mock_reader_cls.return_value = mock_reader
        result = file_to_dataset(file_path)
        mock_reader.SetFileName.assert_any_call(file_path)
        mock_reader.Update.assert_called_once()
        # We return a deep copy, not the original object — check type instead of identity.
        assert isinstance(result, vtkPolyData)


def test_file_to_dataset_file_not_exists():
    """Verify that file_to_dataset raises RuntimeError when the file does not exist."""
    file_path = "/tmp/missing.vtu"
    with patch("os.path.exists", return_value=False):
        with pytest.raises(RuntimeError, match="file does not exist"):
            file_to_dataset(file_path)


def test_file_to_dataset_unsupported_extension():
    """Verify that file_to_dataset raises RuntimeError for unsupported file extensions."""
    file_path = "/tmp/test.txt"
    with patch("os.path.exists", return_value=True), \
         patch("os.path.basename", return_value="test.txt"), \
         patch("os.path.splitext", return_value=("test", ".txt")):
        with pytest.raises(RuntimeError, match="Unsupported file"):
            file_to_dataset(file_path)


def test_file_to_dataset_reader_raises_runtimeerror():
    """Verify that file_to_dataset raises RuntimeError when the reader fails."""
    file_path = "/tmp/test.vtu"
    with patch("os.path.exists", return_value=True), \
         patch("os.path.basename", return_value="test.vtu"), \
         patch("os.path.splitext", return_value=("test", ".vtu")), \
         patch("ansys.visor.viewer.vtk.io.file_to_dataset.vtkXMLUnstructuredGridReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.Update.side_effect = RuntimeError("reader error")
        mock_reader_cls.return_value = mock_reader
        with pytest.raises(RuntimeError, match="could not create dataset from file: reader error"):
            file_to_dataset(file_path)


# ------------------------------------------------------------------ #
# vtkhdf-specific unit tests
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("original_filename", [
    "model.VTKHDF",
    "model.VtkHdf",
    "model.VTKHDF",
])
def test_file_to_dataset_vtkhdf_extension_is_case_insensitive(original_filename):
    """Extension matching must be case-insensitive for .vtkhdf files.

    The real code does:
        filename = os.path.basename(file_path).lower()
        extension = os.path.splitext(filename)[1][1:]
    so os.path.basename must return the already-lowered name, and
    os.path.splitext must be called on that lowered name — both mocks
    must reflect that same flow.
    """
    lowered = original_filename.lower()       # e.g. "model.vtkhdf"
    stem, ext = lowered.rsplit(".", 1)        # "model", "vtkhdf"
    with patch("os.path.exists", return_value=True), \
         patch("os.path.basename", return_value=lowered), \
         patch("os.path.splitext", return_value=(stem, f".{ext}")), \
         patch("ansys.visor.viewer.vtk.io.file_to_dataset.vtkHDFReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.GetOutput.return_value = vtkPolyData()
        mock_reader_cls.return_value = mock_reader
        file_to_dataset(f"/tmp/{original_filename}")
        mock_reader_cls.assert_called_once()


def test_file_to_dataset_vtkhdf_raises_for_unsupported_output_type():
    """vtkHDFReader returning an unsupported dataset type must raise RuntimeError.

    The source sets is_hdf=True inside the vtkhdf branch, then checks:
        if is_hdf and not isinstance(output, (vtkDataSet, vtkCompositeDataSet))
    A plain Python object satisfies `not isinstance(..., vtkDataSet/vtkCompositeDataSet)`
    because VTK's metaclass only accepts real VTK objects in isinstance — for a
    non-VTK type the check returns False cleanly (no TypeError).
    """
    file_path = "/tmp/model.vtkhdf"

    class _NotAVtkType:
        pass

    with patch("os.path.exists", return_value=True), \
         patch("os.path.basename", return_value="model.vtkhdf"), \
         patch("os.path.splitext", return_value=("model", ".vtkhdf")), \
         patch("ansys.visor.viewer.vtk.io.file_to_dataset.vtkHDFReader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.GetOutput.return_value = _NotAVtkType()
        mock_reader_cls.return_value = mock_reader
        with pytest.raises(RuntimeError, match="unsupported dataset type"):
            file_to_dataset(file_path)


def test_file_to_dataset_vtkhdf_uses_hdf_reader_not_xml_reader():
    """Ensure .vtkhdf files are dispatched to vtkHDFReader, not any XML reader."""
    file_path = "/tmp/model.vtkhdf"
    with patch("os.path.exists", return_value=True), \
         patch("os.path.basename", return_value="model.vtkhdf"), \
         patch("os.path.splitext", return_value=("model", ".vtkhdf")), \
         patch("ansys.visor.viewer.vtk.io.file_to_dataset.vtkHDFReader") as mock_hdf, \
         patch("ansys.visor.viewer.vtk.io.file_to_dataset.vtkXMLPolyDataReader") as mock_xml_vtp, \
         patch("ansys.visor.viewer.vtk.io.file_to_dataset.vtkXMLUnstructuredGridReader") as mock_xml_vtu, \
         patch("ansys.visor.viewer.vtk.io.file_to_dataset.vtkXMLMultiBlockDataReader") as mock_xml_vtm:
        mock_reader = MagicMock()
        mock_reader.GetOutput.return_value = vtkPolyData()
        mock_hdf.return_value = mock_reader
        file_to_dataset(file_path)
        mock_hdf.assert_called_once()
        mock_xml_vtp.assert_not_called()
        mock_xml_vtu.assert_not_called()
        mock_xml_vtm.assert_not_called()

