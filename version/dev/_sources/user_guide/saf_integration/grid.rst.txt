

VISOR is a shared technology component (STC) within the Solutions Application Framework (SAF) that provides a 3D
visualization environment for simulation data.
VISOR is designed to be integrated into SAF solutions, allowing users to visualize and interact with simulation results
in a consistent and user-friendly manner.

Product Instance Manager
------------------------

VISOR is exposed in the SAF solution through its Product Instance Management (PIM) functionality,
which provides a standardized interface for managing and accessing VISOR instances.
See more information in the `PIM documentation`_.




SAF integration examples
------------------------

Below are two examples of how to integrate VISOR into a SAF solution:

#. **SAF VISOR POC**:

   `SAF VISOR POC`_ is a simple example that demonstrates how to integrate
   VISOR into a SAF solution for interactive 3D visualization of engineering data.

#. **SAF reference solution**:

   `Airfoil Explorer`_ is a reference solution application
   showcasing integration of five key STCs through a guided workflow for defining airfoil geometry, generating a mesh,
   running a 2D potential flow solve, and visualizing results. Ideal as a template for building engineering solution
   apps.






.. _PIM documentation:
    https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/user_guide/backend/instance_management/index.html
.. _Airfoil Explorer:
    https://github.com/ansys-internal/airfoil-explorer
.. _SAF VISOR POC:
    https://github.com/ansys-internal/saf-theia-poc
