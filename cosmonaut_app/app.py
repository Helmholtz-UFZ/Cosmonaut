import cosmonaut_app.callbacks  # This import is necessary to register the callbacks with the app
from cosmonaut_app.config import PORT
from cosmonaut_app.flask_routes import app, server

app.server = server

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=PORT)
