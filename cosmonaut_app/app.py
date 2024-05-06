from layout import app
from flask_routes import server

app.server = server

if __name__ == "__main__":
    app.run_server(debug=True)
