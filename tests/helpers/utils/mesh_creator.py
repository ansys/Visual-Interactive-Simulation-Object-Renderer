# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

from typing import List

import numpy as np
from vtk import vtkFloatArray, vtkSphereSource


class MeshCreator:
    """
    Helper class to create a vtkPolyData mesh (sphere) and add variables to it.

    Parameters
    ----------
    scale : float
        Scale (radius) of the sphere.
    xoffset : float
        Offset of the sphere center along the x-axis.

    Attributes
    ----------
    polydata : vtkPolyData
        The generated sphere mesh.
    num_points : int
        Number of points in the mesh.

    """
    def __init__(self, scale=1.0, xoffset=0.0):
        self.scale = scale
        self.xoffset = xoffset
        self.polydata = self._generate_polydata()

    @property
    def num_points(self):
        return self.polydata.GetNumberOfPoints()

    def add_variable(self, name, num_components, values):
        vals = np.asarray(values, dtype=np.float32)

        # Enforce correct shape
        if vals.shape != (self.num_points, num_components):
            raise ValueError(
                f"Expected shape ({self.num_points}, {num_components}), "
                f"got {vals.shape}"
            )

        arr = vtkFloatArray()
        arr.SetName(name)
        arr.SetNumberOfComponents(num_components)
        arr.SetNumberOfTuples(self.num_points)

        for i in range(self.num_points):
            if num_components == 1:
                arr.SetValue(i, float(vals[i, 0]))
            else:
                row = vals[i, :].tolist()
                arr.SetTuple(i, row)
        self.polydata.GetPointData().AddArray(arr)
        self.polydata.GetPointData().SetActiveScalars(name)

    def add_constant_variable(self, name: str, num_components: int, constant_values: List[float]):
        values = self.get_constant_values(num_components, constant_values)
        self.add_variable(name, num_components, values)

    def add_random_variable(self, name: str, num_components: int, scale_factor=1.0):
        values = self.get_random_values(num_components, scale_factor=scale_factor)
        self.add_variable(name, num_components, values)

    def get_constant_values(self, num_components: int, constant_values: List[float]) -> np.ndarray:
        """
        Create an array with a different constant value per component.
        The values list is used to set the constant value across all points for the corresponding component.
        """
        if len(constant_values) != num_components:
            raise ValueError("constant_values list length needs to equal num_components")

        # Numpy array of shape (self.num_points, num_components)
        arr = np.empty((self.num_points, num_components), dtype=np.float32)
        for i in range(0, num_components):
            arr[:, i] = float(constant_values[i])
        return arr

    def get_random_values(self, num_components=1, scale_factor=1.0) -> np.ndarray:
        """
        Create an array with random variables for each component, from 0 to scale_factor.
        """
        rng = np.random.default_rng() # Use a seed for reproducibility
        return (scale_factor * rng.random((self.num_points, num_components), dtype=np.float32))

    def _generate_polydata(self):
        source = vtkSphereSource()
        source.SetRadius(self.scale)
        source.SetThetaResolution(32)
        source.SetPhiResolution(32)
        source.SetCenter(self.xoffset, 0, 0)
        source.Update()
        return source.GetOutput()