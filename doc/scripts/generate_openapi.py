import json

from ansys.visor.viewer.api.server import app

with open("source/http_api_reference/openapi.json", "w+") as f:
    json.dump(app.openapi(), f, indent=2)
