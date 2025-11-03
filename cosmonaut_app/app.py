# callbacks import is necessary to register the callbacks with the app
import os

from cosmonaut_app import callbacks  # noqa: F401
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.flask_routes import app, server

app.server = server

if __name__ == "__main__":
    # Read DEBUG from environment variable (default to False)
    debug_mode = os.getenv("DEBUG", "0") == "1"
    app.run(host="0.0.0.0", debug=debug_mode, port=FLASK_PORT)
