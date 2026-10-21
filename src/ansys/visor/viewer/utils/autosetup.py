"""
Auto-setup script for preparing Visor WASM assets.

This script downloads the required trame_vtklocal WASM content and
copies it into the frontend bundle. Intended for developers and CI builds.
"""

import re
import shutil
import site
import sys
from importlib import metadata
from pathlib import Path

import trame.app as trame_app
import trame_vtklocal.module as trame_vtklocal_module


def prepare_wasm_assets(project_root: Path) -> None:
    """Download and copy trame_vtklocal WASM assets into the frontend."""

    def get_vtk_version() -> str:
        version = re.findall(r"\d+(?:\.\d+)*|$", metadata.version("vtk"))[0]
        if not version:
            raise Exception("Could not parse VTK version")
        return version

    def download_wasm() -> None:
        server = trame_app.get_server()
        server.enable_module(trame_vtklocal_module)

    def copy_wasm(src: Path, dst: Path) -> None:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    # --- execution ---

    version = get_vtk_version()

    download_wasm()

    if sys.platform == "win32":
        site_packages = project_root / ".venv" / "Lib" / "site-packages"
    elif sys.platform in ["darwin", "linux"]:
        site_packages = Path(site.getsitepackages()[0])
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")

    # trame_vtklocal >= 1.6.2 no longer ships a flat "wasm/<version>" directory; it downloads
    # per-architecture builds on demand into "wasm32/<version>" and "wasm64/<version>" instead.
    # We bundle the wasm32 (non-threaded) build since it doesn't require crossOriginIsolated.
    src = site_packages / "trame_vtklocal" / "module" / "serve" / "wasm32" / version

    if not src.is_dir():
        raise Exception(f"WASM not found at: {src}")

    dst = project_root / "src" / "ansys" / "visor" / "visor-client" / "modules" / "wasm"
    copy_wasm(src, dst)


def main():
    """Main function to be called when the script is executed directly."""
    prepare_wasm_assets(Path.cwd())


if __name__ == "__main__":
    main()