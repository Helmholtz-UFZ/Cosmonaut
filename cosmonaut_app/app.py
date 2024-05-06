from layout import app
from flask_routes import server
import callbacks  # This import is necessary to register the callbacks with the app

app.server = server

if __name__ == "__main__":
    app.run_server(debug=True)
