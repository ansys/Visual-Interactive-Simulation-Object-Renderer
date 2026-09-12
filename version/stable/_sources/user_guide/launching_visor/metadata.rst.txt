.. _visor-metadata:

Use metadata
############

VISOR supports an optional ``metadata`` argument in start and update requests.
Providing metadata is recommended for improved visualization context.

The ``metadata`` argument can include the following fields:

- ``name``: String representing the name of the dataset or visualization.
- ``unit``: String representing the unit of measurement for the dataset (for example, ``"cm"``, ``"m"``,
  or ``"inches"``).
- ``state``: Optional dictionary that can include initial per-part values. Only the initial opacity
  is supported as a per-part property. The structure of the state dictionary is as follows:
  This information is useful for understanding the scale of the data and is displayed in the VISOR user interface.
- ``state``: Optional dictionary that can include initial per-part values. Only the initial opacity
  is supported as a per-part property. The structure of the state dictionary is as follows:

  - ``parts``: Dictionary where keys are part names (strings) and values are dictionaries with properties.
  - ``opacity``: Float between 0.0 (fully transparent) and 1.0 (fully opaque) representing the initial opacity
    of the part.

VISOR HTTP API
~~~~~~~~~~~~~~

When using the VISOR HTTP service, the ``/start`` and ``/update`` endpoints accept an optional ``metadata`` parameter
in the request payload.

.. important::

   The ``metadata`` argument should be a dictionary matching the structure of the ``Metadata`` class.

Minimal example:

.. tab-set::

    .. tab-item:: Start pyload

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

           # Using visor-cli to start VISOR with metadata
           # metadata.json has content {"name": "My Visualization", "unit": "cm"}

           visor-cli start --file-path path/to/your_file.vtm --metadata-path metadata.json

Example including per-part opacities:

.. tab-set::

    .. tab-item:: Start payload

        .. code-block:: json

           {
               "file_path": "path/to/your_file.vtm",
               "metadata": {
                   "name": "My Visualization",
                   "unit": "cm",
                   "state": {
                      "parts": {
                        "part1": {"opacity": 0.25},
                        "part2": {"opacity": 0.75}
                      }
                   }
               },
               "timeout": 60
           }

    .. tab-item:: VISOR CLI command

        .. code-block:: bash

           # Metadata can be passed in a JSON file, for example:
           # {
           #     "name": "My Visualization",
           #     "unit": "cm",
           #     "state": {
           #         "parts": {
           #             "part1": {"opacity": 0.25},
           #             "part2": {"opacity": 0.75}
           #         }
           #     }
           # }

           visor-cli start --file-path path/to/your_file.vtm --metadata-path metadata.json


VISOR Python API
~~~~~~~~~~~~~~~~

When using the Python API, the ``Visor`` class accepts an optional ``metadata`` parameter in its constructor.

The ``metadata`` argument needs to be an instance of the ``Metadata`` class.

Minimal example:

.. code-block:: python

   from ansys.visor.viewer import Visor
   from ansys.visor.viewer import Metadata

   an_input_file = "path/to/your_file.vtm"
   metadata = Metadata(name="My Visualization", unit="cm")

   visualizer = Visor()
   visualizer.start(input=an_input_file, metadata=metadata)

Additional Example:

The ``Metadata`` class also supports an optional ``state`` field to define initial per-part values.
Only the initial opacity is supported as a per-part property.

.. code-block:: python

   from ansys.visor.viewer import Visor
   from ansys.visor.viewer import Metadata

   # Path to file.  Assume the file contains parts named "part1" and "part2".
   an_input_file = "path/to/your_file.vtm"

   # Create metadata with name, unit, and initial opacity state for parts.
   metadata = Metadata(
       name="My Visualization",
       unit="cm",
       state={
           "parts": {
               "part1": {"opacity": 0.25},
               "part2": {"opacity": 0.75},
           },
       },
   )
   visualizer = Visor()
   visualizer.start(input=an_input_file, metadata=metadata)

Reference
~~~~~~~~~

Reference: ``Metadata`` class (`source code <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/blob/main/src/ansys/visor/viewer/core/metadata.py>`_).

.. literalinclude:: ../../../../src/ansys/visor/viewer/core/metadata.py
   :pyobject: Metadata
   :language: python

