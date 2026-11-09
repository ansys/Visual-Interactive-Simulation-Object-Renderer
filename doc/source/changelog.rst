.. _ref_release_notes:

Release notes
#############

This document contains the release notes for the project.

.. vale off

.. towncrier release notes start

`1.1.0 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/releases/tag/v1.1.0>`_ - November 09, 2026
=========================================================================================================================

.. tab-set::


  .. tab-item:: Breaking

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Remote rendering 4.1d: Add a SERVER rendering mode streamed through trame-rca
          - `#183 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/183>`_


  .. tab-item:: Added

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - [Remote rendering 3.2a] server-tracked camera: record, load-path write, and re-serialization
          - `#110 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/110>`_

        * - [Remote rendering 3.2b] save state reads from server camera
          - `#111 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/111>`_

        * - [Remote rendering 3.2c] attribute camera changes to the input that caused them
          - `#124 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/124>`_

        * - [Remote rendering 3.2d] report settled camera gestures to the server
          - `#125 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/125>`_

        * - [Remote rendering 3.3a] server-authoritative widget toggles and projection
          - `#137 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/137>`_

        * - [Remote rendering 3.3b] fold per-part edge visibility into the global toggle
          - `#138 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/138>`_

        * - [Remote rendering 3.3c] server-authoritative cross-section plane
          - `#139 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/139>`_

        * - [Remote rendering 3.3d] sync camera to server on orientation widget
          - `#143 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/143>`_

        * - [Remote rendering 3.4] server-owned UI panel and theme state
          - `#144 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/144>`_

        * - [Remote rendering 3.5a] move variable ownership to server
          - `#152 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/152>`_

        * - [Remote rendering 3.5b] client uses server owned variables
          - `#153 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/153>`_

        * - [Remote rendering 3.5c] Server creates color lookup table and client stops creating its own
          - `#161 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/161>`_

        * - Remote rendering 4.1a: Share VTK pipeline between client and server renderers
          - `#180 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/180>`_

        * - Remote rendering 4.1b: Add trame-rca as dependency and update wslink
          - `#181 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/181>`_

        * - Remote rendering 4.1c: Render frames on the server for streaming
          - `#182 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/182>`_

        * - Remote rendering 4.2a: Move CLIENT mode viewer wiring out of app
          - `#184 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/184>`_

        * - Remote rendering 4.2b: Choose viewer from server mode and show streamed frames
          - `#185 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/185>`_

        * - Remote rendering 4.3a: forward mouse and wheel input to server
          - `#186 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/186>`_

        * - Remote rendering 4.3b: Display the panels in server mode
          - `#187 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/187>`_

        * - Remote rendering 4.3c: Select parts by clicking a streamed frame
          - `#188 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/188>`_

        * - Remote rendering 4.6: Keep view fitted to the canvas on resize
          - `#189 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/189>`_

        * - Remote rendering 4.5: Record camera and cross section drags in SERVER mode
          - `#190 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/190>`_

        * - Remote rendering 4.4a: Update server mode panels when scene changes
          - `#194 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/194>`_

        * - Remote rendering 4.4b: move viewer wiring to custom classes
          - `#195 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/195>`_

        * - Remote rendering 4.5b: Send the cross-section plane to the server-mode client
          - `#196 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/196>`_

        * - Add geometry picker for server mode
          - `#199 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/199>`_

        * - Queue client-mode scene updates and skip the rebuild for data-only updates
          - `#202 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/202>`_

        * - Optimize update_variables endpoint by sending values as binary
          - `#212 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/212>`_


  .. tab-item:: Fixed

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Visor dash styling
          - `#109 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/109>`_

        * - Fix scalar variables not applying after re-selecting a part colored by a vector component
          - `#162 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/162>`_

        * - Normalize VTKHDF long arrays to fixed width for the wasm client
          - `#169 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/169>`_

        * - Release GL context in server mode after each server-rendered frame
          - `#198 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/198>`_

        * - Add render_window to magicmock in unit test
          - `#213 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/213>`_


  .. tab-item:: Documentation

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Enable badges on readme and remove stale link
          - `#105 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/105>`_

        * - Clean up version switcher logic after public release
          - `#106 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/106>`_

        * - Added measurement feature and updated graphics
          - `#120 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/120>`_

        * - Update saf link in readme
          - `#123 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/123>`_


  .. tab-item:: Maintenance

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Update CHANGELOG for v1.0.1
          - `#102 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/102>`_

        * - Bump main version after release
          - `#103 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/103>`_

        * - Add link to changelog.md
          - `#121 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/121>`_

        * - Exclude some packages from automated dependabot upgrades
          - `#132 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/132>`_

        * - Add a composite action to simplify workflows
          - `#141 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/141>`_

        * - Bump vtk to 9.7.0
          - `#146 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/146>`_

        * - Bump trame_vtklocal to 1.6.2
          - `#147 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/147>`_

        * - Align variable naming across stacks
          - `#150 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/150>`_

        * - Visor-cli updates for logs and init actions
          - `#151 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/151>`_

        * - [Remote rendering 3.6a] Cleanups after moving authority to server
          - `#165 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/165>`_

        * - [Remote rendering 3.6b] Resolve state on server and apply as given on the client
          - `#166 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/166>`_

        * - [Remote rendering 3.6c] Reserialize actor state inside the renderer apply methods
          - `#167 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/167>`_

        * - Add compatibility check with SAF SDK
          - `#170 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/170>`_

        * - [Remote rendering 3.6d] Deliver server state to the browser without sending it back
          - `#171 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/171>`_

        * - [Remote rendering] Clean up renderer interface before adding a second mode
          - `#176 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/176>`_

        * - Update ansys actions for CI CD. Add workspace file to gitignore
          - `#193 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/193>`_

        * - Add pip audit for vulnerability analysis
          - `#200 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/200>`_

        * - Library updates as per dependabot and pip-audit scans
          - `#201 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/201>`_


