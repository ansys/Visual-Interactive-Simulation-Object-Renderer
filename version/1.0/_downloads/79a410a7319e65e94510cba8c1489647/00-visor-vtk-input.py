"""
.. _ref_launch_visor_with_vtk_object:


Launch VISOR with a VTK object
==============================

To launch the VISOR visualization, instantiate the viewer and call the ``start`` method
with a ``vtkDataSet`` object.

This example shows how to create a simple cube using VTK and visualize it using VISOR.

"""

from IPython.display import IFrame
from vtk import vtkCubeSource

from ansys.visor.viewer import Visor


# Create a cube source and get the output as a vtkPolyData object
def get_cube(x: float, y: float, z: float):
    cube_source = vtkCubeSource()
    cube_source.SetXLength(x)
    cube_source.SetYLength(y)
    cube_source.SetZLength(z)
    cube_source.Update()
    return cube_source.GetOutput()


cube = get_cube(1.0, 2.0, 3.0)
# Visualize the cube using VISOR
visualizer = Visor()
visualizer.start(input=cube)

# VISOR starts a server and opens a browser window to visualize the data.
# The server runs in the background until visualizer.stop() is called or the main process is stopped.
# In a Jupyter notebook, the VISOR server stops when the kernel is restarted or stopped.

# View the visualizer inline (if in a Jupyter notebook)
IFrame(src='http://localhost:8081', width=1200, height=600)

# Update the server by passing a modified vtkDataSet object to the VISOR instance's update method
cube = get_cube(1.0, 2.0, 3.0)
visualizer.update(input=cube)

# To stop the server, call the stop method
visualizer.stop()


