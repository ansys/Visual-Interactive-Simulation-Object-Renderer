# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

import numpy as np
import pytest

from ansys.visor.viewer import Metadata
from tests.helpers.utils.mesh_creator import MeshCreator

# Random mesh will be created before the visor_server starts to feed it as a parametrized
# value to the fixture.

# Define the names and number of components for the vector variable to be updated
TEST_VECTOR_NAME = "test_vector"
NUM_COMPONENTS = 3
TEST_SCALAR_NAME = "test_scalar"
SCALE_FACTOR = 5.0

# Create initial mesh with variables
# Set up first mesh
data_obj1 = MeshCreator(xoffset=-2)

# Add the variables
data_obj1.add_random_variable(
    TEST_VECTOR_NAME, NUM_COMPONENTS, scale_factor=SCALE_FACTOR
)
data_obj1.add_random_variable(TEST_SCALAR_NAME, 1, scale_factor=SCALE_FACTOR)

# Retrieve the polydata object
polydata1 = data_obj1.polydata

ASSETS = {
    "asset_path": polydata1,
    "metadata_path": Metadata(name="sphere_1", unit="m"),
}


@pytest.mark.parametrize("visor_asset_spec", [ASSETS], indirect=True)
@pytest.mark.regression
def test_update_variables(visor_server, request):
    """Test updating_variables() method in a Visor scene

    Creates a random mesh with point variables, loads it into Visor,
    updates the variable values to constant values, and verifies the update took place.

    Test replicates example in documentation:
    https://visor.docs.pyansys.com/version/dev/examples/03-updating-visor-scene
    """

    visor = visor_server
    # Print dataset metadata and get the dataset ID
    datasets = visor.list_datasets()

    # Get the dataset ID - there is only one loaded.
    dataset_id = list(datasets.keys())[0]

    # Get the variable data arrays from Visor (returns per-part entries)
    variable_data1 = visor.list_variables(dataset_id)
    # flatten to list of individual variables for easier assertions
    flat_vars1 = [v for part in variable_data1 for v in getattr(part, "variables", [])]

    # Now update the variable values in Visor

    # Create the new variables for the test point dataArrays:
    # a list of random values between 0 and 10
    constant_values = [1.0, 2.0, 3.5]
    new_vector_values = data_obj1.get_constant_values(NUM_COMPONENTS, constant_values)
    new_scalar_values = data_obj1.get_constant_values(1, [5.0])

    # Compile a dict with the vector variable metadtata + updated values
    vector_update_info = {
        "type": "point",
        "name": TEST_VECTOR_NAME,
        "num_components": NUM_COMPONENTS,
        "data": new_vector_values,
    }
    # Compile a dict with the scalar variable metadtata + updated values
    scalar_update_info = {
        "type": "point",
        "name": TEST_SCALAR_NAME,
        "num_components": 1,
        "data": new_scalar_values,
    }

    # Run the actual update command
    visor.update_variables(dataset_id, [vector_update_info, scalar_update_info])
    variable_data2 = visor.list_variables(dataset_id)
    flat_vars2 = [v for part in variable_data2 for v in getattr(part, "variables", [])]

    assert flat_vars1 != flat_vars2, "Failed to update variable data."

    # Find the updated vector variable by name and verify its ranges reflect the constant values
    updated_vector = [v for v in flat_vars2 if getattr(v, "name", None) == TEST_VECTOR_NAME]
    assert len(updated_vector) >= 1, f"Updated vector {TEST_VECTOR_NAME} not found in variables"
    updated_constant_data = updated_vector[0].ranges
    for i in range(len(updated_constant_data)):
        assert (
            float(np.mean(updated_constant_data[i])) == constant_values[i]
        ), f"Failed to update variable {TEST_VECTOR_NAME}. {float(np.mean(updated_constant_data[i]))}!={constant_values[i]}"
