"""Worker Management Page for COSMONAUT App.

# User documentation (This section is for user documentation and will appear in the user documentation.)

Monitor and manage background workers and tasks.

This administrative page provides real-time visibility into the Celery background task
system that processes prediction jobs and maintenance operations. Features include:

**Worker Status:**
- View active worker processes and their configuration
- See worker pool types, concurrency settings, and queue assignments
- Check worker availability and health

**Task Monitoring:**
- View currently executing tasks (active tasks)
- See tasks waiting in worker queues (reserved tasks)
- Monitor scheduled tasks waiting for their run time
- Track revoked (cancelled) tasks
- Display task details including name, arguments, and execution time

**Task Control:**
- Kill actively running tasks (forcefully terminate)
- Cancel scheduled tasks before they execute
- Confirmation dialogs prevent accidental terminations

**Status Updates:**
- Manual refresh to get latest worker and task information
- Timestamp showing when data was last refreshed

This page is essential for monitoring system load, debugging stuck tasks, and managing
resource usage during peak periods.

# Notes (This section is for developer notes and will not appear in the user documentation.)

The page implementation is `cosmo_suite.pages.worker_management`, which registers
itself under the page key `pages.worker_management` on import. This module exists
so Dash's `pages_folder` discovery imports it after `Dash(...)` is instantiated
(`register_page` must run after app instantiation), and so the user documentation
above stays app-owned — `doc_generator` parses the docstring of *this* file.

The framework page derives a task's job_id generically from the presence of
positional args instead of matching a domain task name, so no cosmonaut-specific
wiring is needed. Its HTML ids come from `cosmo_suite.constants`.
"""

import cosmo_suite.layouts

# Set BEFORE importing the page: page_container_column_layout reads this at
# layout-build time, and pages/job_management.py builds its layout as a
# module-level statement, so a value assigned afterwards would silently miss.
# Assign the module attribute — `from … import default_wrapper_class` would bind
# a copy of the value and configure nothing.
# See cosmo-suite docs/conventions/framework_page_imports.md.
cosmo_suite.layouts.default_wrapper_class = "no-map-page"

import cosmo_suite.pages.worker_management  # noqa: E402,F401
