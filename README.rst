
Visual Interactive Simulation Object Renderer (VISOR)
=====================================================

|pyansys| |python| |pypi| |GH-CI| |Apache-2.0| |black|

.. |pyansys| image:: https://img.shields.io/badge/Py-Ansys-ffc107.svg?labelColor=black&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAABDklEQVQ4jWNgoDfg5mD8vE7q/3bpVyskbW0sMRUwofHD7Dh5OBkZGBgW7/3W2tZpa2tLQEOyOzeEsfumlK2tbVpaGj4N6jIs1lpsDAwMJ278sveMY2BgCA0NFRISwqkhyQ1q/Nyd3zg4OBgYGNjZ2ePi4rB5loGBhZnhxTLJ/9ulv26Q4uVk1NXV/f///////69du4Zdg78lx//t0v+3S88rFISInD59GqIH2esIJ8G9O2/XVwhjzpw5EAam1xkkBJn/bJX+v1365hxxuCAfH9+3b9/+////48cPuNehNsS7cDEzMTAwMMzb+Q2u4dOnT2vWrMHu9ZtzxP9vl/69RVpCkBlZ3N7enoDXBwEAAA+YYitOilMVAAAAAElFTkSuQmCC
   :target: https://docs.pyansys.com/
   :alt: PyAnsys

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-visor-viewer?logo=pypi
   :target: https://pypi.org/project/ansys-visor-viewer/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-visor-viewer.svg?logo=python&logoColor=white
   :target: https://pypi.org/project/ansys-visor-viewer
   :alt: PyPI

.. |GH-CI| image:: https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/actions/workflows/build_and_package.yml/badge.svg?branch=main
   :target: https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/actions/workflows/build_and_package.yml
   :alt: GH-CI

.. |codecov| image:: https://codecov.io/gh/ansys/Visual-Interactive-Simulation-Object-Renderer/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/ansys/Visual-Interactive-Simulation-Object-Renderer

.. |Apache-2.0| image::  https://img.shields.io/badge/License-Apache%202.0-blue.svg
   :target: https://opensource.org/license/Apache-2.0
   :alt: Apache-2.0

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=flat
   :target: https://github.com/psf/black
   :alt: Black

.. |pre-commit| image:: https://results.pre-commit.ci/badge/github/ansys/Visual-Interactive-Simulation-Object-Renderer/main.svg
   :target: https://results.pre-commit.ci/latest/github/ansys/Visual-Interactive-Simulation-Object-Renderer/main
   :alt: pre-commit.ci status

.. contents::
   :local:



Demo
----

You can view a `demo <https://visor.dev.ansysapis.com/index.html>`_ of
VISOR to see it in action.


Overview
--------

VISOR is a Python-based 3D visualization web component.

You can use VISOR to integrate with the following tools:

* `SAF (Solution Application Framework) <https://upgraded-carnival-wn6lkym.pages.github.io>`_
  to provide 3D visualization capabilities.
* `Ansys Dynamic Reporting <https://nexusdemo.ensight.com/docs/html/Nexus.html>`_
  to support dynamic reporting workflows.
* `PyAnsys Visualization Interface Tool <https://visualization-interface.tools.docs.pyansys.com/>`_
  to connect PyAnsys libraries to different plotting backends.

You can use VISOR for 3D visualization on desktop and on premises. VISOR customizes existing
rendering frameworks to meet functional and nonfunctional requirements, including integrability,
scalability, performance, and usability for solution apps.

You run VISOR with VTK (Visual Toolkit) rendering and Trame to support a client-server architecture and Python integration
workflows. You target VTK WASM with WebGL because WebGPU support is not yet available.


Installation
------------

To set up prerequisites and install VISOR, see
`Getting started <https://visor.docs.pyansys.com/version/dev/getting_started/index.html>`_
in the VISOR documentation.


Quick start
-----------

For a basic usage example, see
`Quick start <https://visor.docs.pyansys.com/version/dev/getting_started/quick_start.html>`_
in the VISOR documentation.


Development
-----------

To set up your development environment, see the `Contributing.md <Contributing.md>`_ file in the
VISOR repository.


Usage
-----

You can use VISOR through the following entry points. Links are to the relevant information in he
VISOR documentation.

* **Standalone Python**

   * Launch a desktop VISOR app with the Python package ``ansys.visor.viewer`` to visualize files.
   * See `VISOR Python API <https://visor.docs.pyansys.com/version/dev/user_guide/launching_visor/visor_python_api.html>`_
     for API usage examples.
   * See `API reference <https://visor.docs.pyansys.com/version/dev/python_api_reference.html>`_
     for details about the Python API.

* **VISOR HTTP service**

   * Manage multiple VISOR instances through the VISOR HTTP API.
   * Integrate with `PIM (Product Instance Management) <https://github.com/ansys/ansys-api-platform-instancemanagement>`_
     to manage VISOR instances in SAF apps.
   * See `VISOR HTTP service <https://visor.docs.pyansys.com/version/dev/user_guide/launching_visor/visor_service.html>`_
     for usage examples.
   * See `HTTP API reference <https://visor.docs.pyansys.com/version/dev/http_api_reference/index.html>`_
     for API details.

* **Dash frontend app**

   * Connect to a VISOR instance from a Dash app with the VISOR Dash component in
     ``ansys.visor.dash.dash_visor_viewer``.
   * See `VISOR Dash component <https://visor.docs.pyansys.com/version/dev/user_guide/launching_visor/visor_dash_component.html>`_
     for details.

For advanced usage and configuration options, see the following VISOR documentation:

`User guide <https://visor.docs.pyansys.com/version/dev/user_guide/index.html>`_ and
`Examples <https://visor.docs.pyansys.com/version/dev/examples/index.html>`_ in the
VISOR sections.
