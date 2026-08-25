# ©2026, ANSYS Inc part of Synopsys. Unauthorized use, distribution or duplication is prohibited.

from dash import Dash, Input, Output, callback, html
from visordash import Visordash, init_endpoints


def run_dash_server(visor_host: str, visor_port: int, dash_port: int, **visordash_kwargs):
    """
    Function executed in a separate process to run the Dash app.

    Parameters
    ----------
    visor_host : str
        Hostname of the running Visor instance.
    visor_port : int
        Port of the running Visor instance.
    dash_port : int
        Port on which the Dash server will listen.
    **visordash_kwargs
        Optional overrides for Visordash props (e.g. ``darkMode=True``,
        ``aspectRatio=1.0``, ``pixelDensity=750``).
    """
    app = Dash(__name__)

    # Register Visor endpoints needed by the component
    init_endpoints(app)

    # Build props: defaults first, then caller overrides
    td_props = {
        "id": "input",
        "host": visor_host,
        "port": visor_port,
        "pixelDensity": 1500,
        "aspectRatio": 2.2,
        "darkMode": False,
    }
    td_props.update(visordash_kwargs)

    # Visordash component wired to running Visor instance
    td = Visordash(**td_props)

    app.layout = html.Div([
        td,
        html.Button("Get Parts Snapshot", id="snapshot-btn"),
        html.Pre(id='output')
    ])

    @callback(
        Output('input', 'fireSnapshot'),
        Input('snapshot-btn', 'n_clicks'),
        prevent_initial_call=True
    )
    def trigger_snapshot(n_clicks):
        return True

    @callback(
        Output('output', 'children'),
        Input('input', 'parts'),
        prevent_initial_call=True
    )
    def display_parts(parts):
        import json
        return json.dumps(parts, indent=2)

    # Important: use_reloader=False to avoid double processes
    app.run(host='0.0.0.0', port=dash_port, debug=False, use_reloader=False)