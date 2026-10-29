# Public-dependency SAF-Visor smoke fixture

This independently authored solution replaces the smoke test's external private
POC. Each installation resolves the latest stable public SAF SDK and related
SAF packages, including Dash support. It does not copy POC code, configuration,
dependencies or assets.
New fixture code follows the enclosing repository's licensing. This checkout
still has Ansys license metadata, so publishing the repository remains subject
to the repository owner's licensing review.

## Coverage and boundaries

Pytest starts the current Visor management API and the public GLOW API/UI
commands. It creates a real SAF project with an isolated local SQLite database
and BDM shared-volume storage. Clicking Initialize Visor invokes a SAF
transaction that initializes and starts Visor through its HTTP API. Browser
uploads run another SAF transaction, store the file through BDM, and pass the
cached file to Visor.

The two Chromium cases independently upload the existing `plate.vtp` and
`mesh.vtu` assets. The Visor management API and the GLOW API and UI start once
per test module. Each case creates a fresh SAF project, and Visor is reset
between cases with `POST /stop`, so the next `/initialize` creates a new empty
visualizer. Each case requires an empty initial scene, a ready embedded
WebGL canvas before upload, the expected single loaded dataset, a live canvas
after upload, no uncaught browser errors, and one newly saved VTKHDF dataset
with positive point/cell counts and bounds matching the input.

This is deliberately **not** a PIM or VisorManager test. It does not use SAF CLI
environment orchestration, desktop orchestration, product-instance decorators,
PIM Light, authentication, private feeds, remote databases or licensed products.
Public `glow_main` API/UI commands give the harness explicit process ownership
without requiring the optional desktop services. The Visor process is owned by
pytest, while its initialization and geometry update are driven by SAF.

## Local execution

Start from the repository root with Python 3.11-3.14 (the examples use 3.11). Build the current checkout,
including WASM, the client and generated Dash bindings. Do not substitute an old
published Visor wheel. The build environment remains separate from SAF because
SAF currently needs Dash 3 while the normal development environment may resolve
Dash 4.

Example in PowerShell, assuming the repository build environment is installed:

```powershell
poetry run visor-setup
npm --prefix src\ansys\visor\visor-client ci
npm --prefix src\ansys\visor\visor-client run build
npm --prefix src\ansys\visor\dash ci
poetry run npm --prefix src\ansys\visor\dash run build
poetry build --format wheel
py -3.11 -m venv .venv-saf
$wheel = (Get-ChildItem dist\*.whl | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
.\.venv-saf\Scripts\python.exe -m pip --isolated install --index-url https://pypi.org/simple --upgrade pip packaging
.\.venv-saf\Scripts\python.exe tests\fixtures\saf_visor_solution\install_latest.py $wheel
.\.venv-saf\Scripts\python.exe -m visor_saf_smoke.main analysis
.\.venv-saf\Scripts\python.exe -m playwright install chromium
.\.venv-saf\Scripts\python.exe -m pytest tests\e2e\smoke\test_smoke_saf_visor.py --browser chromium -v --durations=0 --junitxml=tests\artifacts\saf-smoke\reports\saf-smoke-junit.xml
```

On Ubuntu use `.venv-saf/bin/python` and run pytest with `DISPLAY` set to an
Xvfb display (or under `xvfb-run -a`) and `VTK_DEFAULT_RENDER_WINDOW_OFFSCREEN=1`,
with Mesa/libGL and the Chromium system dependencies installed. Use a new
`.venv-saf` after rebuilding the wheel, because pip skips a wheel whose version
is already installed. When building the wheel from a git checkout, Poetry skips
git-ignored build outputs. CI removes those ignore rules from `.gitignore`
first, as the release workflow does. The SAF smoke steps in the
[Python workflow](../../../.github/workflows/python-tests.yml) run in the
Python 3.11-3.14 legs of the `test` job and reuse their frontend and Dash builds.

## Dependencies and maintenance

Use [install_latest.py](install_latest.py) for every local installation and CI
run, after bootstrapping current pip and packaging as shown above. The fixture
manifest intentionally does not pin the SDK. The installer runs one eager
`pip install` of the wheel and the fixture, then compares every installed
`ansys-saf-*`, `ansys-bdm-*` and `ansys-iam-*` distribution with the newest
stable, non-yanked release on public PyPI. If any version is behind, it prints
a table of name, installed and latest versions and exits non-zero. This catches
pip silently backtracking to older releases when the latest ones conflict.
It then runs `pip check` and downloads the VTK WASM assets that `trame_vtklocal`
would otherwise fetch on the first Visor start, which makes the first browser
case fail with "WASM module is not loaded yet". Unused applications, such as SAF CLI and desktop
orchestration, are not installed.

The latest releases must be mutually compatible with the current Visor wheel
and Python runtime. Conflicts fail installation rather than falling back to
older SAF versions. Prereleases are excluded. Other dependencies resolve fresh
within their declared requirements. Installations are therefore intentionally
not reproducible across release dates. A direct `pip install` of the fixture
alone does not enforce this policy.

The installer writes the installed and latest versions to
`tests/artifacts/saf-smoke/dependencies/saf-versions.json`. Public-index
failures also fail explicitly. SAF SDK, its core packages and Visor all support
Python 3.11-3.14, and the pinned VTK publishes wheels for all of them, so the SAF
smoke test runs in every leg of the regular Python matrix. The wheel is
`py3-none-any`; each leg builds it and installs it into its own `.venv-saf`.

Review newly resolved packages and their licensing, run solution analysis,
and rerun both cases. Upstream SDK pins may intentionally conflict with newer
individual SAF releases. Such failures require investigation, not relaxed
latest-version constraints.

Selected runs fail when the fixture, services or assets are missing. The SAF
steps use `continue-on-error` like the other suites, and the shared
[JUnit checker](../../../.github/scripts/check_junit_results.sh) in the
`check_results` step gates the SAF report on every Python leg. It rejects
missing reports, failures and errors. It does not reject skipped-only runs or
enforce an expected case count, and the browser check only catches uncaught
page errors, not console errors. Ordinary test discovery excludes this
directory through `norecursedirs`. Release/nightly workflows are not extended
by this change.

Logs, package versions, installed Visor module/wheel provenance, browser errors,
screenshots, isolated project files and saved geometry are retained under
`tests/artifacts/saf-smoke`. Service logs and provenance are written once per
run, and each case writes its own `state`, `browser-errors.json`, `page.png`
and `visor-stop.json` to a subdirectory named after the case. Playwright traces
are saved on failure under `tests/artifacts/traces`. Server processes are
cleaned up as a tree at the end of the module, including on startup failure.
No external services or credentials should be needed at runtime.
