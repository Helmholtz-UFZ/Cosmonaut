# callbacks import is necessary to register the callbacks with the app
from cosmonaut_app import callbacks  # noqa: F401
from cosmonaut_app.config import FLASK_PORT
from cosmonaut_app.flask_routes import app, server

app.server = server

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=FLASK_PORT)
