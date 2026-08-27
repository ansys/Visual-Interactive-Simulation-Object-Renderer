.. _contributing-index:

Contributing to VISOR
#####################

Use this guide to contribute to ``VISOR``.

Ansys, part of Synopsys, maintains ``VISOR`` and reviews every submission before merging.
You can also help other users, answer questions, and contribute features that make the software more useful.

Before you contribute to ``VISOR``, read the
`Contributing <https://dev.docs.pyansys.com/how-to/contributing.html>`_ topic
in the **PyAnsys developer's guide**.


Clone the repository
====================

Follow the steps in the installation section of the :ref:`installation-index` to set up VISOR in development mode.


Commit message guidelines
=========================

This project follows the `Conventional Commits <https://www.conventionalcommits.org>`_ specification.

Commit format
-------------

Use these prefixes in your commit messages:

- Use ``feat:`` for a new feature.
- Use ``fix:`` for a bug fix.
- Use ``docs:`` for documentation updates only.
- Use ``chore:`` for maintenance tasks that do not affect production code.
- Use ``refactor:`` for code restructuring that does not change behavior.
- Use ``style:`` for formatting or style changes that do not affect logic.
- Use ``test:`` for adding or modifying tests.
- Use ``ci:`` for CI configuration changes.
- Use ``build:`` for build script or dependency changes.

Branch naming conventions
-------------------------

Use these branch name prefixes:

- Use ``fix`` for minor bug fixes, patches, or experiments.
- Use ``feat`` for a new feature or significant addition.
- Use ``junk`` for experimental changes that you can delete if they go stale.
- Use ``maint`` for general repository or CI maintenance.
- Use ``doc`` for documentation-only changes.
- Use ``no-ci`` for low-impact work that should not trigger CI.
- Use ``testing`` for test improvements or test-related changes.
- Use ``release`` for release work.


Run tests
=========

Install the development packages that you need to run tests:

.. code-block:: bash

    poetry install --with dev



Run tests for each layer
------------------------

Use the following test layers in the ``tests/`` directory:

.. list-table::
    :header-rows: 1

    * - Layer
      - Location
      - Description
    * - Unit
      - ``tests/unit/``
      - Fast, isolated component tests
    * - Frontend unit
      - ``src/ansys/visor/visor-client/``
      - TypeScript/React component tests (Jest)
    * - Integration
      - ``tests/integration/``
      - Multi-component interaction tests
    * - Smoke
      - ``tests/e2e/smoke/``
      - WebGL render and interaction sanity checks (Playwright)
    * - Regression
      - ``tests/e2e/regressions/``
      - Visual snapshot and component state validation (Playwright)
    * - SAF integration
      - ``tests/e2e/smoke/test_smoke_saf_visor*.py``
      - ``saf``-marked smoke tests against a real ``saf-visor-poc`` solution (Playwright)
    * - Notebooks
      - ``tests/notebooks/``
      - Jupyter


.. note::
    When you run ``pytest`` from the project root, it discovers only ``unit`` and ``integration`` tests by default.
    Run smoke, regression, and Notebook tests explicitly, as shown in the next sections.

Run unit and integration tests:

.. code-block:: bash

    # Unit and integration (default discovery)
    poetry run pytest tests/unit tests/integration

    # With verbose output
    poetry run pytest tests/unit tests/integration -v

    # Filter by marker
    poetry run pytest tests -m "unit"
    poetry run pytest tests -m "not e2e"

    # With coverage report
    poetry run pytest tests/unit tests/integration --cov=src --cov-report=html


Run end-to-end tests (Playwright)
---------------------------------

Install Playwright before you run end-to-end (e2e) tests:

.. code-block:: bash

    poetry run playwright install chromium


Run smoke and regression tests:

.. code-block:: bash

    poetry run pytest tests/e2e/smoke
    poetry run pytest tests/e2e/regressions


In **Linux headless environments**, e2e tests require a virtual display. Set these variables before you run e2e tests:

.. code-block:: bash

    Xvfb :99 -screen 0 1920x1080x24 &
    export DISPLAY=:99
    export VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN=1


If a test fails, Playwright saves traces as ZIP files in the ``tests/artifacts/traces/`` directory.


Run SAF integration smoke tests
-------------------------------

``tests/e2e/smoke/test_smoke_saf_visor.py`` verify that ``saf-visor-poc`` correctly loads and visualizes
VTK files through VISOR when run as a SAF/Glow solution.
These tests are marked ``saf`` and are skipped automatically when the
``saf`` CLI is not available on ``PATH``.

They also require a local clone of ``saf-visor-poc``, pointed to via the ``--saf-project-dir``
option or the ``SAF_VISOR_POC_DIR`` environment variable:

.. code-block:: bash

    poetry run pytest tests/e2e/smoke -m saf --saf-project-dir "/path/to/saf-visor-poc"

    # or, using the environment variable
    export SAF_VISOR_POC_DIR="/path/to/saf-visor-poc"
    poetry run pytest tests/e2e/smoke -m saf


The test launches its own ``saf run`` subprocess (module-scoped fixture) against a fresh
port pair and tears it down afterward. Notes:

