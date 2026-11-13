"""
.. _ref_launch_two_visor_viewers:

Launch two concurrent VISOR visualizers
=======================================

To launch the VISOR visualization, instantiate the viewer and call the ``start`` method
with a file name or a ``vtkDataSet`` object.

This example shows how to run VISOR in a Jupyter notebook. It creates two separate
VISOR visualizers on two distinct ports (8081, 8082) and views them in iframes.

Note that VISOR servers run in background threads, so the main thread is free to
continue executing other code.
"""

###########################################################
from IPython.display import IFrame

from ansys.visor.viewer import Visor

# Define paths to two different assets
asset_path1 = '../../examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z0.vtm'
asset_path2 = '../../examples/assets/tensors9.vtp'

# Instantiate a VISOR visualizer on port 8081.
visor1 = Visor(url='http://localhost:8081')

# Start the visualizer server in the background using the first asset
visor1.start(asset_path1)

# View the visualizer inline (if in a Jupyter notebook)
IFrame(src='http://localhost:8081', width=1200, height=600)

# Update the visualizer with the second asset
visor1.update(asset_path2)

# Initialize a second VISOR visualizer on port 8082
visor2 = Visor(url='http://localhost:8082')

# Start the second visualizer server in the background
visor2.start(asset_path1)
# IFrame(src='http://localhost:8082', width=1200, height=600) # Uncomment if running in a Jupyter notebook

# Stop the first VISOR instance
visor1.stop()

# Stop the second VISOR instance
visor2.stop()
