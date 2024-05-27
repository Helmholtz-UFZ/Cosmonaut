from layout import app
from flask_routes import server
import callbacks  # This import is necessary to register the callbacks with the app
from cosmonaut_app.config import PORT

app.server = server

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", debug=True, port=PORT)
