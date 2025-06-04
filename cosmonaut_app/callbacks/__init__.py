from . import callbacks_upload  # noqa: F401
from . import callbacks_map  # noqa: F401
from . import callbacks_routing  # noqa: F401
from . import callbacks_job  # noqa: F401
from . import callbacks_ui  # noqa: F401

# Project Structure:
# callbacks/
#   __init__.py
#   callbacks_job.py
#   callbacks_map.py
#   callbacks_routing.py
#   callbacks_ui.py
#   callbacks_upload.py

# ===== callbacks/__init__.py =====
"""
Callback registration system for the Cosmonaut Dash app.
Import this module to register all callbacks with the app.
"""
# This file is intentionally left empty to ensure that the callbacks are registered
# when the module is imported. The actual callback functions are defined in
# the individual callback files (callbacks_job.py, callbacks_map.py, etc.).
