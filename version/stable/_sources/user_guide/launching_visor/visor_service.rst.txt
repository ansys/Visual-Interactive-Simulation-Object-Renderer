.. _visor-service:

Launch VISOR using the HTTP API service
#######################################

Use the VISOR HTTP API service to manage multiple 3D visualization instances.
Each instance uses a host and port that you specify, and each instance runs on a dedicated Trame server.

The service endpoints let you perform the following tasks:

* Initialize and shut down VISOR instances.
* Start and stop visualizations.
* Update input files and metadata.
* Switch between multiple instances.
* Query the state of the service.

This setup lets you manage multiple, independently configured visualization instances.
You can switch between datasets or configurations, start or stop visualizations on demand,
and update assets without restarting the full service.

Use the VISOR service
~~~~~~~~~~~~~~~~~~~~~

To interact with the VISOR service APIs, choose one of the following options:

- Run the APIs directly using HTTP requests.
- Use the ``visor-cli`` tool, which provides a command-line interface for the service.

#. Run the VISOR APIs with HTTP endpoints.

   The VISOR service exposes RESTful HTTP endpoints that you can access with any HTTP client library.
   You can start with one of the following options:

   * OpenAPI documents page at ``http://localhost:53211/docs``.

     * Use this interactive page to test API endpoints.
     * View available endpoints, parameters, and responses.
     * Send requests directly from your browser without writing code.

   * Python ``requests`` library or another HTTP client library.

   Subsequent examples show payloads for each endpoint.
   You can send requests with any HTTP client.


#. Use the VISOR CLI tool.

   The ``visor-cli`` tool provides a command-line interface for the VISOR HTTP service.
   It simplifies starting, updating, and stopping VISOR instances without manually crafting HTTP requests.

Subsequent examples show both Python ``requests`` and the ``visor-cli`` tool.


Start the VISOR service
~~~~~~~~~~~~~~~~~~~~~~~

To start the VISOR HTTP service, choose one of the following options.

**Examples**

Use the tabs to switch between seeing the ``uvicorn`` command and the VISOR CLI.

.. tab-set::

   .. tab-item:: Uvicorn command

      .. code-block:: bash

         uvicorn ansys.visor.viewer.api.server:app --host localhost --port 53211

   .. tab-item:: VISOR CLI

      .. code-block:: bash

         # start the VISOR HTTP service on the default host (localhost) and port (53211)
         visor-cli server start

         # OR, to start the VISOR HTTP service on a custom host and port, run
         visor-cli --api-host localhost --api-port 53211 server start


This command starts the ``uvicorn`` service and initializes the VISOR server, but it does not
start a VISOR instance. The service listens on port ``53211``. You can access API endpoints
at ``http://localhost:53211``.

After the service starts, use the API to start, update, and stop VISOR instances.


Start the API
^^^^^^^^^^^^^

Use the ``/start`` endpoint to send a POST request with a file path and metadata.

Start endpoint: ``http://localhost:53211/start``

Start payload:

.. code-block:: json

   {
       "file_path": "<full repo path>/visor/tests/files/many_blocks/many_blocks.vtm",
       "metadata": {
           "name": "Many Blocks Asset",
           "unit": "cm"
       },
       "timeout": 60
   }

Response:

.. code-block:: json

   {
       "success": "Server started on http://localhost:8081"
   }

The app starts at ``http://localhost:8081/index.html``.

**Examples**

Use the tabs to switch between seeing the Python and VISOR CLI examples.

.. tab-set::

   .. tab-item:: Python (requests)

      .. code-block:: python

         import requests

         payload = {
             "file_path": "tests/files/many_blocks/many_blocks.vtm",
             "metadata": {"name": "Many Blocks Asset", "unit": "cm"},
             "timeout": 60,
         }
         response = requests.post("http://localhost:53211/start", json=payload)
         print(response.json())
         {"success": "Server started on http://localhost:8081"}

   .. tab-item:: VISOR CLI

      .. code-block:: bash

         # Start a VISOR instance with the specified file and metadata
         # Metadata file contains {"name": "Many Blocks Asset", "unit": "cm"}

         visor-cli instance start tests/files/many_blocks/many_blocks.vtm --metadata-path tests/files/many_blocks/metadata.json --timeout 60
         {'success': 'Server started on http://localhost:8081'}


