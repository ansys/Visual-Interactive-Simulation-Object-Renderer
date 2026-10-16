.. _quick-start:

Quick start
###########

Use the VISOR Python API to quickly create and run a minimal SAF-based solution.

#. Run the following code to create a VISOR instance and load a VTM file:

   .. code-block:: python

      from ansys.visor.viewer import Visor

      an_input_file = "your_file.vtm"
      visualizer = Visor(
          url="http://localhost:8888"
      )  # optional; default is "http://localhost:8081"
      visualizer.start(input=an_input_file)

#. Open the VISOR standalone app at the specified URL.
   This example uses http://localhost:8888.

The following image shows a loaded VTM file. VISOR supports both VTM and VTK files.

.. image:: /_static/visor_standalone_many_blocks_localhost_8081_2025-07030.png
   :alt: VISOR standalone app with many blocks in the loaded file
   :align: center
