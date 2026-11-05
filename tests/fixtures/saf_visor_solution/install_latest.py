"""Install the current wheel with the latest stable public SAF dependencies."""

import argparse
import json
import subprocess
import sys
from importlib.metadata import distributions
from pathlib import Path
from urllib.request import urlopen

from packaging.utils import canonicalize_name
from packaging.version import Version

# Paths, PyPI endpoints, and the name prefixes of the SAF-family packages this script checks.
FIXTURE = Path(__file__).resolve().parent
ROOT = FIXTURE.parents[2]
DEFAULT_OUTPUT = ROOT / "tests" / "artifacts" / "saf-smoke" / "dependencies"
PYPI_INDEX = "https://pypi.org/simple"
PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"
SAF_PREFIXES = ("ansys-saf-", "ansys-bdm-", "ansys-iam-")
PIP = [sys.executable, "-m", "pip"]


def is_usable_release(version: Version, files: list[dict]) -> bool:
    """Return whether a release is stable and has at least one non-yanked file.

    Args:
        version: Parsed release version.
        files: PyPI file metadata entries for that release.
    """
    is_stable = not (version.is_prerelease or version.is_devrelease)
    has_available_file = any(not file.get("yanked") for file in files)
    return is_stable and has_available_file


def latest_release(name: str) -> str:
    """Return the newest stable, non-yanked version of a package on public PyPI.

    Args:
        name: Distribution name to look up.

    Raises:
        RuntimeError: If the package has no usable release.
    """
    # Fetch the package's release list from PyPI, keep only stable non-yanked versions, and return the highest.
    with urlopen(PYPI_JSON_URL.format(name=name), timeout=30) as response:
        releases = json.load(response)["releases"]
    usable = [
        Version(version) for version, files in releases.items()
        if is_usable_release(Version(version), files)
    ]
    if not usable:
        raise RuntimeError(f"No non-yanked stable public release exists for {name}")
    return str(max(usable))


def pip_install(wheel: Path) -> None:
    """Install the wheel and the fixture with its test extra, upgrading eagerly from public PyPI."""
    # --isolated ignores local pip config and environment variables, and --index-url limits lookups to public PyPI.
    # "eager" upgrades every dependency to its newest allowed version, not only the ones that conflict.
    command = [
        *PIP, "--isolated", "install",
        "--index-url", PYPI_INDEX,
        "--upgrade", "--upgrade-strategy", "eager",
        str(wheel.resolve()), f"{FIXTURE}[test]",
    ]
    subprocess.run(command, check=True)


def installed_saf_versions() -> dict[str, str]:
    """Return the installed version of every SAF, BDM and IAM distribution, keyed by canonical name."""
    # Walk the current environment and keep only the SAF-family distributions.
    versions = {}
    for dist in distributions():
        name = canonicalize_name(dist.metadata["Name"])
        if name.startswith(SAF_PREFIXES):
            versions[name] = dist.version
    return versions


def find_outdated(installed: dict[str, str], latest: dict[str, str]) -> list[tuple[str, str, str]]:
    """Return `(name, installed, latest)` for each package that is not at its latest version."""
    return [
        (name, installed[name], latest[name])
        for name in latest
        if Version(installed[name]) != Version(latest[name])
    ]


def print_outdated(outdated: list[tuple[str, str, str]]) -> None:
    """Print a table of the packages that are behind their latest release."""
    print(f"{'name':40} {'installed':12} latest")
    for name, installed, latest in outdated:
        print(f"{name:40} {installed:12} {latest}")


def prepare_wasm() -> None:
    """Download the VTK WASM assets that trame_vtklocal otherwise fetches on first server start.

    Without this, the first test that opens the viewer races the download and
    fails with "WASM module is not loaded yet".

    Raises:
        subprocess.CalledProcessError: If the download fails.
    """
    code = (
        "import trame.app as app, trame_vtklocal.module as module; "
        "app.get_server().enable_module(module)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def install(wheel: Path, output: Path) -> None:
    """Install the wheel and fixture, then verify every SAF package is the latest release.

    The versions are written to `saf-versions.json` in the output directory.
    The VTK WASM assets are downloaded once the packages verify.

    Args:
        wheel: Path to the current checkout's Visor wheel.
        output: Directory that receives `saf-versions.json`.

    Raises:
        ValueError: If `wheel` is not an existing `.whl` file.
        SystemExit: If any SAF package is not the latest release. This catches pip
            silently backtracking to older releases when the latest ones conflict.
    """
    # Fail early unless the input is an actual wheel file.
    if not wheel.is_file() or wheel.suffix != ".whl":
        raise ValueError(f"Expected the current checkout's wheel, got {wheel}")

    # Install the wheel and its test dependencies, then compare what is now installed with the latest PyPI releases.
    pip_install(wheel)

    installed = installed_saf_versions()
    latest = {name: latest_release(name) for name in sorted(installed)}
    # Save both sets of versions as a record of this run.
    output.mkdir(parents=True, exist_ok=True)
    report = {"installed": installed, "latest": latest}
    (output / "saf-versions.json").write_text(json.dumps(report, indent=2))

    # Fail the run if any SAF package is behind; otherwise confirm the dependency set is consistent with pip check.
    outdated = find_outdated(installed, latest)
    if outdated:
        print_outdated(outdated)
        sys.exit("Installed SAF packages are not the latest public releases.")
    subprocess.run([*PIP, "check"], check=True)
    prepare_wasm()


def main() -> None:
    """Parse the command line and run the installation."""
    # Command line: a required wheel path and an optional output directory.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, help="Path to the current Visor wheel")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Directory for saf-versions.json (default: %(default)s)",
    )
    args = parser.parse_args()
    install(args.wheel, args.output)


if __name__ == "__main__":
    main()
