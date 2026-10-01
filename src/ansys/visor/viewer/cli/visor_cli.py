"""Command line interface for Visor Viewer."""

import sys

import requests

from ansys.visor.viewer.cli.apis import (
    InstanceAPI,
    LogsAPI,
    ServerAPI,
)
from ansys.visor.viewer.cli.parse_args import parse_args
from ansys.visor.viewer.config import settings


def check_server_running(host, port):
    """Check if the server is running by making a health check request"""
    try:
        binding_host = settings.binding_host or host
        scheme = settings.url_scheme
        resp = requests.get(f"{scheme}://{binding_host}:{port}/health", timeout=1)
        if resp.status_code == 200:
            return True
        print("Server health check failed:", resp.text)
    except Exception as e:
        print("Could not connect to server:", e)
    return False

def check_server_reachable(host, port):
    """
    Check whether anything is listening on the server address, healthy or not.

    Intended for guarding destructive commands: any HTTP response (including
    errors such as 500) or an established-but-failing connection counts as
    reachable.  Returns False only when a connection cannot be established.
    """
    binding_host = settings.binding_host or host
    url = f"{settings.url_scheme}://{binding_host}:{port}/health"
    try:
        requests.get(url, timeout=1)
    except requests.exceptions.SSLError:
        return True  # TCP connection was made; something is listening
    except requests.exceptions.ConnectionError:
        return False  # refused or connect timeout: nothing is listening
    except requests.exceptions.RequestException:
        return True  # e.g. read timeout: connected but no reply, assume running
    except Exception:
        return True  # unknown failure: assume the server may be running
    return True

def check_init_args(
        api_host,
        api_port,
        host,
        port,
        rendering_mode,
        standalone,
        dark_mode,
):
    """
    If the user explicitly passed --rendering-mode, --standalone, or --dark-mode, check whether
    the target instance already exists.  These flags have no effect when
    connecting to an existing instance, so we treat it as an error to
    prevent silent misconfiguration.
    """
    # Check if --rendering-mode, --standalone, or --dark-mode args are passed
    user_set_flags = []
    if rendering_mode is not None:
        user_set_flags.append("--rendering-mode")
    if standalone is not None:
        user_set_flags.append("--standalone")
    if dark_mode is not None:
        user_set_flags.append("--dark-mode")

    # If neither is passed, no need to check for existing instance since we're not trying to set any params
    if not user_set_flags:
        return

    # If --standalone or --dark_mode args are passed, check if target instance already exists on server
    binding_host = settings.binding_host or host
    scheme = settings.url_scheme
    target_url = f"{scheme}://{binding_host}:{port}"
    try:
        api_scheme = settings.url_scheme
        existing = requests.get(
            f"{api_scheme}://{api_host}:{api_port}/", timeout=5
        ).json().get("urls", [])
    except Exception as e:
        print(f"Warning: could not check existing instances: {e}")
        existing = []

    if target_url in existing:
        print(
            f"\nError: Instance already initialized on {target_url}.\n"
            f"Cannot use {', '.join(user_set_flags)} when connecting to an existing instance. "
            f"{'These values are' if len(user_set_flags) > 1 else 'This value is'}"
            " fixed at creation time and cannot be changed.\n"
        )
        sys.exit(1)

def needs_server_running(args):
    """
    Determine if the current command requires a running server.
    Returns False if the command is 'server start', 'server health', or 'logs'.
    """
    if args.group == "logs" or \
       args.group == "server" and args.action in ["start", "health"]:
        return False
    return True

def needs_server_stopped(args):
    """
    Determine if the current command requires a stopped server.
    Returns True if the command is 'logs clear'.
    """
    return args.group == "logs" and args.action == "clear"


def main():
    """Main CLI tool for Visor Viewer."""
    args = parse_args()

    # Most commands talk to the server, so make sure it is up first
    if needs_server_running(args):
        if not check_server_running(args.api_host, args.api_port):
            print("Server is not running. Please start the server first.")
            sys.exit(1)

    # Clearing logs while the server is writing to them is unsafe
    if needs_server_stopped(args):
        print(f"Checking if the server is running on {args.api_host}:{args.api_port}...")
        if check_server_reachable(args.api_host, args.api_port):
            print(
                f"Server is running on {args.api_host}:{args.api_port}. "
                "Please stop the server before clearing logs."
            )
            sys.exit(1)

    # Execute the appropriate API action based on the group and action
    if args.group == "server":
        api = ServerAPI(args.api_host, args.api_port)
        if args.action == "start":
            api.start()
        elif args.action == "health":
            api.health()
        elif args.action == "info":
            api.info()
        elif args.action == "init":
            check_init_args(
                args.api_host,
                args.api_port,
                args.host,
                args.port,
                args.rendering_mode,
                args.standalone,
                args.dark_mode,
            )
            api.initialize(args.host, args.port, args.rendering_mode, args.standalone, args.dark_mode, args.start)
        elif args.action == "list":
            api.list()
    elif args.group == "instance":
        api = InstanceAPI(args.api_host, args.api_port)
        if args.action == "start":
            api.start(args.file_path, args.metadata_path, args.timeout)
        elif args.action == "update":
            api.update(args.file_path, args.metadata_path)
        elif args.action == "add":
            api.add_dataset(args.file_path, args.metadata_path)
        elif args.action == "remove":
            api.remove_dataset(args.dataset_id)
        elif args.action == "list":
            api.list_datasets()
        elif args.action == "stop_visualization":
            api.stop_visualization()
        elif args.action == "stop":
            api.stop()
        elif args.action == "save":
            api.save(args.state_dir)
        elif args.action == "load":
            api.load(args.state_dir)

    if args.group == "logs":
        api = LogsAPI(log_dir=args.log_dir)
        if args.action == "list":
            api.list_logs()
        elif args.action == "tail":
            api.tail_log(args.log_name, args.follow, args.lines)
        elif args.action == "clear":
            api.clear_logs(args.force)
        return



if __name__ == "__main__":
    main()
