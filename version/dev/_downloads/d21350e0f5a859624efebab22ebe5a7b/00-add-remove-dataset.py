"""
.. _ref_add_remove_dataset:


Add and remove datasets
=======================

You can add and remove datasets from an existing VISOR scene without restarting the visualizer.

This example shows how to add a new dataset to an existing VISOR scene, list all
datasets in the scene, and remove an existing dataset by its ID.

"""

from ansys.visor.viewer import Visor

# Set up example assets, which exist in the VISOR repository.
# File 1 + Metadata 1
input_file1 = "examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z0.vtm"
metadata_file1 = "examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z0.json"
# File 2 + Metadata 2
input_file2 = "examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z3.vtm"
metadata_file2 = "examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z3.json"


# Start VISOR visualizer with an initial dataset
visualizer = Visor()
visualizer.start(input=input_file1, metadata=metadata_file1)

# Add a dataset to the existing scene
print(f"Adding dataset: {input_file2} with metadata: {metadata_file2}")
visualizer.add_dataset(input="new_dataset.vtu", metadata="new_metadata.json")

# List all datasets in the current scene
datasets = visualizer.list_datasets() # returns a dictionary keyed by dataset IDs
print(f"Current datasets in the scene: {datasets}")

# Remove one of the datasets
dataset_id = list(datasets.keys())[0] # Get the first dataset ID

# Remove a dataset by its ID (assuming the ID is known, such as 1)
print(f"Removing dataset with ID: {dataset_id}")
visualizer.remove_dataset(dataset_id=dataset_id)

# Stop the visualizer
visualizer.stop()