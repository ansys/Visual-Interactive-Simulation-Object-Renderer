.. _visor-update-variables:

Update variable values in a VISOR dataset
#########################################

If a dataset in VISOR contains variable arrays, you can update those values
without reloading the full dataset. Use this mechanism to push new time-step
data, simulation results, or other per-frame array changes into a live VISOR
session.

You can use this feature through the Python API and HTTP API.
The VISOR CLI does not support this feature.

For more comprehensive examples, see the :ref:`gallery` and :ref:`classdocumentation` sections.

.. note::

    In the following HTTP API examples, the VISOR service is assumed to run on
    ``localhost:53211``. To start the service, run
    ``visor-cli server start``.


Composite (multiblock) datasets
================================

``update_variables`` supports simple datasets (``vtkPolyData``,
``vtkUnstructuredGrid``) and composite datasets (``vtkMultiBlockDataSet``,
``vtkMultiPieceDataSet``).

For composite datasets, each leaf block is called a **part**. Each part uses a
``part_id``, which is an opaque integer that remains stable for the current
server session but is not preserved across restarts. After you load a dataset,
call ``list_variables()`` to discover the current ``part_id`` values before
you call ``update_variables()``.


List variables on a dataset
****************************

``list_variables()`` returns a list of parts. Each part includes
``part_id``, ``part_name``, and the variables available on that part. For
non-composite datasets, the list contains exactly one entry.

First, get the dataset ID for the dataset that you want to update:

.. tab-set::

    .. tab-item:: Python

        .. code-block:: python

            from ansys.visor.viewer import Visor

            visualizer = Visor(url="http://localhost:53211", input="path/to/your_file.vtm")

            datasets = visualizer.list_datasets()
            dataset_id = list(datasets.keys())[0]  # select the first dataset

    .. tab-item:: HTTP API

        .. code-block:: python

            import requests

            response = requests.get("http://localhost:53211/list_datasets")
            datasets = response.json()
            dataset_id = list(datasets.keys())[0]

Then list variables:

.. tab-set::

    .. tab-item:: Python

        .. code-block:: python

            parts = visualizer.list_variables(dataset_id)

            for part in parts:
                print(f"part_id={part.part_id}  name={part.part_name}")
                for var in part.variables:
                    print(
                        f"  {var.name}  type={var.type}  components={var.num_components}  points={var.num_points}"
                    )

        The returned objects expose the following attributes:

        - ``part.part_id``: Integer ID used to target this part in ``update_variables()``.
        - ``part.part_name``: Name taken from VTK block metadata.
        - ``part.variables``: List of ``VisorVariable`` objects, each with
          ``name``, ``type`` (``"point"`` or ``"cell"``), ``num_components``,
          ``num_points``, ``ranges``, and ``magnitude_range``.

    .. tab-item:: HTTP API

        .. code-block:: python

            import requests

            response = requests.post(f"http://localhost:53211/{dataset_id}/list_variables")
            result = response.json()

            # result["parts"] is a list of part objects
            for part in result["parts"]:
                print(f"part_id={part['part_id']}  name={part['part_name']}")
                for var in part["variables"]:
                    print(f"  {var['name']}  type={var['type']}")

        Response shape:

        .. code-block:: json

            {
              "parts": [
                {
                  "part_id": 1234567890,
                  "part_name": "blade_1",
                  "variables": [
                    {
                      "name": "temperature",
                      "type": "point",
                      "num_components": 1,
                      "num_points": 962
                    }
                  ]
                }
              ]
            }

.. note::

    The ``"parts"`` response shape applies to all dataset types. For
    non-composite datasets, the list has exactly one entry.


Update variable values
**********************

After you get ``part_id`` values from the ``list_variables()`` Python method, you
can push new data for any variable on any part.

Each entry in the update list uses this structure:

.. code-block:: python

    {
        "type": "point",  # or "cell"
        "name": "variable_name",  # must match an existing array name
        "num_components": 1,  # 1 for scalar, 3 for vector, etc.
        "data": [...],  # flat array, length = num_points * num_components
        "part_id": 1234567890,  # required for composite datasets; omit for non-composite
    }

Over the HTTP API, ``data`` is not part of the JSON. It travels as a separate
binary part, as described in the next section.


HTTP request format
-------------------

The ``update_variables`` HTTP endpoint takes a ``multipart/form-data`` request
with:

- a ``metadata`` form field holding JSON of the form
  ``{"variables": [{"name", "type", "num_components", "part_id"}, ...]}``,
  where ``part_id`` is optional; and
- one ``data`` file part per variable, in the same order as the ``metadata``
  entries, containing the values as little-endian ``float32`` in C order
  (``num_points * num_components`` values).

All variables in one request are applied as a single scene update. A request
whose part count does not match the metadata, or whose part length is not a
whole number of ``float32`` tuples, is rejected with HTTP 422.

This example updates a scalar and a vector variable in one request:

