# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

"""Interact with a running SAF-launched Visor instance's FastAPI management server.

This is done so e2e tests can discover the Visor management API and drive it (e.g. save_state)
without going through the SAF Dash UI.

The API host:port is assigned dynamically by PIM per project and isn't persisted
by saf-visor-poc, so you must supply it explicitly (--api-host/--api-port) or point
--log-file at a saf run log whose stdout was redirected to a file (e.g. via


Subcommands
-----------
list-datasets   List loaded datasets, then the variables (grouped by part) of the
                sole loaded dataset. If more than one dataset is loaded, a warning
                is printed and only the first dataset's variables are shown.
save-state      Save the visualizer's current state to a directory and print where
                it was saved. The directory path is resolved on the machine Visor
                is running on, not necessarily the machine running this script.

Examples
--------
python visor_api_tool.py --api-host 127.0.0.1 --api-port 60537 list-datasets
python visor_api_tool.py --log-file /tmp/saf_run.log save-state /tmp/visor_state
"""

import argparse
import json
import re
import sys

import requests

API_HOST_PORT_RE = re.compile(r"Visor API host:\s*(.+?),\s*port:\s*(\d+)", re.DOTALL)


def _read_log_text(log_file: str) -> str:
    """Read a log file, auto-detecting its encoding.
    """
    with open(log_file, "rb") as f:
        raw = f.read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8", errors="replace")


def discover_from_log(log_file: str) -> tuple[str, int]:
    """Extract the Visor management API host/port from a saf run log file."""
    content = _read_log_text(log_file)

    match = API_HOST_PORT_RE.search(content)
    if not match:
        raise RuntimeError(
            f"Could not find a 'Visor API host: <host>, port: <port>' line in {log_file}. "
            "Make sure the SAF project has launched Visor at least once, and that "
            "safs stdout was redirected to the log file."
        )
    host = match.group(1).strip()
    return host, int(match.group(2))


def _request(method: str, api_host: str, api_port: int, path: str, **kwargs) -> dict:
    """Call the Visor management API and return the parsed JSON body."""
    base = f"http://{api_host}:{api_port}"
    resp = requests.request(method, f"{base}{path}", **kwargs)
    if resp.status_code == 503:
        raise RuntimeError(
            "Visor responded 503: no active visualizer instance. "
            "The SAF project must have called /initialize + /start (i.e. Visor "
            "must have been opened at least once) before this operation can be performed."
        )
    resp.raise_for_status()
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise RuntimeError(
            f"{api_host}:{api_port} did not return JSON (Content-Type: "
            f"{resp.headers.get('Content-Type')!r}). This is likely NOT the Visor management "
            "API - check you didn't pass SAF's Solution UI or Solution API port by mistake."
        )
    return resp.json()


def list_datasets(api_host: str, api_port: int) -> dict:
    """Call the Visor management API and return the loaded datasets."""
    return _request("GET", api_host, api_port, "/list_datasets", timeout=30).get("datasets", {})


def list_variables(api_host: str, api_port: int, dataset_id: int) -> list:
    """Call the Visor management API and return the variables for a dataset, grouped by part."""
    return _request("GET", api_host, api_port, f"/{dataset_id}/list_variables", timeout=30).get("parts", [])


def save_state(api_host: str, api_port: int, state_dir: str) -> str:
    """Call the Visor management API to save the current state; return the server's success message."""
    body = _request("POST", api_host, api_port, "/save_state", json={"state_dir": state_dir}, timeout=60)
    return body.get("success", "")


def resolve_api_host_port(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[str, int]:
    """Resolve --api-host/--api-port either directly or via --log-file discovery."""
    if args.log_file:
        try:
            return discover_from_log(args.log_file)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
    if args.api_host and args.api_port:
        return args.api_host, args.api_port
    parser.error("Provide either --log-file, or both --api-host and --api-port.")


def run_list_datasets(api_host: str, api_port: int) -> None:
    try:
        datasets = list_datasets(api_host, api_port)
    except requests.ConnectionError:
        print(f"Could not connect to {api_host}:{api_port}. Is the Visor API server running?", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    if not datasets:
        print("No datasets are currently loaded.")
        return

    print(json.dumps(datasets, indent=2))

    if len(datasets) > 1:
        print(
            f"\nWarning: {len(datasets)} datasets are loaded, showing variables for the first one only.",
            file=sys.stderr,
        )
    dataset_id = next(iter(datasets))

    try:
        parts = list_variables(api_host, api_port, int(dataset_id))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(f"\nVariables for dataset {dataset_id}:")
    print(json.dumps(parts, indent=2))


def run_save_state(api_host: str, api_port: int, state_dir: str) -> None:
    try:
        message = save_state(api_host, api_port, state_dir)
    except requests.ConnectionError:
        print(f"Could not connect to {api_host}:{api_port}. Is the Visor API server running?", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-host", help="Host of the Visor management API server.")
    parser.add_argument("--api-port", type=int, help="Port of the Visor management API server.")
    parser.add_argument("--log-file", help="Path to a saf run log to auto-discover --api-host/--api-port from.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list-datasets",
        help="List loaded datasets and the variables of the sole loaded dataset.",
    )

    save_state_parser = subparsers.add_parser(
        "save-state",
        help="Save the visualizer's current state to a directory.",
    )
    save_state_parser.add_argument(
        "state_dir",
        help="Directory to save the state to (resolved on the Visor server's machine).",
    )

    args = parser.parse_args()
    api_host, api_port = resolve_api_host_port(args, parser)

    print(f"Using Visor management API at {api_host}:{api_port}", file=sys.stderr)

    if args.command == "list-datasets":
        run_list_datasets(api_host, api_port)
    elif args.command == "save-state":
        run_save_state(api_host, api_port, args.state_dir)


if __name__ == "__main__":
    main()
