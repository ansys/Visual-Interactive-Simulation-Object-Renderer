
# ADR 09: VISOR Logging

## Table of Contents
- [Decision](#decision)
- [Context](#context)
    - [Unifying Logging in VISOR](#unifying-logging-in-visor)
    - [Adding Trame Logs in VISOR](#adding-trame-logging-in-visor)
- [Proposed Changes](#proposed-changes)
  - [Unify Logging](#unify-logging)
  - [Trame Logging](#trame-logging)
- [Example Log Output](#example-log-output)
- [Observability Compliance](#observability-compliance)
- [Related Issues](#related-issues)



## Decision

* Unify the VISOR Python logging by implementing a custom VisorLogger class and
using it throughout the project.
* Add a default log directory where all Python logs are stored, configured in the `config.Settings` class.
* Allow a user to enable additional trame logging to a customizable log location, by adding a keyword
argument to the VISOR class constructor. In standalone VISOR, this is configured in the `config.Settings`
class and passed to the VISOR class upon instantiation.

## Context


### Unifying Logging in VISOR

Logging in the VISOR Python code is currently configured separately in individual VISOR viewer modules.  Most of the
modules set up logging something like the following example code from `application.py`:
```angular2html
import logging
logger = logging.getLogger(__name__)
log_path = path.join(curdir, "logs")
from pathlib import Path

Path(log_path).mkdir(parents=True, exist_ok=True)
file = path.join(log_path, "visor.log")
logging.basicConfig(filename=file, encoding="utf-8", level=logging.DEBUG)
```

There are a few reasons why we would benefit from centralizing this code for consistency across the project.
1. **Adds consistency in logging across the project**: This would allow our logs to be consistent in the log naming,
output location, formatting, and log level.
2. **Simplifies logging setup**: Easier to set up logging by utilizing reusable components.
3. **Adds clarity in logging practices**: Having centralized logging in the project allows us to more
easily evaluate and make changes to to comply with Ansys standards.


### Adding Trame Logging in VISOR

In addition to the existing logging in VISOR, a user may want extra log info coming from Trame.

We would like to allow a user to optionally enable additional logging about the Trame server, and for
them to be able to select the output location where those logs are written.

By default, this option would be disabled.



## Proposed Changes

### Unify Logging
We can create a VisorLogger subclass of the Python logging.Logger class, where the file handling is centralized, and
the default logging level and format are defined.

We can define a default log directory within the application `config.Settings` class as follows:
```angular2html
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "VISOR Viewer"
    default_host: str = "localhost"
    default_port: int = 8081
    default_standalone: bool = True
    default_log_dir: str = str(Path.cwd().joinpath("logs")) # New setting
```

The following VisorLogging class can use the `default_log_dir` as a default if no other directory is set.
```angular2html
"""Logging configuration"""
import logging
from logging import Logger
from pathlib import Path

from ansys.visor.viewer.config import Settings

class VisorLogger(Logger):
    """
    Custom logger for the VISOR app.
    This logger writes logs to a file, allows setting the log level,
    and ensures the log directory exists.
    Args:
        name (str): The name of the logger, typically the module or class name.
        filename (str): The name of the log file.
        log_dir (Optional[str]): Directory to save logs.
                                 Default is the default_log_dir from config settings.
        level (int): Logging level. Default is logging.DEBUG.
    """

    # Logging format to comply with Ansys ADR:
    # https://github.com/ansys-internal/architecture-decision-records/blob/main/content/docs/adrs/0016-observability-strategy.md
    LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d %(funcName)s()] - %(message)s"
    ENCODING = "utf-8"

    def __init__(self,
                 name: str,
                 filename: str,
                 log_dir: str | None = None,
                 level: int =logging.DEBUG):
        # Initialize the parent class
        super().__init__(name, level)

        # Log level
        self.level = level

        # Set up the log directory and file path
        self.filename = filename
        self.log_dir = log_dir
        if log_dir is None:
            settings = Settings()
            self.log_dir = settings.default_log_dir
        self.file_path = self.get_file_path()

        # Ensure the log directory exists
        self.create_dir()

        # Configure the root logger via basicConfig
        # (this will affect any logger that doesn't have a handler)
        logging.basicConfig(
            level=level,
            format=self.LOGGING_FORMAT,
            handlers=[
                logging.FileHandler(
                    self.file_path,
                    encoding=self.ENCODING
                )
            ],
        )

        # Create file handler and set logging level
        file_handler = logging.FileHandler(
            self.file_path,
            encoding=self.ENCODING
        )
        file_handler.setLevel(level)

        # Add formatter for file handler
        formatter = logging.Formatter(self.LOGGING_FORMAT)
        file_handler.setFormatter(formatter)

        self.addHandler(file_handler)

        # Prevent propagation to the root logger
        self.propagate = False

    def create_dir(self) -> None:
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)

    def get_file_path(self) -> Path:
        return Path(self.log_dir).joinpath(self.filename)
```

For convenience, we can also create a subclass of the above that uses the default log directory from the project settings,
and writes to a file called `visor.log`.

```angular2html
class VisorDefaultLogger(VisorLogger):
    """
    Custom logger for VISOR app with a default log file.
    This logger writes to a fixed log file named "visor.log", ensuring
    consistency across multiple modules within the project.
    It inherits from the VisorLogger class, which allows for centralized
    configuration and logging.
    This default logger is intended for logging all of the project-related
    messages to the same log file across different modules while maintaining
    a consistent logging format and level.
    Args:
        name (str): The name of the logger, typically the module or class name.
    """
    def __init__(self, name):
        # Initialize the parent class
        super().__init__(name, "visor.log")
```


To summarize:

* Create a `default_log_dir` in the `Settings` class, which a user will configure for
the needs of their application.
* Create a `VisorLogger` subclass of the Python `logging.Logger` class, which sets up logging to a file,
allows setting the log level, and ensures the log directory exists. If a log directory is not specified, use the
default_log_dir from the Settings class.
  * Note that within `VisorLogger` the `basicConfig` is configured, which enables any logger that doesn't
  have a handler to continue to write to the specified log file even if it is not using the logger
  explicitly (e.g. the trame logger currently, but any other framework that does logging under the
  hood will be captured by this too).
* Created a `VisorDefaultLogger` subclass of `VisorLogger` which takes only the logger name
(usually the file name) as input, and writes out to a file called `visor.log` in the `default_log_dir` directory. This class is a convenience that was created to simplify and unify the logging across modules.
* Use `VisorDefaultLogger` in most of the viewer modules (anywhere that had `visor.log` specified as the
output log file previously).
* Use `VisorLogger` to log to `server.log`


**Substantive changes**:  The changes above should be mostly invisible to the user. However, the following will be different:
* Logging format across all files
* Ability to set the log output directory in `config.Settings`
* Output directory for `server_instances.log` is now the `default_log_dir`
(this used to be under `src\ansys\visor\viewer\logs`)


### Trame Logging

We propose the following implementation.
1. Expose a `trame_log_dir` setting in `config.Settings`, which is by default set to None, but when set,
turns on Trame logging which will write the output log files to this directory.
2. Application logs: `visor_trame_app.log`
   * **Direct Trame's native Python logs to a custom file**:
    Trame uses Python's `logging` library to log using logger names `trame`, `trame_server`, and `trame.app`.
    By default, these are written out to `visor.log`, but we can also capture these and redirect them to
    a separate Trame application log file using the Python `logging` library.
   * **Lifecycle hooks**: Trame offers hooks that can be added about the Trame server lifecycle
    (e.g. `on_server_start`, `on_client_exited`).  We can log these under a `trame_lifecycle` logger name
    and write to the same log file as above.
3. Network logs: `visor_trame_network.log`
   * The Trame server has an optional keyword argument `log_network`
   (see the [Trame docs](https://trame.readthedocs.io/en/latest/core.server.html)),
   which is False by default, but when set to a path to a log file, will write out
   additional logs to that file.  This logs communication between Python and the frontend.


Note that the trame log dir is configurable, but the trame log names are fixed.



## Example Log Output

---
1. application logs via `trame.logger` and lifecycle hooks: provides information about the application lifecycle (tracking when the server start, updates, ends).    The output looks like e.g.
```
2025-05-01 08:09:26,050 - trame.decorators.klass - DEBUG - Instance created
2025-05-01 08:09:26,050 - trame.decorators.klass - DEBUG - server=<trame_server.core.Server object at 0x00000241F7A876A0> prefix=''
2025-05-01 08:09:26,050 - trame.decorators.klass - DEBUG - state.change(['plane_widget'])(_on_widget_update)
2025-05-01 08:09:26,050 - trame.decorators.klass - DEBUG - trigger(get_scene_graph_json)(get_scene_graph_json)
2025-05-01 08:09:26,051 - trame.decorators.klass - DEBUG - trigger(node_hide)(node_hide)
2025-05-01 08:09:26,051 - trame.decorators.klass - DEBUG - trigger(node_show)(node_show)
2025-05-01 08:09:26,051 - trame.decorators.klass - DEBUG - trigger(toggle_cross_section)(toggle_cross_section)
2025-05-01 08:09:26,051 - trame.decorators.klass - DEBUG - trigger(toggle_wireframe)(toggle_wireframe)
2025-05-01 08:09:26,051 - trame.decorators.klass - DEBUG - trigger(update_selection)(update_selection)
2025-05-06 15:14:02,280 - trame_server.controller - INFO - [controller.py:70 register_trigger()] - trigger(update_selection)
2025-05-06 15:39:42,278 - trame_lifecycle - DEBUG - [application.py:163 server_ready()] - Server is ready.
2025-05-06 15:39:43,113 - trame_lifecycle - DEBUG - [application.py:168 client_connected()] - Client connected.
2025-05-06 15:39:46,232 - trame_lifecycle - DEBUG - [application.py:173 client_exited()] - Client exited.
2025-05-06 15:39:49,595 - trame_lifecycle - DEBUG - [application.py:168 client_connected()] - Client connected.
2025-05-06 15:39:51,736 - trame_lifecycle - DEBUG - [application.py:173 client_exited()] - Client exited.
2025-05-06 15:39:54,949 - trame_lifecycle - DEBUG - [application.py:178 server_exited()] - Server is exiting.
2025-05-06 15:39:57,494 - trame_lifecycle - DEBUG - [application.py:163 server_ready()] - Server is ready.
2025-05-06 15:39:59,178 - trame_lifecycle - DEBUG - [application.py:168 client_connected()] - Client connected.
2025-05-06 15:40:06,227 - trame_lifecycle - DEBUG - [application.py:178 server_exited()] - Server is exiting.
```


2. The log_network Server option provides logs of communication between Python and the frontend, e.g.
```
----------- STATE: Client => Server -----------
[
  {
    "key": "trame__busy",
    "value": 0
  }
]
------------------------------------------------------------
----------- STATE: Server => Client -----------
{
  "trame__busy": 0
}
------------------------------------------------------------
----------- EVENT: Client => Server -----------
{
  "name": "get_scene_graph_json",
  "args": [],
  "kwargs": {}
}
------------------------------------------------------------
----------- EVENT: Client => Server -----------
{
  "name": "node_show",
  "args": [
    7601913218618099
  ],
  "kwargs": {}
}
------------------------------------------------------------
----------- EVENT: Client => Server -----------
{
  "name": "node_show",
  "args": [
    3465350337367369
  ],
  "kwargs": {}
}
```
## Observability Compliance

ADR [#16](https://github.com/ansys-internal/architecture-decision-records/blob/main/content/docs/adrs/0016-observability-strategy.md)
outlines observability requirements on an Ansys level.

We have logs, but no traces or metrics implemented yet.  Traces are required for all applications / services
that are part of a distributed / microservices architecture, so we will need OpenTelemetry integration in VISOR.
This is in our backlog ([#94](https://github.com/ansys-internal/theia/issues/94)),
and we would like to take steps to move closer to this.

After unifying the main logging mechanism in VISOR, we will have made a couple of improvements bringing us
closer to the logging requirements.

| Requirement                                                             | Current                  |  Unified Logs |
|-------------------------------------------------------------------------|-------------------------------|-------|
| [Required] Logs                                                         | ✅                             | ✅ |
| [Required] Logs are structured, well formatted                          | ✅                             | ✅ |
| [Required] Logs generate high severity log events (ERROR, FATAL)        | ✅                             | ✅ |
| [Required] Logs in distributed envs are JSON formatted                  | ❌                             | ❌ |
| [Required] Logs able to change min severity level through configuration | Yes, but not in one place    | ✅ |
| [Required Field] Message                                                | ✅                             | ✅ |
| [Required Field] LoggerName                                             | ✅                             | ✅ |
| [Required Field] Level                                                  | ✅                             | ✅ |
| [Required Field] Timestamp                                              | ❌                             | ✅ |
| [Recommended Field] LineNo                                              | ❌                             | ✅ |
| [Recommended Field] FileName/Class/Module                               | ❌                             | ✅ |
| Traces*                                                                 | ❌                             | ❌ |
| Metrics                                                                 | ❌                             | ❌ |
| [Required Field] TraceId                                                | N/A (until traces implemented) | N/A (until traces implemented) |
| [Required Field] SpanId                                                 | N/A (until traces implemented) | N/A (until traces implemented) |
| [Required Field] ServiceName                                            | N/A (until traces implemented) | N/A (until traces implemented) |

\* Because do not have traces implemented yet, we can't yet to add the TraceId, SpandId, or ServiceName in our logs.


## Related Issues

Two issues related to this topic are here:
* [#251](https://github.com/ansys-internal/theia/issues/251)
Unify logging mechanisms
(PR [#252](https://github.com/ansys-internal/theia/pull/252))
* [#236](https://github.com/ansys-internal/theia/issues/236)
Create logging mechanism for Trame server in VISOR
(PR [239](https://github.com/ansys-internal/theia/pull/239))
