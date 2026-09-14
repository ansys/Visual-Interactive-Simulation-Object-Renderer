"""
.. _ref_launch_visor:

Launch VISOR
============

To launch the VISOR visualization, instantiate the viewer and call the ``start`` method
with a file name or a ``vtkDataSet`` object.

This example shows how to run VISOR in a Jupyter notebook.  It creates a VISOR visualizer
on the default port (8081) and views it in an iframe.

If you are not using a Jupyter notebook, the VISOR server is viewable in a new browser tab.

Note that the VISOR server runs in a background threads, so the main thread is free to
continue executing other code.
"""

###########################################################
from IPython.display import IFrame

from ansys.visor.viewer import Visor

# Define paths to two different assets
asset_path1 = '../../examples/assets/vtk_scene_sphere_l2_b3_r32_v3_c1_z0.vtm'
asset_path2 = '../../examples/assets/tensors9.vtp'

# Instantiate a VISOR visualizer on port 8081.
visor = Visor(url='http://localhost:8081')

# Start the visualizer server in the background using the first asset
visor.start(asset_path1)

# VISOR starts a server and opens a browser window to visualize the data.
# The server runs in the background until visualizer.stop() is called or the main process is stopped.
# In a Jupyter notebook, the VISOR server stops when the kernel is restarted or stopped.

# View the visualizer inline (if in a Jupyter Notebook)
IFrame(src='http://localhost:8081', width=1200, height=600)

# Update the visualizer with the second asset
visor.update(asset_path2)

# Print information about the visualizer instance
visor.info()
# {'app_name': 'VISOR Viewer',
#  'host': 'localhost',
#  'port': 8081,
#  'standalone': True,
#  'file_input_path': '../../examples/assets/tensors9.vtp',
#  'metadata': None}

# Stop the first VISOR instance
visor.stop()




