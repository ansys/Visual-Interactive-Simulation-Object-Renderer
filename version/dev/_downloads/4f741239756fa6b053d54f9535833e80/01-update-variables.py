"""
.. _ref_update_variables:


Update variables in existing datasets
=====================================

You can update the variables of existing datasets in a VISOR scene without reloading the entire dataset.

The ``list_variables`` and ``update_variables`` methods of the VISOR visualizer and
the corresponding APIs in the VISOR service expose this feature.

This example shows how to list the variables of an existing dataset in a VISOR scene
and update one of the variables with new data.

.. note::

   This feature is only available for ``vtkUnstructuredGrid`` and ``vtkPolyData`` dataset types.
   It is not supported for ``vtkMultiBlockDataSet`` or ``vtkMultiPieceDataSet`` dataset types.

"""
##########################################
# Import modules and define helper classes
##########################################

from typing import List

import numpy as np
from vtk import vtkFloatArray, vtkSphereSource

from ansys.visor.viewer import Metadata, Visor


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
        Generated sphere mesh.
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
        Create an array with random variables for each component, from 0 to the scale factor value.
        """
        rng = np.random.default_rng()
        return (scale_factor * rng.random((self.num_points, num_components), dtype=np.float32))

    def _generate_polydata(self):
        source = vtkSphereSource()
        source.SetRadius(self.scale)
        source.SetThetaResolution(32)
        source.SetPhiResolution(32)
        source.SetCenter(self.xoffset, 0, 0)
        source.Update()
        return source.GetOutput()

###############################
# Set up the mesh and variables
###############################

# Define the names and number of components for the vector variable to update
TEST_VECTOR_NAME = "test_vector"
NUM_COMPONENTS = 3
TEST_SCALAR_NAME = "test_scalar"
SCALE_FACTOR = 5.0

# Create initial mesh with variables
# Set up first mesh
data_obj1 = MeshCreator(xoffset=-2)

# Add the variables
data_obj1.add_random_variable(TEST_VECTOR_NAME, NUM_COMPONENTS, scale_factor=SCALE_FACTOR)
data_obj1.add_random_variable(TEST_SCALAR_NAME, 1, scale_factor=SCALE_FACTOR)

# Retrieve the polydata object
polydata1 = data_obj1.polydata

############################
# Initialize and start VISOR
############################

vis = Visor()
vis.start(polydata1, metadata=Metadata(name="sphere_1", unit="m"))

######################################
# List datasets and get dataset the ID
######################################

# Print dataset metadata and get the dataset ID
datasets = vis.list_datasets()
# print(json.dumps(datasets, indent=4))
# Get the dataset ID - there is only one loaded.
dataset_id = list(datasets.keys())[0]
print(f"dataset ID: {dataset_id}")

##################################################
# Create new variable data and compile the payload
##################################################

# Create the new variables for the test point dataArrays:
# a list of random values between 0 and 10
new_vector_values = data_obj1.get_constant_values(NUM_COMPONENTS, [1.0, 2.0, 3.5])
new_scalar_values = data_obj1.get_constant_values(1, [5.0])

# Compile a dict with the vector variable metadata and updated values
vector_update_info = {
    "type": "point",
    "name": TEST_VECTOR_NAME,
    "num_components": NUM_COMPONENTS,
    "data": new_vector_values
}
# Compile a dict with the scalar variable metadata and updated values
scalar_update_info = {
    "type": "point",
    "name": TEST_SCALAR_NAME,
    "num_components": 1,
    "data": new_scalar_values
}

###################################
# Run the update variable operation
###################################

# Run the actual update command
vis.update_variables(dataset_id, [vector_update_info, scalar_update_info])

# The VISOR scene should now reflect the updated variable values.

# Stop the visualizer
vis.stop()

################
# End of example
################

