.. _configure-visor:

VISOR configuration
###################

Place a ``.visor`` file at the root of your project to customize runtime behavior,
including log paths, the default host and port, and UI preferences.

With a ``.visor`` file, you can override default values in the ``Settings`` class without code changes.
VISOR loads this YAML configuration file at startup.

When to use
===========

Use a ``.visor`` file for the following configuration tasks:

- Define team-wide defaults for paths, assets, and feature flags.
- Configure different deployment environments.
- Customize application behavior without editing source code.

VISOR applies the ``.visor`` file when you run VISOR as a service or use the Python API.


File name and location
======================

- Use ``.visor`` as the file name (YAML format).
- Place the file in the current working directory at startup.

VISOR reads the ``.visor`` file during initialization. If the file is not present, VISOR uses built-in defaults.


Precedence and merge rules
==========================

VISOR applies configuration values in the following order, from lowest to highest precedence:

1. Built-in ``Settings`` defaults
2. Values defined in the ``.visor`` file

Any values that you define in the ``.visor`` file override the corresponding default settings.


Settings defaults
=================

You can use a ``.visor`` file to override the following default values from the
`Settings class <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/blob/main/src/ansys/visor/viewer/config.py>`_:

.. code-block:: yaml

   app_name: "VISOR Viewer"
   default_host: "localhost"
   default_port: 8081
   default_standalone: False
   default_dark_mode: True
   default_log_dir: str(Path.cwd().joinpath("logs"))
   trame_log_dir: None
   binding_host: null

Descriptions of each setting follow:

- ``app_name``: VISOR application name to show in the title bar and window manager.
- ``default_host``: Default host for the VISOR server.
- ``default_port``: Default port for the VISOR server.
- ``default_standalone``: Whether VISOR runs in standalone mode by default.
- ``default_dark_mode``: Whether VISOR uses dark mode by default.
- ``default_log_dir``: Default directory for VISOR logs.
- ``trame_log_dir``: Directory for Trame logs. The default is ``None``, which disables Trame logging.
- ``binding_host``: Optional externally routed binding host. VISOR reads ``GLOW_PRODUCT_BINDING_HOST``
  at startup when present. Otherwise, VISOR leaves this value as ``null`` to allow per-instance host fallback.


Minimal example
===============

Here is a minimal example of a ``.visor`` file:

.. code-block:: yaml

   app_name: "VISOR Viewer Name Override"
   default_host: "localhost"
   default_port: 8088
   default_standalone: False
   default_dark_mode: True
   default_log_dir: "/path/to/custom_log_directory"
   trame_log_dir: "/path/to/trame/logs"
   binding_host: null


Environment variables
=====================

VISOR supports a small set of environment variables that affect runtime networking and TLS behavior:

- ``GLOW_PRODUCT_BINDING_HOST``: When you set this variable, VISOR reads it at startup and stores the value in
  ``binding_host``. Use it to provide an externally routed binding host so services and reverse proxies can
  determine the externally visible hostname used for routes.

- ``GLOW_CERTS_DIR`` and ``ANSYS_GRPC_CERTIFICATES``: VISOR checks these variables in that order. Use either
  variable to point to a directory that contains platform TLS certificate files. If a matching certificate/key pair
  exists (preferred filenames ``server.crt``/``server.key``, fallback filenames ``client.crt``/``client.key``),
  VISOR tries to auto-configure the internal Trame/wslink server so websocket endpoints can use WSS. If
  auto-configuration fails, VISOR logs the error and still starts the server.
