.. _paraview-mode:

PARAVIEW mode setup
###################

.. note::

   PARAVIEW mode is a beta feature and is still in development.

In PARAVIEW rendering mode, VISOR renders through a ParaView ``pvserver``.
VISOR drives the server from a ``pvpython`` process that runs in its own
virtual environment, the ``.pvenv``.  This page shows how to build that
environment beside the ``.venv`` that VISOR is installed in (see
:ref:`installation-index`) and how to launch ``pvserver``.

Each VISOR instance in PARAVIEW mode needs its own ``pvserver`` process, which
you start by hand before you start the instance.  For details, see
:ref:`paraview-mode-launch-pvserver`.

Instructions are given for Windows and Linux.  Run all commands from the
directory that holds the ``.venv``: in PowerShell on Windows, or in a Bash
shell on Linux.  The
paths assume ParaView 6.2.0, installed at ``C:\Program Files\ParaView 6.2.0``
on Windows or extracted to ``/opt/ParaView-6.2.0`` on Linux.  Adjust them to
match your installation.

Pin pydantic in the ``.venv``
=============================

Pydantic models pass between the API process and the ``pvpython`` process, so
both environments must hold identical pydantic, pydantic-core and
pydantic-settings versions.  Pin the ``.venv`` to these versions:

.. tab-set::
   :sync-group: os

   .. tab-item:: Windows
      :sync: windows

      .. code-block:: powershell

         .venv\Scripts\python.exe -m pip install "pydantic==2.14.1" "pydantic-core==2.50.1" "pydantic-settings==2.6.0"

   .. tab-item:: Linux
      :sync: linux

      .. code-block:: bash

         .venv/bin/python -m pip install "pydantic==2.14.1" "pydantic-core==2.50.1" "pydantic-settings==2.6.0"

If these pins ever change, change them in both environments together.

Create the ``.pvenv``
=====================

1. Check the Python version that ``pvpython`` embeds:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            & "C:\Program Files\ParaView 6.2.0\bin\pvpython.exe" -c "import sys; print(sys.version)"

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            /opt/ParaView-6.2.0/bin/pvpython -c "import sys; print(sys.version)"

   It must print ``3.12.x``.

2. Create the environment with a CPython of the same minor version:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            py -3.12 -m venv .pvenv

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            python3.12 -m venv .pvenv

3. Install the dependencies.  Do not install ``vtk``: ParaView supplies it.
   ``numpy`` is pinned below 2 so that it matches the numpy 1.26 that
   ParaView's own extensions are built against.

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            .pvenv\Scripts\python.exe -m pip install "trame==3.12.0" "trame-server>=3.6.0" "wslink>=2.6.0" "trame-rca==2.11.8" "pydantic==2.14.1" "pydantic-core==2.50.1" "pydantic-settings==2.6.0" pyyaml "pillow>=12.3.0" "numpy<2"

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            .pvenv/bin/python -m pip install "trame==3.12.0" "trame-server>=3.6.0" "wslink>=2.6.0" "trame-rca==2.11.8" "pydantic==2.14.1" "pydantic-core==2.50.1" "pydantic-settings==2.6.0" pyyaml "pillow>=12.3.0" "numpy<2"

4. Install ``trame-vtklocal`` without its dependencies, which would pull in
   ``vtk``:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            .pvenv\Scripts\python.exe -m pip install --no-deps "trame-vtklocal==1.6.2"

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            .pvenv/bin/python -m pip install --no-deps "trame-vtklocal==1.6.2"

5. Install VISOR itself, without dependencies.  The ``.pvenv`` must hold the
   same VISOR version as the ``.venv``, so read the version from the
   ``.venv`` and install that version:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            $v = .venv\Scripts\python.exe -c "from importlib.metadata import version; print(version('ansys-visor-viewer'))"
            .pvenv\Scripts\python.exe -m pip install --no-deps "ansys-visor-viewer==$v"

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            v=$(.venv/bin/python -c "from importlib.metadata import version; print(version('ansys-visor-viewer'))")
            .pvenv/bin/python -m pip install --no-deps "ansys-visor-viewer==$v"

   If you work from a clone of the VISOR repository (see the developer
   installation in :ref:`installation-index`), install your checkout in
   editable mode instead, from the repository root:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            .pvenv\Scripts\python.exe -m pip install --no-deps -e .

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            .pvenv/bin/python -m pip install --no-deps -e .

