Visual Interactive Simulation Object Renderer (VISOR)
=====================================================

.. toctree::
   :hidden:
   :maxdepth: 5

   getting_started/index
   user_guide/index
   python_api_reference
   http_api_reference/index
   examples/index
   contributing/index
   changelog


Introduction
------------

VISOR (Visual Interactive Simulation Object Renderer)
is a Python-based 3D visualization web component for Ansys solutions and apps.

You can use VISOR for 3D visualization on desktop and on premises. It customizes existing
rendering frameworks to meet functional and nonfunctional requirements, including integrability,
scalability, performance, and ease of use.

You can use VISOR to integrate with the following tools:

* `SAF (Solution Application Framework) <https://upgraded-carnival-wn6lkym.pages.github.io>`_
  to provide 3D visualization capabilities.
* `Ansys Dynamic Reporting <https://nexusdemo.ensight.com/docs/html/Nexus.html>`_
  to support dynamic reporting workflows.
* `PyAnsys Visualization Interface Tool <https://visualization-interface.tools.docs.pyansys.com/>`_
  to connect PyAnsys libraries to different plotting backends.

You run VISOR with VTK (Visual Toolkit) rendering through Trame for client-server architecture and Python
integration workflows. You target VTK WASM with WebGL support.

View a `demo <https://visor.dev.ansysapis.com/index.html>`_ to see VISOR in action.

.. grid:: 2
  :gutter: 4

  .. grid-item-card:: :material-outlined:`play_circle;2em`
    :link-type: doc
    :link: getting_started/index

    .. raw:: html

      <span style="font-size: 1.5em; color:#5a2a82;">Getting started</span>

    Learn how to install VISOR, set up and run a minimal solution, review known
    limitations, and override default settings.

  .. grid-item-card:: :material-outlined:`menu_book;2em`
    :link-type: doc
    :link: user_guide/index

    .. raw:: html

      <span style="font-size: 1.5em; color:#5a2a82;">User guide</span>

    Learn how to run VISOR in different modes, use its arguments, bring in your data,
    and integrate with SAF.

  .. grid-item-card:: :material-outlined:`api;2em`
    :link-type: doc
    :link: python_api_reference

    .. raw:: html

      <span style="font-size: 1.5em; color:#5a2a82;">API reference</span>

    Access the Python API reference documentation for VISOR, including classes and methods.

  .. grid-item-card:: :material-outlined:`api;2em`
    :link-type: doc
    :link: http_api_reference/index

    .. raw:: html

      <span style="font-size: 1.5em; color:#5a2a82;">HTTP API reference</span>

    Access the HTTP API reference documentation for VISOR services, including endpoint
    usage and example responses.

  .. grid-item-card:: :material-outlined:`lightbulb;2em`
    :link-type: doc
    :link: examples/index

    .. raw:: html

      <span style="font-size: 1.5em; color:#5a2a82;">Examples</span>

    Explore examples demonstrating VISOR usage.





Project index
-------------

* :ref:`genindex`