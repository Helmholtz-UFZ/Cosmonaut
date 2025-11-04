import cosmonaut_app.callbacks  # noqa: F401
from cosmonaut_app.app import server as app  # noqa: F401

# This is the entry point for the Dash app
# It is used by the WSGI server to start the Dash app
# TODO FIXME: When the app is started with `gunicorn`, the JOB_WORKING_DIR seems to be buggy
