.. _visor-input-format:

Supply an input file
####################

You can use VTK and VTM files as input.
VISOR reads the following VTK data types:

* ``vtkMultiBlockDataSet``
* ``vtkMultiPieceDataSet``
* ``vtkUnstructuredGrid``
* ``vtkPolyData``

Supported inputs for the VISOR HTTP service
###########################################

When you use the VISOR HTTP service, the ``/start`` and ``/update`` endpoints accept a ``file_path`` parameter
that specifies the input file path. The file path must be accessible from the machine where the VISOR
service is running.

You can also use the ``visor-cli`` tool, which calls the VISOR HTTP service. The ``/start`` and ``/update``
endpoints accept a ``--file-path`` argument to specify the input file.

The HTTP API does not support streaming file content directly in the request body.

The following examples show a ``/start`` payload and the equivalent VISOR CLI command:

.. tab-set::

    .. tab-item:: Start payload

        .. code-block:: json

           {
               "file_path": "path/to/your_file.vtm",
               "metadata": {
                   "name": "My Visualization",
                   "unit": "cm"
               },
               "timeout": 60
           }

    .. tab-item:: VISOR CLI command

        .. code-block:: bash

           visor-cli start --file-path path/to/your_file.vtm --name "My Visualization" --unit "cm"


Supported inputs for the VISOR Python API
#########################################

You can use the VISOR Python API with input files and in-memory VTK objects.

To provide an input file path, pass a string to the ``input`` parameter of the ``Visor`` class:

.. code-block:: python

   from ansys.visor.viewer import Visor

   an_input_file = "path/to/your_file.vtm"

   visualizer = Visor()
   visualizer.start(input=an_input_file)
