"""
Unit tests for what the streamed modules load on import.

A fresh interpreter imports the trame app and the state publisher a streamed
session uses, then reports every loaded module name.  Neither may pull in the
off-screen VTK pipeline, nor trame-vtklocal through it.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

_IMPORT_SCRIPT = (
    "import json, sys\n"
    "import ansys.visor.viewer.app.trame.server_app\n"
    "import ansys.visor.viewer.app.trame.server_state_publisher\n"
    "print(json.dumps(sorted(sys.modules)))\n"
)


@pytest.fixture(scope="module")
def loaded_modules() -> set[str]:
    """Module names loaded by a fresh interpreter after importing the streamed modules."""
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_SCRIPT],
        capture_output=True,
        text=True,
        check=True,
    )
    # Settings loading may print first; the module list is the last line.
    return set(json.loads(result.stdout.strip().splitlines()[-1]))


def test_streamed_imports_leave_server_renderer_unloaded(loaded_modules: set[str]) -> None:
    assert "ansys.visor.viewer.renderer.server_renderer" not in loaded_modules


def test_streamed_imports_leave_trame_vtklocal_unloaded(loaded_modules: set[str]) -> None:
    assert "trame_vtklocal" not in loaded_modules
