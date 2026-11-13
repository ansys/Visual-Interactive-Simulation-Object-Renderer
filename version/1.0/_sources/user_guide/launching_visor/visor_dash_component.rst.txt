.. _visor-dash-component:


Use the VISOR Dash component
############################

Use VISOR in a Dash app with the ``Visordash`` component.

The Dash component creates a WebSocket connection to a running VISOR instance on a given port.
The following example shows how to connect the Dash component to a VISOR instance. It uses
the following ports:

- VISOR app server port: ``8081``
- VISOR Dash component port: ``8050``

With these ports, the VISOR Dash server is available at ``http://localhost:8050``.
The VISOR Dash server connects to the VISOR app server at ``http://localhost:8081``.

Start the VISOR app server first with the VISOR CLI or Python API.

**Example**

To use the VISOR Dash component, start a VISOR instance and then run the Dash app
that connects to that instance.

This example uses a VISOR instance running on ``http://localhost:8081``.

#. Start the VISOR HTTP server:

   .. code-block:: bash

       visor-cli server start

#. Start a VISOR instance with a VTM file using either the VISOR CLI or Python API:

   .. tab-set::

       .. tab-item:: VISOR CLI

           .. code-block:: bash

               visor-cli instance start your_file.vtm

       .. tab-item:: Python API

           .. code-block:: python

               from ansys.visor.viewer import Visor

               visualizer = Visor(
                   url="http://localhost:8081",
                   input="your_file.vtm",
               )
               visualizer.start()


#. Run the Dash app:

   .. code-block:: python

       from visordash import init_endpoints, Visordash
       from dash import Dash, html

       app = Dash(__name__)

       VISOR_PORT = 8081  # Port where VISOR instance is running
       DASH_PORT = 8050  # Port where Dash app runs

       init_endpoints(app)

       td = Visordash(
           id="input",
           value="my-value",
           label="my-label",
           host="localhost",
           port=VISOR_PORT,
       )

       app.layout = html.Div([td, html.Div(id="output")])

       app.run(
           host="0.0.0.0", port=DASH_PORT, debug=False, use_reloader=False
       )  # use_reloader=False avoids double execution


.. note::

    Start the VISOR app server in the same Dash app or through the VISOR HTTP API.
    Use the default URL (``http://localhost:8081``), or set a custom URL in both the Dash component and
    the VISOR app server.

