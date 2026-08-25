from pathlib import Path
from unittest.mock import MagicMock, patch

from ansys.visor.viewer.vtk.io.dataset_to_file import dataset_to_file


class TestDatasetToFile:
    def test_creates_parent_directory_if_absent(self, tmp_path):
        """Verify that dataset_to_file creates parent directory if is absent."""
        dest = tmp_path / "subdir" / "snap.vtkhdf"
        mock_writer = MagicMock()
        with patch("ansys.visor.viewer.vtk.io.dataset_to_file.vtkHDFWriter", return_value=mock_writer):
            dataset_to_file(dest, MagicMock())
        assert dest.parent.exists()

    def test_calls_writer_with_correct_filename_and_input(self, tmp_path):
        """Verify that dataset_to_file calls writer with correct filename and input."""
        dest = tmp_path / "snap.vtkhdf"
        dataset = MagicMock()
        mock_writer = MagicMock()
        with patch("ansys.visor.viewer.vtk.io.dataset_to_file.vtkHDFWriter", return_value=mock_writer):
            dataset_to_file(dest, dataset)
        mock_writer.SetFileName.assert_called_once_with(str(dest))
        mock_writer.SetInputData.assert_called_once_with(dataset)
        mock_writer.Write.assert_called_once()

    def test_returns_path_object(self, tmp_path):
        """Verify that dataset_to_file returns path object."""
        dest = tmp_path / "snap.vtkhdf"
        mock_writer = MagicMock()
        with patch("ansys.visor.viewer.vtk.io.dataset_to_file.vtkHDFWriter", return_value=mock_writer):
            result = dataset_to_file(dest, MagicMock())
        assert isinstance(result, Path)
        assert result == dest

    def test_accepts_string_path(self, tmp_path):
        """Verify that dataset_to_file accepts string path."""
        dest = tmp_path / "snap.vtkhdf"
        mock_writer = MagicMock()
        with patch("ansys.visor.viewer.vtk.io.dataset_to_file.vtkHDFWriter", return_value=mock_writer):
            result = dataset_to_file(str(dest), MagicMock())
        assert result == dest

