from dash import Dash, Input, Output, callback, html
from visordash import Visordash, init_endpoints


def get_app():
    app = Dash(__name__)
    init_endpoints(app)

    td = Visordash(
        id='input',
        host='localhost',
        port=8081,
        aspectRatio=2.2,
        pixelDensity=1500,
        darkMode=False,
    )

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

    return app

def run_dash():
    app = get_app()
    print("Dash started")
    app.run(host='0.0.0.0', port=8050, debug=False, use_reloader=False)  # use_reloader=False avoids double-execution
    print("Dash exiting")

if __name__ == '__main__':
    try:
        run_dash()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received! Stopping...")
