"""Page configuration for documentation generation.

This module serves as the single source of truth for which pages are documented.
Both doc_generator.py and screenshot_generator.py import from here to ensure
they stay synchronized.
"""

# User workflow pages: sequential steps in the routing workflow
# Format: (module_name, display_title)
USER_WORKFLOW_PAGES = [
    ("home", "Home Page"),
    ("user_info", "User Information"),
    ("data_upload", "Data Upload"),
    ("street_selection", "Street Selection"),
    ("routing_params", "Routing Parameters"),
    ("route_computation", "Route Computation"),
    ("route_download", "Route & Download"),
]

# Administrative pages: system management and monitoring
# Format: (module_name, display_title)
ADMIN_PAGES = [
    ("logs", "Application Logs"),
    ("worker_management", "Worker Management"),
    ("job_manager", "Job Manager"),
]

# Pages to exclude from documentation
EXCLUDED_PAGES = ["map", "__init__", "documentation"]