Verify the ``.pvenv``
=====================

1. numpy and VTK come from the right places:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            & "C:\Program Files\ParaView 6.2.0\bin\pvpython.exe" --venv ".pvenv" -c "import numpy, vtkmodules; print(numpy.__version__, vtkmodules.__path__)"

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            /opt/ParaView-6.2.0/bin/pvpython --venv ".pvenv" -c "import numpy, vtkmodules; print(numpy.__version__, vtkmodules.__path__)"

   The output must show numpy ``1.26.x`` and a ``vtkmodules`` path inside the
   ParaView installation directory.  A path under ``.pvenv`` means a pip copy
   of VTK was installed: remove it.

2. The pydantic versions match.  Run both commands and compare the
   ``pydantic`` lines; all three must be identical:

   .. tab-set::
      :sync-group: os

      .. tab-item:: Windows
         :sync: windows

         .. code-block:: powershell

            .venv\Scripts\python.exe -m pip list
            .pvenv\Scripts\python.exe -m pip list

      .. tab-item:: Linux
         :sync: linux

         .. code-block:: bash

            .venv/bin/python -m pip list
            .pvenv/bin/python -m pip list

Configure VISOR
===============

Add these keys to the ``.visor`` file in the directory the API is started
from (see :ref:`configure-visor` for the file format):

.. tab-set::
   :sync-group: os

   .. tab-item:: Windows
      :sync: windows

      .. code-block:: yaml

         paraview_pvpython: C:/Program Files/ParaView 6.2.0/bin/pvpython.exe
         paraview_venv: C:/path/to/visor/.pvenv
         pvserver_host: localhost
         pvserver_port: 11111

   .. tab-item:: Linux
      :sync: linux

      .. code-block:: yaml

         paraview_pvpython: /opt/ParaView-6.2.0/bin/pvpython
         paraview_venv: /path/to/visor/.pvenv
         pvserver_host: localhost
         pvserver_port: 11111

``pvserver_host`` and ``pvserver_port`` are the defaults used when a session
does not name a server.

.. _paraview-mode-launch-pvserver:

Launch ``pvserver``
===================

VISOR does not start ``pvserver``.  You must start one ``pvserver`` process
manually for every VISOR instance in PARAVIEW mode, before you start that
instance:

- A ``pvserver`` serves one VISOR instance only.  Started without
  ``--multi-clients``, it accepts a single connection and exits when that
  instance ends.
- To run several PARAVIEW instances at the same time, start one ``pvserver``
  per instance, each on its own port, and give each instance its port.  For
  example, with the VISOR CLI:

  .. code-block:: console

     visor-cli server init --rendering-mode PARAVIEW --pvserver-port 11112 --start

  Instances that do not name a port use ``pvserver_port`` from the ``.visor``
  file.
- After an instance ends, start a new ``pvserver`` before you start the next
  instance on that port.

Start ``pvserver`` without ``--multi-clients``:

.. tab-set::
   :sync-group: os

   .. tab-item:: Windows
      :sync: windows

      .. code-block:: powershell

         & "C:\Program Files\ParaView 6.2.0\bin\pvserver.exe" --server-port=11111 --force-offscreen-rendering

   .. tab-item:: Linux
      :sync: linux

      .. code-block:: bash

         /opt/ParaView-6.2.0/bin/pvserver --server-port=11111 --force-offscreen-rendering

Before starting ``pvserver``, stop any ``pvserver`` or ``pvpython`` processes
left from an earlier run: a stale process causes version handshake errors.

``pvserver`` must be able to read the files VISOR opens, at the same path
the API is given.

If ``pvserver`` is not running, VISOR fails to connect after about ten
seconds and reports an error that names the ``host:port`` it tried.

Offscreen rendering on Linux
----------------------------

On a Linux machine without a display, both ``pvserver`` and the ``pvpython``
process that the API starts need an OpenGL context.  Use one of these options:

- A ParaView build with EGL or OSMesa support, which renders offscreen
  without an X server.
- A virtual X display: run ``pvserver`` and the VISOR API under ``xvfb-run``.
  VISOR does not wrap the ``pvpython`` process itself, so it inherits the
  display of the API process.