`1.0.1 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/releases/tag/v1.0.1>`_ - September 11, 2026
==========================================================================================================================

.. tab-set::


  .. tab-item:: Added

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Remote rendering 3.1a - add per-part write path to the dataset registry
          - `#50 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/50>`_

        * - Remote rendering 3.1b - implement per-part apply logic on the renderer and node pipeline
          - `#51 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/51>`_

        * - Remote rendering 3.1c - register per-part triggers, serialize VTK access with lock, trigger payload validation
          - `#52 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/52>`_

        * - Remote rendering 3.1d - route client per-part mutations through the server triggers
          - `#53 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/53>`_

        * - Remote rendering 3.1e - source per-part state from registry on save and restore it on load
          - `#54 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/54>`_


  .. tab-item:: Fixed

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Apply selected to the scene-graph node and seed tree rows from node state
          - `#67 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/67>`_

        * - Release issues
          - `#92 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/92>`_

        * - Improving stage skipping for releasing
          - `#95 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/95>`_

        * - Project metadata
          - `#97 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/97>`_

        * - Moving to poetry 2 build
          - `#99 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/99>`_

        * - Only provide code in GitHub release
          - `#101 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/101>`_


  .. tab-item:: Documentation

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Configure CNAME for VISOR docs
          - `#37 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/37>`_

        * - Capitalize project name in documentation
          - `#39 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/39>`_

        * - Update email address to from ansys to synopsys
          - `#40 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/40>`_

        * - Clean up doc installation section and remove unused Makefile
          - `#56 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/56>`_

        * - Remove custom css from docs
          - `#57 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/57>`_

        * - Clean up internal refs
          - `#71 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/71>`_


  .. tab-item:: Maintenance

    .. list-table::
        :header-rows: 0
        :widths: auto

        * - Copy VISOR project from internal repo
          - `#1 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/1>`_

        * - Update license file to MIT
          - `#5 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/5>`_

        * - Clean up stale references to internal repo
          - `#9 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/9>`_

        * - Push releases to public PyPI
          - `#11 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/11>`_

        * - Add code of conduct file
          - `#45 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/45>`_

        * - Disable/Remove internal workflows
          - `#47 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/47>`_

        * - (draft) bump fast-uri to 4.1.3 per CVE-2026-76172
          - `#49 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/49>`_

        * - Change license to Apache 2.0.  Add long form of the name
          - `#55 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/55>`_

        * - Switch version from _beta to _dev and adjust nightly package version
          - `#64 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/64>`_

        * - Add README badges and display license and code style
          - `#65 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/65>`_

        * - Seed PartIndex positionally from VisorSceneBase.add_dataset's part-node list
          - `#66 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/66>`_

        * - Prepare for public release
          - `#70 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/70>`_

        * - Clean up internal refs in workflows
          - `#72 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/72>`_

        * - License statement
          - `#90 <https://github.com/ansys/Visual-Interactive-Simulation-Object-Renderer/pull/90>`_


.. vale on