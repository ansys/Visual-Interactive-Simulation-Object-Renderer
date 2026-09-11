.. _installation-index:

Installation
#############

.. role:: ansys-gold

User installation
-----------------

You can run VISOR with Python 3.11 through Python 3.14 on Windows, macOS, and Linux.

Create and activate a virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To avoid conflicts with other Python packages, create and activate a `virtual environment <https://docs.python.org/3/tutorial/venv.html>`_
before you install VISOR.

#. Create a virtual environment:

   .. code:: console

      python -m venv .venv

#. Activate the virtual environment for your operating system.

   On Windows, run this command:

   .. code:: console

      .venv\Scripts\activate


   On Linux and macOS, run this command:

   .. code:: console

      source .venv/bin/activate

Install VISOR
~~~~~~~~~~~~~

In the virtual environment, install VISOR with all optional dependencies:

.. code:: console

   python -m pip install ansys-visor-viewer


Developer installation
----------------------

#. Check that the following prerequisites are installed:

   - `Poetry <https://python-poetry.org/docs/>`_
   - `Node.js & npm <https://nodejs.org/en/download/>`_

#. Clone the VISOR repository:

   .. code:: console

      git clone https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/.git
      cd visor

#. Create a virtual environment:

   .. code:: console

      python -m venv .venv

#. Activate the virtual environment for your operating system.

   On Windows, run this command:

   .. code:: console

      .venv\Scripts\activate

   On Linux and macOS, run this command:

   .. code:: console

      source .venv/bin/activate

#. Install and build VISOR in editable mode within the virtual environment:

   .. code:: console

      # Install VISOR Python dependencies and the setup script
      poetry install --with setup

      # Run the setup script to copy WASM modules to the correct location
      visor-setup

      # Build the frontend
      cd src\ansys\visor\visor-client
      npm install
      npm run build
      cd ..\..\..\.. # Go back to the root of the VISOR repository

      # Install Dash component
      cd src\ansys\visor\dash
      npm install
      npm run build
      cd ..\..\..\.. # Go back to the root of the VISOR repository


#. Verify your installation by importing the module:

   .. code:: pycon

      >>> from ansys.visor.viewer import Visor