- SAF server startup (including SAF/Glow log noise and the VISOR launch alert) can take up to
  ~2 minutes; do not lower the fixture's timeouts without reproducing locally first.
- The test retries the file upload a few times if it hits the transient
  "shared product instance ... has not been initialized" GLOW error, which can occur briefly
  after the VISOR launch alert appears.
- If tests hang or fail with a ``500`` error or a launch-alert timeout, check for orphaned
  ``saf``/``dotnet`` (PIM Light Server) processes left over from a previous interrupted run
  and stop them before retrying.


Run Notebook tests
------------------

.. code-block:: bash

    poetry run pytest --nbval tests/notebooks/


Run frontend unit tests (Jest)
------------------------------

Run the TypeScript/React frontend test suite with Jest. You do not need the Python environment for these tests.

.. code-block:: bash

    cd src/ansys/visor/visor-client
    npm run test


To generate a JUnit XML report for CI:

.. code-block:: bash

    JEST_JUNIT_OUTPUT_DIR=../../../../tests/artifacts/unit \
    JEST_JUNIT_OUTPUT_NAME=frontend-junit.xml \
    npx jest --ci --reporters=default --reporters=jest-junit --verbose


Jest writes report files to the ``tests/artifacts/unit/`` directory alongside the Python unit test reports:

- ``frontend-junit.xml``: JUnit XML result file
- ``frontend-result.log``: Console output log

Set testing options
-------------------

Update canonicals
~~~~~~~~~~~~~~~~~

If you change UI elements or example models, smoke and regression tests that use image comparison might fail.
Update the canonical images either by replacing the baseline image manually or by running ``pytest`` with the
``--update-baseline`` option:

.. code-block:: bash

    poetry run pytest ./tests/e2e/smoke --update-baseline
    poetry run pytest ./tests/e2e/regressions --update-baseline


If no canonical image is found, ``pytest`` uses this option by default and skips the test on the first run.


Use a different location for canon images
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, canonical images are stored in the ``tests/references`` directory. Use the ``--baseline-dir`` option to
change this path:

.. code-block:: bash

    poetry run pytest ./tests/e2e/smoke --baseline-dir "tests/new_ref_loc"


If the directory does not exist, ``pytest`` creates it and generates a new baseline image on the first run.


Set a different pixel threshold
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you create new tests for visual elements, you might need to adjust the pixel threshold.
The RMS difference is usually 0, but some models or mappings can introduce small session-to-session variations.
The default threshold is 2.55 RMS.

To set a different pixel threshold:

.. code-block:: bash

    poetry run pytest ./tests/e2e/smoke --pixel-threshold 5


This does not update the default value.

Use a different host
~~~~~~~~~~~~~~~~~~~~

By default, ``VISOR`` launches on ``127.0.0.1``. To test against a different host, use the ``--host`` option:

.. code-block:: bash

    poetry run pytest ./tests/e2e/smoke --host 0.0.0.0


Build and view documentation locally
====================================

Sphinx generates the ``VISOR`` documentation. The source files are in the ``doc`` directory.
The ``.github/workflows/nightly-docs.yml`` workflow rebuilds the documentation nightly.

Build documentation
-------------------

To build the documentation locally, perform the following steps:

.. code-block:: bash

    # navigate to the docs directory
    cd docs

    # Install the documentation dependencies
    poetry install --with doc

    # Build the documentation
    # on Windows:
    make.bat html
    # on Linux:
    make html


After the build completes, open the ``index.html`` file in the ``_build/html`` directory in a web browser.

For example, if you cloned the ``VISOR`` repository to ``file:///C:/SYNOPSYSDev/NoBackup/visor``, open
the ``file:///C:/SYNOPSYSDev/NoBackup/visor/doc/_build/html/index.html`` file in a web browser.


Set up the documentation version switcher (optional)
----------------------------------------------------

The documentation version switcher lets you toggle between documentation versions. The ``doc/source/conf.py`` file
configures it. During the release process, the build generates a ``versions.json`` file and commits it to the
``gh-pages`` branch, which is not present in ``main``.

The version switcher works only on the live documentation site or when you serve the documentation from a
local web server. If you open ``index.html`` directly from the filesystem, the version switcher is disabled.

To enable the version switcher while serving the documentation locally, follow these steps:

1. Create a GitHub Personal Access Token (PAT).

The version switcher fetches the ``versions.json`` file from the private VISOR repository,
which requires authentication.

- Go to `Personal access tokens (classic) <https://github.com/settings/tokens>`_ in the GitHub developer settings.
- Click **Generate new token** and select the **Generate new token (classic)** option.
- Check the ``repo`` scope only.
- Click **Generate token** and copy the value.
- Activate the token for use in the Ansys and Ansys-internal organizations.
- Set the token as an environment variable named ``GITHUB_TOKEN``.


Note: The documentation deployment GitHub workflow generates a PAT automatically.


2. Serve with a local web server.

Because of browser security restrictions, serve the documentation over HTTP for the version switcher to work:

.. code-block:: bash

    cd doc
    python -m http.server 8000


Then open the `http://localhost:8000/_build/html/index.html <http://localhost:8000/_build/html/index.html>`_ file.
