.. _visor-add-remove-datasets:

Add, list, and remove datasets
##############################

After a VISOR instance starts, you can add or remove datasets dynamically.
You can do this through the Python API, HTTP API, or VISOR CLI.

For more comprehensive examples, see the :ref:`gallery` and :ref:`classdocumentation` section.

.. note::
    In the following examples, the **HTTP API** and **VISOR CLI** tabs assume that the VISOR service
    is running on ``localhost:53211``. To start the service, run ``visor-cli server start``.

Add a dataset
*************

After a VISOR visualization starts, you can add a dataset with the ``add_dataset()`` Pythonmethod,
the HTTP API, or the VISOR CLI.

The following examples show how to add a dataset to an existing VISOR instance.

.. tab-set::

    .. tab-item:: Python

        Use the ``Visor`` class in Python.

        .. code-block:: python

            # Add a new dataset
            new_dataset_file = "path/to/your/new_dataset.vtm"
            new_metadata_file = "path/to/your/new_dataset_metadata.json"  # optional
            visualizer.add_dataset(new_dataset_file, metadata_file=new_metadata_file)

    .. tab-item:: HTTP API

        Use the HTTP API with the Python ``requests`` library.
        This example assumes the service is running on ``localhost:53211``.

        .. code-block:: python

            import requests

            # Add a new dataset via HTTP API
            new_dataset_file = "path/to/your/new_dataset.vtm"
            new_metadata_file = "path/to/your/new_dataset_metadata.json"  # optional
            payload = {
                "file_path": new_dataset_file,
                "metadata_file": new_metadata_file,  # optional
            }
            response = requests.post(f"http://localhost:53211/add_dataset", json=payload)

    .. tab-item:: VISOR CLI

        Use the VISOR CLI in a terminal.
        This example assumes the service is running on ``localhost:53211``.

        .. code-block:: bash

            # Add a new dataset via VISOR CLI
            visor-cli instance add path/to/your/new_dataset.vtm
            # or with metadata (optional)
            visor-cli instance add path/to/your/new_dataset.vtm --metadata-path path/to/your/new_dataset_metadata.json


List current datasets
*********************

Before you interact with datasets in a running VISOR instance, list the current datasets to get their IDs.
You can do this with the ``list_datasets()`` Python method, the HTTP API, or the VISOR CLI.

.. tab-set::

    .. tab-item:: Python

        Use the ``Visor`` class in Python.

        .. code-block:: python

            # List datasets
            datasets = visualizer.list_datasets()
            print("Available datasets:", datasets)

            dataset_ids = list(datasets.keys())  # Get the list of dataset IDs
            dataset_id = dataset_ids[0]  # Select the first dataset ID

    .. tab-item:: HTTP API

        Use the HTTP API with the Python ``requests`` library.
        This example assumes the service is running on ``localhost:53211``.

        .. code-block:: python

            import requests

            # List datasets via HTTP API
            response = requests.get(f"http://localhost:53211/list_datasets")
            datasets = response.json()
            print("Available datasets:", datasets)

            dataset_ids = list(datasets.keys())  # Get the list of dataset IDs
            dataset_id = dataset_ids[0]  # Select the first dataset ID

    .. tab-item:: VISOR CLI

        Use the VISOR CLI in a terminal.
        This example assumes the service is running on ``localhost:53211``.

        .. code-block:: bash

            # List datasets via VISOR CLI
            visor-cli instance list
            # Prints a dictionary of dataset IDs and their metadata


Remove a dataset
****************

You can remove a dataset from a running VISOR instance with the ``remove_dataset()`` Python method,
the HTTP API, or the VISOR CLI.

.. tab-set::

    .. tab-item:: Python

        Use the ``Visor`` class in Python.

        .. code-block:: python

            # Remove a dataset
            datasets = visualizer.remove_dataset(dataset_id)

    .. tab-item:: HTTP API

        Use the HTTP API with the Python ``requests`` library.
        This example assumes the service is running on ``localhost:53211``.

        .. code-block:: python

            import requests

            payload = {"dataset_id": dataset_id}
            # Remove datasets via HTTP API
            response = requests.post(f"http://localhost:53211/remove_datasets", json=payload)

    .. tab-item:: VISOR CLI

        Use the VISOR CLI in a terminal.
        This example assumes the service is running on ``localhost:53211``.

        .. code-block:: bash

            # Remove a dataset with ID <dataset_id> via VISOR CLI
            visor-cli instance remove <dataset_id>
