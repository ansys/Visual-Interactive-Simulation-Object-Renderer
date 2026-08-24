"""Argument parsing for visor-cli"""

from argparse import ArgumentParser

from ansys.visor.viewer.core.visor_enums import RenderingMode


def parse_args():
    """Parse the command line arguments."""
    parser = ArgumentParser("visor-cli")

    parser.add_argument(
        "--api-host",
        default="localhost",
        help="API host (default: localhost)"
        )
    parser.add_argument(
        "--api-port",
        default=53211,
        type=int,
        help="API port (default: 53211)")

    subparsers = parser.add_subparsers(dest="group", required=True)


    #####################
    # Server subcommands
    #####################
    server_parser = subparsers.add_parser("server", help="Server operations")
    server_sub = server_parser.add_subparsers(dest="action", required=True)

    # start service
    server_sub.add_parser("start", help="Start the API server (runs uvicorn command)")

    # health API
    server_sub.add_parser("health", help="Check server health")

    # info API
    server_sub.add_parser("info", help="Print server info")

    # initialize API
    init_parser = server_sub.add_parser("init", help="Initialize a Visor instance")
    init_parser.add_argument("--host", default="localhost",
                             help="Instance host (default: localhost)")
    init_parser.add_argument("--port", type=int,help="Instance port (default: 0, meaning the app chooses an unused port)", default=0)
    init_parser.add_argument(
        "--rendering-mode",
        choices=[e.name for e in RenderingMode],
        default=None,
        help=(
            "Rendering mode to use. Choices: "
            + ", ".join(e.name for e in RenderingMode)
            + ". Default: LOCAL. Use HEADLESS for headless/no-GPU mode."
        ),
    )
    init_parser.add_argument(
        "--standalone",
        type=lambda x: x.lower() == "true",
        default=None,
        help="Standalone mode (True or False). Cannot be changed on an existing instance."
    )
    init_parser.add_argument(
        "--dark-mode",
        type=lambda x: x.lower() == "true",
        default=None,
        help="Dark mode (True or False, default: from settings or server default)"
    )

    # list API
    server_sub.add_parser("list", help="List Visor instances")


    ######################
    # Instance subcommands
    ######################
    instance_parser = subparsers.add_parser("instance", help="Instance operations")
    instance_sub = instance_parser.add_subparsers(dest="action", required=True)

    # start API
    start_parser = instance_sub.add_parser("start", help="Start a visualization")
    start_parser.add_argument("file_path", nargs="?", default=None, help="File to load in viewer")
    start_parser.add_argument("--metadata-path", type=str, default=None, help="Path to metadata JSON file")
    start_parser.add_argument("--timeout", type=int, default=0, help="Timeout in seconds")

    # update API
    update_parser = instance_sub.add_parser("update", help="Update with new input")
    update_parser.add_argument("file_path", help="File to update in viewer")
    update_parser.add_argument("--metadata-path", type=str, default=None, help="Path to metadata JSON file")

    # add dataset API
    add_dataset_parser = instance_sub.add_parser("add", help="Add new dataset to instance")
    add_dataset_parser.add_argument("file_path", help="File to update in viewer")
    add_dataset_parser.add_argument("--metadata-path", type=str, default=None, help="Path to metadata JSON file")

    # list datasets API
    instance_sub.add_parser("list", help="List datasets loaded in instance")

    # remove dataset API
    remove_dataset_parser = instance_sub.add_parser("remove", help="Remove dataset from instance")
    remove_dataset_parser.add_argument("dataset_id", type=int, help="ID of datasets to remove")

    # stop_visualization API
    instance_sub.add_parser("stop_visualization", help="Stop visualization")

    # stop API
    instance_sub.add_parser("stop", help="Stop and clean up the instance")

    # save state API
    save_state_sub = instance_sub.add_parser("save", help="Save the current state of the instance")
    save_state_sub.add_argument("state_dir", help="Directory to save the instance state")

    # load state API
    load_state_sub = instance_sub.add_parser("load", help="Load the current state of the instance")
    load_state_sub.add_argument("state_dir", help="Directory to load the instance state from")


    ######################
    # Logs subcommands
    ######################
    logs_parser = subparsers.add_parser("logs", help="Log file operations")
    logs_parser.add_argument("log_name", nargs="?", help="Name of the log file (without .log)")
    logs_parser.add_argument("-f", "--follow",
                             action="store_true",
                             help="Follow the log file (like tail -f)"
                             )
    logs_parser.add_argument("--log-dir",
                             default=None,
                             help="Directory containing log files (default: from settings)"
                             )
    logs_parser.add_argument(
        "-n", "--lines", type=int, default=10,
        help="Number of lines to show from the end of the log file (default: 10)"
    )

    return parser.parse_args()
