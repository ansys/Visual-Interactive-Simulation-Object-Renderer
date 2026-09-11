.. _ref_release_notes:

Release notes
#############

This document contains the release notes for the project.

.. vale off

.. towncrier release notes start

`1.0.0 <https://github.com/ansys/visor/releases/tag/v1.0.0>`_ - September 11, 2026
==================================================================================

.. tab-set::


  .. tab-item:: Added

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Remote rendering 3.1a - add per-part write path to the dataset registry
          - `#50 <https://github.com/ansys/visor/pull/50>`_

        * - Remote rendering 3.1b - implement per-part apply logic on the renderer and node pipeline
          - `#51 <https://github.com/ansys/visor/pull/51>`_

        * - Remote rendering 3.1c - register per-part triggers, serialize VTK access with lock, trigger payload validation
          - `#52 <https://github.com/ansys/visor/pull/52>`_

        * - Remote rendering 3.1d - route client per-part mutations through the server triggers
          - `#53 <https://github.com/ansys/visor/pull/53>`_

        * - Remote rendering 3.1e - source per-part state from registry on save and restore it on load
          - `#54 <https://github.com/ansys/visor/pull/54>`_


  .. tab-item:: Fixed

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Apply selected to the scene-graph node and seed tree rows from node state
          - `#67 <https://github.com/ansys/visor/pull/67>`_

        * - Release issues
          - `#92 <https://github.com/ansys/visor/pull/92>`_

        * - Improving stage skipping for releasing
          - `#95 <https://github.com/ansys/visor/pull/95>`_

        * - Project metadata
          - `#97 <https://github.com/ansys/visor/pull/97>`_


  .. tab-item:: Documentation

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Configure CNAME for VISOR docs
          - `#37 <https://github.com/ansys/visor/pull/37>`_

        * - Capitalize project name in documentation
          - `#39 <https://github.com/ansys/visor/pull/39>`_

        * - Update email address to from ansys to synopsys
          - `#40 <https://github.com/ansys/visor/pull/40>`_

        * - Clean up doc installation section and remove unused Makefile
          - `#56 <https://github.com/ansys/visor/pull/56>`_

        * - Remove custom css from docs
          - `#57 <https://github.com/ansys/visor/pull/57>`_

        * - Clean up internal refs
          - `#71 <https://github.com/ansys/visor/pull/71>`_


  .. tab-item:: Maintenance

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Copy VISOR project from internal repo
          - `#1 <https://github.com/ansys/visor/pull/1>`_

        * - Update license file to MIT
          - `#5 <https://github.com/ansys/visor/pull/5>`_

        * - Clean up stale references to internal repo
          - `#9 <https://github.com/ansys/visor/pull/9>`_

        * - Push releases to public PyPI
          - `#11 <https://github.com/ansys/visor/pull/11>`_

        * - Add code of conduct file
          - `#45 <https://github.com/ansys/visor/pull/45>`_

        * - Disable/Remove internal workflows
          - `#47 <https://github.com/ansys/visor/pull/47>`_

        * - (draft) bump fast-uri to 4.1.3 per CVE-2026-76172
          - `#49 <https://github.com/ansys/visor/pull/49>`_

        * - Change license to Apache 2.0.  Add long form of the name
          - `#55 <https://github.com/ansys/visor/pull/55>`_

        * - Switch version from _beta to _dev and adjust nightly package version
          - `#64 <https://github.com/ansys/visor/pull/64>`_

        * - Add README badges and display license and code style
          - `#65 <https://github.com/ansys/visor/pull/65>`_

        * - Seed PartIndex positionally from VisorSceneBase.add_dataset's part-node list
          - `#66 <https://github.com/ansys/visor/pull/66>`_

        * - Prepare for public release
          - `#70 <https://github.com/ansys/visor/pull/70>`_

        * - Clean up internal refs in workflows
          - `#72 <https://github.com/ansys/visor/pull/72>`_

        * - License statement
          - `#90 <https://github.com/ansys/visor/pull/90>`_


.. vale on