Update the API
^^^^^^^^^^^^^^

The ``/update`` endpoint updates the running VISOR instance with a new file.

Update endpoint: ``http://localhost:53211/update``

Update payload:

.. code-block:: json

   {
       "file_path": "visor/tests/files/plate.vtp",
       "metadata": {
           "name": "Plate Asset",
           "unit": "cm"
       }
   }

Response:

.. code-block:: json

   {
       "success": "Server input updated on http://localhost:8081"
   }

The viewer replaces the old asset with the new ``file_path`` value.

**Examples**

Use the tabs to switch between Python and the VISOR CLI examples.

.. tab-set::

   .. tab-item:: Python (requests)

      .. code-block:: python

         import requests

         payload = {
             "file_path": "visor/tests/files/plate.vtp",
             "metadata": {"name": "Plate Asset", "unit": "cm"},
             "timeout": 60,
         }
         response = requests.post("http://localhost:53211/update", json=payload)
         print(response.json())
         {"success": "Server updated on http://localhost:8081"}

   .. tab-item:: VISOR CLI

      .. code-block:: bash

         # Start a VISOR instance with the specified file and metadata
         # plate_metadata.json file contains {"name": "Plate Asset", "unit": "cm"}

         visor-cli instance update visor/tests/files/plate.vtp --metadata-path visor/tests/files/plate_metadata.json
         {'success': 'Server updated on http://localhost:8081'}


Stop the visualization API
^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``/stop_visualization`` endpoint stops the active VISOR instance.

Stop visualization endpoint: ``http://localhost:53211/stop_visualization``

Response:

.. code-block:: json

    {
         "success": "Stopped visualization for server running on http://localhost:8081"
    }

**Examples**

Use the tabs to switch between seeing the Python and VISOR CLI examples.

.. tab-set::

   .. tab-item:: Python (requests)

      .. code-block:: python

         import requests

         response = requests.post("http://localhost:53211/stop_visualization")
         print(response.json())
         {"success": "Stopped visualization for server running on http://localhost:8081"}

   .. tab-item:: VISOR CLI

      .. code-block:: bash

         visor-cli instance stop_visualization
         {'success': 'Stopped visualization for server running on http://localhost:8081'}



Stop the API
^^^^^^^^^^^^

The ``/stop`` endpoint stops the active VISOR server and deletes the instance.

Stop endpoint: ``http://localhost:53211/stop``

Response:

.. code-block:: json

    {
         "success": "Stopped visualization for server running on http://localhost:8081 and deleted instance"
    }


**Examples**

Use the tabs to switch between seeing the Python and VISOR CLI examples.

.. tab-set::

   .. tab-item:: Python (requests)

      .. code-block:: python

         import requests

         response = requests.post("http://localhost:53211/stop")
         print(response.json())
         {
             "success": "Stopped visualization for server running on http://localhost:8081 and deleted instance"
         }

   .. tab-item:: VISOR CLI

      .. code-block:: bash

         visor-cli instance stop
         {'success': 'Stopped visualization for server running on http://localhost:8081 and deleted instance'}


Initialize the API
^^^^^^^^^^^^^^^^^^

The ``/initialize`` endpoint creates a new VISOR instance at the provided host and port.
If ``port`` is set to ``0``, the server selects an unused port on the host.
The service creates the instance but does not start it. If an instance already exists at the
specified host and port, the service retrieves it and sets it as the active instance.

Initialize endpoint: ``http://localhost:53211/initialize``

Initialize payload:

.. code-block:: json

   {
       "host": "localhost",
       "port": 8082,
       "standalone": true
   }

Response:

.. code-block:: json

    {
        ["Set active instance to http://localhost:8082"]
    }


**Examples**

Use the tabs to switch between seeing the Python and VISOR CLI examples.

.. tab-set::

   .. tab-item:: Python (requests)

      .. code-block:: python

         import requests

         payload = {"host": "localhost", "port": 8082, "standalone": True}
         response = requests.post("http://localhost:53211/initialize", json=payload)
         print(response.json())
         ["Set active instance to http://localhost:8082"]

   .. tab-item:: VISOR CLI

      .. code-block:: bash

         visor-cli server init --host localhost --port 8082
         ['Set active instance to http://localhost:8082']




