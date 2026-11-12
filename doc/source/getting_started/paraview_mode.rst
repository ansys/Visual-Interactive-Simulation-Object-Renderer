.. _paraview-mode:

PARAVIEW mode setup
###################

In PARAVIEW rendering mode, VISOR renders through a ParaView ``pvserver``.
VISOR drives the server from a ``pvpython`` process that runs in its own
virtual environment, the ``.pvenv``.  This page shows how to build that
environment beside the repository's ``.venv`` and how to launch ``pvserver``.

All commands run in PowerShell from the repository root.  The paths assume
ParaView 6.2.0 installed at ``C:\Program Files\ParaView 6.2.0``.

Pin pydantic in the ``.venv``
=============================

Pydantic models pass between the API process and the ``pvpython`` process, so
both environments must hold identical pydantic, pydantic-core and
pydantic-settings versions.  Pin the ``.venv`` to these versions:

.. code-block:: powershell

   .venv\Scripts\python.exe -m pip install "pydantic==2.14.1" "pydantic-core==2.50.1" "pydantic-settings==2.6.0"

If these pins ever change, change them in both environments together.

Create the ``.pvenv``
=====================

1. Check the Python version that ``pvpython`` embeds:

   .. code-block:: powershell

      & "C:\Program Files\ParaView 6.2.0\bin\pvpython.exe" -c "import sys; print(sys.version)"

   It must print ``3.12.x``.

2. Create the environment with a CPython of the same minor version:

   .. code-block:: powershell

      py -3.12 -m venv .pvenv

3. Install the dependencies.  Do not install ``vtk``: ParaView supplies it.
   ``numpy`` is pinned below 2 so that it matches the numpy 1.26 that
   ParaView's own extensions are built against.

   .. code-block:: powershell

      .pvenv\Scripts\python.exe -m pip install "trame==3.12.0" "trame-server>=3.6.0" "wslink>=2.6.0" "trame-rca==2.11.8" "pydantic==2.14.1" "pydantic-core==2.50.1" "pydantic-settings==2.6.0" pyyaml "pillow>=12.3.0" "numpy<2"

4. Install ``trame-vtklocal`` without its dependencies, which would pull in
   ``vtk``:

   .. code-block:: powershell

      .pvenv\Scripts\python.exe -m pip install --no-deps "trame-vtklocal==1.6.2"

5. Install VISOR itself, without dependencies.  The package metadata is
   required at import time.

   .. code-block:: powershell

      .pvenv\Scripts\python.exe -m pip install --no-deps -e .

Verify the ``.pvenv``
=====================

1. numpy and VTK come from the right places:

   .. code-block:: powershell

      & "C:\Program Files\ParaView 6.2.0\bin\pvpython.exe" --venv ".pvenv" -c "import numpy, vtkmodules; print(numpy.__version__, vtkmodules.__path__)"

   The output must show numpy ``1.26.x`` and a ``vtkmodules`` path inside
   ``C:\Program Files\ParaView 6.2.0``.  A path under ``.pvenv`` means a pip
   copy of VTK was installed: remove it.

2. The streamed app imports without ``trame-vtklocal``:

   .. code-block:: powershell

      & "C:\Program Files\ParaView 6.2.0\bin\pvpython.exe" --venv ".pvenv" -c "import sys, ansys.visor.viewer.app.trame.server_app; print('trame_vtklocal' in sys.modules)"

   The command must finish without an error and print ``False``.

3. The pydantic versions match.  Run both commands and compare the
   ``pydantic`` lines; all three must be identical:

   .. code-block:: powershell

      .venv\Scripts\python.exe -m pip list
      .pvenv\Scripts\python.exe -m pip list

Configure VISOR
===============

Add these keys to the ``.visor`` file in the directory the API is started
from (see :ref:`configure-visor` for the file format):

.. code-block:: yaml

   paraview_pvpython: C:/Program Files/ParaView 6.2.0/bin/pvpython.exe
   paraview_venv: C:/path/to/visor/.pvenv
   pvserver_host: localhost
   pvserver_port: 11111

``pvserver_host`` and ``pvserver_port`` are the defaults used when a session
does not name a server.

Launch ``pvserver``
===================

Start ``pvserver`` without ``--multi-clients``:

.. code-block:: powershell

   & "C:\Program Files\ParaView 6.2.0\bin\pvserver.exe" --server-port=11111 --force-offscreen-rendering

Restart ``pvserver`` after every session.  Before starting it, stop any
``pvserver`` or ``pvpython`` processes left from an earlier run: a stale
process causes version handshake errors.

``pvserver`` must be able to read the files VISOR opens, at the same path
the API is given.

If ``pvserver`` is not running, VISOR fails to connect after about ten
seconds and reports an error that names the ``host:port`` it tried.

Linux
=====

The same steps apply with ``bin/pvpython`` and ``.pvenv/bin/python``.
Offscreen OpenGL comes from the ParaView build (EGL or OSMesa) or from running
the API under ``xvfb-run``.