.. code-block:: python

    import json

    import numpy as np
    import requests

    variables = [
        {"type": "point", "name": "temperature", "num_components": 1},
        {"type": "cell", "name": "velocity", "num_components": 3},
    ]
    values = [
        np.array([300.0, 305.5, 310.2], dtype="<f4"),  # 3 points
        np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype="<f4"),  # 2 cells
    ]
    requests.post(
        f"http://localhost:53211/{dataset_id}/update_variables",
        data={"metadata": json.dumps({"variables": variables})},
        files=[
            ("data", (f"{i}.bin", array.tobytes(), "application/octet-stream"))
            for i, array in enumerate(values)
        ],
    )

Every binary part uses the field name ``data``. The server matches the parts to
the ``metadata`` entries by order. It ignores the filenames, so ``f"{i}.bin"``
only labels each part.


Target a specific part (composite datasets)
--------------------------------------------

Provide ``part_id`` to update a single leaf block. Get the ``part_id``
directly from the ``list_variables()`` response.

.. tab-set::

    .. tab-item:: Python

        .. code-block:: python

            import numpy as np

            parts = visualizer.list_variables(dataset_id)

            # Update one variable on one specific part
            part = parts[0]
            var = part.variables[0]

            new_data = np.zeros((var.num_points, var.num_components))

            visualizer.update_variables(
                dataset_id,
                [
                    {
                        "type": var.type,
                        "name": var.name,
                        "num_components": var.num_components,
                        "data": new_data,
                        "part_id": part.part_id,
                    }
                ],
            )

    .. tab-item:: HTTP API

        .. code-block:: python

            import json

            import numpy as np
            import requests

            metadata = {
                "variables": [
                    {
                        "type": "point",
                        "name": "temperature",
                        "num_components": 1,
                        "part_id": 1234567890,
                    }
                ]
            }
            values = np.zeros(962, dtype="<f4")
            requests.post(
                f"http://localhost:53211/{dataset_id}/update_variables",
                data={"metadata": json.dumps(metadata)},
                files=[("data", ("0.bin", values.tobytes(), "application/octet-stream"))],
            )


Broadcast update (composite datasets)
--------------------------------------

Omit ``part_id`` (or set it to ``null``) on a composite dataset to broadcast
the same data to every part where the variable name exists and the array length
matches. The server skips parts where the variable name is not found or where
the array length does not match, and logs a warning. Use this mode to reset a
variable to a uniform value across all parts.

.. tab-set::

    .. tab-item:: Python

        .. code-block:: python

            import numpy as np

            parts = visualizer.list_variables(dataset_id)
            var = parts[0].variables[0]  # pick a variable present on all parts

            reset_data = np.zeros((var.num_points, var.num_components))

            # No part_id: broadcasts to all matching parts
            visualizer.update_variables(
                dataset_id,
                [
                    {
                        "type": var.type,
                        "name": var.name,
                        "num_components": var.num_components,
                        "data": reset_data,
                    }
                ],
            )

    .. tab-item:: HTTP API

        .. code-block:: python

            import json

            import numpy as np
            import requests

            metadata = {
                "variables": [
                    {
                        "type": "point",
                        "name": "temperature",
                        "num_components": 1,
                        # no "part_id" key: broadcast
                    }
                ]
            }
            values = np.zeros(962, dtype="<f4")
            requests.post(
                f"http://localhost:53211/{dataset_id}/update_variables",
                data={"metadata": json.dumps(metadata)},
                files=[("data", ("0.bin", values.tobytes(), "application/octet-stream"))],
            )

.. warning::

    Broadcast applies the **same** data array to every matching part. Use it for
    resets or uniform values, but not for time-stepping scenarios where each
    part carries different data at each step. For those cases, issue one
    targeted update (with ``part_id``) per part.


Non-composite dataset updates
------------------------------

For non-composite datasets, (``vtkPolyData``, ``vtkUnstructuredGrid``),
``part_id`` is optional and has no effect.

.. tab-set::

    .. tab-item:: Python

        .. code-block:: python

            import numpy as np

            parts = visualizer.list_variables(dataset_id)
            var = parts[0].variables[0]  # single-part dataset: parts[0] is the whole dataset

            new_data = np.random.rand(var.num_points * var.num_components)

            visualizer.update_variables(
                dataset_id,
                [
                    {
                        "type": var.type,
                        "name": var.name,
                        "num_components": var.num_components,
                        "data": new_data,
                        # part_id not required for non-composite datasets
                    }
                ],
            )

    .. tab-item:: HTTP API

        .. code-block:: python

            import json

            import numpy as np
            import requests

            metadata = {
                "variables": [
                    {"type": "point", "name": "temperature", "num_components": 1},
                ]
            }
            values = np.array([300.0, 305.5, 310.2], dtype="<f4")
            requests.post(
                f"http://localhost:53211/{dataset_id}/update_variables",
                data={"metadata": json.dumps(metadata)},
                files=[("data", ("0.bin", values.tobytes(), "application/octet-stream"))],
            )
