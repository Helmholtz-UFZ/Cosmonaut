"""Manage all jobs from a central dashboard.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This administrative page provides a comprehensive overview of all jobs in the system.
You can:
- View all jobs in a table with status, start date and time, and submission details
- See job status at a glance with color coding (PENDING=orange, RUNNING=green,
  COMPLETED=blue, FAILED=red)
- Select and delete individual jobs or multiple jobs at once
- Clean up: remove every unsubmitted job and every expired submitted job at once
- Access individual job pages directly from the table by clicking Job ID

The table uses color coding to quickly identify job statuses. You can select rows to
perform bulk operations like deletion. The "Clean" button removes all unsubmitted jobs
immediately, and submitted jobs older than their retention period (60 days). Without it,
the nightly cleanup removes unsubmitted jobs after 2 days.

# Notes (This section is for developer notes and will not appear in the user documentation.)

The page implementation is `cosmo_ecosystem.pages.job_management`, which registers
itself under the page key `pages.job_management` (path `/job-management`) on import.
This module exists so Dash's `pages_folder` discovery imports it after `Dash(...)` is
instantiated (`register_page` must run after app instantiation), and so the user
documentation above stays app-owned — `doc_generator` parses the docstring of *this*
file. Keep the word `register_page` in this file: discovery skips any file whose text
does not contain it (`dash/_pages.py`), and the page would silently not exist.

The one COSMONAUT-specific part is the row link: `resolve_reload_url` sends a job to
the page where its user resumes it, by status and, for a PENDING job, by stage. Its
HTML ids come from `cosmo_ecosystem.constants`.
"""

import cosmo_ecosystem.layouts
import cosmo_ecosystem.pages

from cosmonaut_app.layout import resolve_reload_url

# Both set BEFORE importing the page: it raises at import while `job_link` is
# unset, and it builds its layout as a module-level statement, so a wrapper class
# assigned afterwards would silently miss. Assign the module attributes — a
# `from … import` would bind a copy of the value and configure nothing.
# See cosmo-ecosystem docs/conventions/framework_page_imports.md.
cosmo_ecosystem.layouts.default_wrapper_class = "no-map-page"
cosmo_ecosystem.pages.job_link = lambda job_id, row: resolve_reload_url(
    job_id, row["status"], row["stage"]
)

import cosmo_ecosystem.pages.job_management  # noqa: E402,F401
