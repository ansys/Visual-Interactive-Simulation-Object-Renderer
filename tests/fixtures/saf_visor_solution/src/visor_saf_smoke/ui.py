"""A real SAF project UI with initialization and transactional file upload."""

import logging

from ansys.saf.glow.client import callback
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from dash_extensions.enrich import DashProxy
from visordash import Visordash, init_endpoints

from visor_saf_smoke.solution.definition import SmokeSolution

logger = logging.getLogger(__name__)
app = DashProxy(__name__)
init_endpoints(app)
app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        html.H1("SAF-Visor integration"),
        html.Button("Initialize Visor", id="initialize"),
        html.Pre(id="launch-status"),
        dcc.Upload(id="upload", children=html.Button("Upload VTP or VTU"), accept=".vtp,.vtu"),
        html.Pre(id="upload-status"),
        html.Div(id="viewer"),
    ]
)


@callback(
    Output("launch-status", "children"),
    Output("viewer", "children"),
    Input("initialize", "n_clicks"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def initialize(n_clicks: int | None, project: SmokeSolution):
    """Initialize and start Visor through a SAF transaction and embed the viewer.

    Returns:
        The launch status and the Visor component, or an error message and no component.
    """
    if not n_clicks:
        raise PreventUpdate
    try:
        step = project.steps.visualization
        step.initialize()
        return "ready", Visordash(
            id="visor",
            host=step.viewer_host,
            port=step.viewer_port,
            aspectRatio=1.6,
            pixelDensity=800,
        )
    except Exception as exc:
        logger.exception("SAF Visor initialization failed")
        return f"error: {exc}", []


@callback(
    Output("upload-status", "children"),
    Input("upload", "contents"),
    State("upload", "filename"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def upload(contents: str | None, filename: str | None, project: SmokeSolution) -> str:
    """Store the uploaded file through a SAF transaction and load it into Visor.

    Returns:
        A `loaded: <name>` status, or an error message.
    """
    if contents is None or filename is None:
        raise PreventUpdate
    try:
        step = project.steps.visualization
        step.upload(filename=filename, contents=contents)
        return f"loaded: {step.uploaded_name}"
    except Exception as exc:
        logger.exception("SAF Visor upload failed")
        return f"error: {exc}"
