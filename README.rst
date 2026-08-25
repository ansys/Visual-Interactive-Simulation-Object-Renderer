
Visor
=====

|pyansys|

.. |pyansys| image:: https://img.shields.io/badge/Py-Ansys-ffc107.svg?labelColor=black&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAABDklEQVQ4jWNgoDfg5mD8vE7q/3bpVyskbW0sMRUwofHD7Dh5OBkZGBgW7/3W2tZpa2tLQEOyOzeEsfumlK2tbVpaGj4N6jIs1lpsDAwMJ278sveMY2BgCA0NFRISwqkhyQ1q/Nyd3zg4OBgYGNjZ2ePi4rB5loGBhZnhxTLJ/9ulv26Q4uVk1NXV/f///////69du4Zdg78lx//t0v+3S88rFISInD59GqIH2esIJ8G9O2/XVwhjzpw5EAam1xkkBJn/bJX+v1365hxxuCAfH9+3b9/+////48cPuNehNsS7cDEzMTAwMMzb+Q2u4dOnT2vWrMHu9ZtzxP9vl/69RVpCkBlZ3N7enoDXBwEAAA+YYitOilMVAAAAAElFTkSuQmCC
   :target: https://docs.pyansys.com/
   :alt: PyAnsys


.. contents::
   :local:

Demo
----

You can view a `demo <https://visor.dev.ansysapis.com/index.html>`_ of
Visor to see it in action.


Overview
--------

Visor is a Python-based 3D visualization web component.

You can use Visor to integrate with the following tools:

* `SAF (Solution Application Framework) <https://upgraded-carnival-wn6lkym.pages.github.io>`_
  to provide 3D visualization capabilities.
* `Ansys Dynamic Reporting <https://nexusdemo.ensight.com/docs/html/Nexus.html>`_
  to support dynamic reporting workflows.
* `PyAnsys Visualization Interface Tool <https://visualization-interface.tools.docs.pyansys.com/>`_
  to connect PyAnsys libraries to different plotting backends.

You can use Visor for 3D visualization on desktop and on premises. Visor customizes existing
rendering frameworks to meet functional and nonfunctional requirements, including integrability,
scalability, performance, and usability for solution apps.

You run Visor with VTK (Visual Toolkit) rendering and Trame to support a client-server architecture and Python integration
workflows. You target VTK WASM with WebGL because WebGPU support is not yet available.


Installation
------------

To set up prerequisites and install Visor, see
`Getting started <https://vigilant-lamp-162kw9z.pages.github.io/version/dev/getting_started/index.html>`_
in the Visor documentation.


Quick start
-----------

For a basic usage example, see
`Quick start <https://vigilant-lamp-162kw9z.pages.github.io/version/dev/getting_started/quick_start.html>`_
in the Visor documentation.


Development
-----------

To set up your development environment, see the `Contributing.md <Contributing.md>`_ file in the
Visor repository.


Usage
-----

You can use Visor through the following entry points. Links are to the relevant information in he
Visor documentation.

* **Standalone Python**

   * Launch a desktop Visor app with the Python package ``ansys.visor.viewer`` to visualize files.
   * See `Visor Python API <https://supreme-fiesta-v6v17mm.pages.github.io/version/dev/user_guide/launching_visor/visor_python_api.html>`_
     for API usage examples.
   * See `API reference <https://supreme-fiesta-v6v17mm.pages.github.io/version/dev/python_api_reference.html>`_
     for details about the Python API.

* **Visor HTTP service**

   * Manage multiple Visor instances through the Visor HTTP API.
   * Integrate with `PIM (Product Instance Management) <https://github.com/ansys/ansys-api-platform-instancemanagement>`_
     to manage Visor instances in SAF apps.
   * See `Visor HTTP service <https://supreme-fiesta-v6v17mm.pages.github.io/version/dev/user_guide/launching_visor/visor_service.html>`_
     for usage examples.
   * See `HTTP API reference <https://supreme-fiesta-v6v17mm.pages.github.io/version/dev/http_api_reference/index.html>`_
     for API details.

* **Dash frontend app**

   * Connect to a Visor instance from a Dash app with the Visor Dash component in
     ``ansys.visor.dash.dash_visor_viewer``.
   * See `Visor Dash component <https://supreme-fiesta-v6v17mm.pages.github.io/version/dev/user_guide/launching_visor/visor_dash_component.html>`_
     for details.

For advanced usage and configuration options, see the following Visor documentation:

`User guide <https://supreme-fiesta-v6v17mm.pages.github.io/version/dev/user_guide/index.html>`_ and
`Examples <https://supreme-fiesta-v6v17mm.pages.github.io/version/dev/examples/index.html>`_ in the
Visor sections.
