"""View and filter application logs for debugging and monitoring.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This page provides access to the application's logging system, allowing you to track
system activity, debug issues, and monitor operations. You can:

- Filter logs by date and time range
- Select specific log levels (Debug, Info, Warning, Error, Critical)
- Filter by process ID to track specific server processes
- Exclude specific modules from the output
- Enable live mode for automatic 10-second polling
- View logs in a formatted, readable table
- Refresh logs on demand to see latest entries

Logs are stored in the database and include timestamps, log levels, logger names,
and messages. This is the primary tool for understanding system behavior, diagnosing
problems, and monitoring application execution.

# Notes (This section is for developer notes and will not appear in the user documentation.)

The page implementation is `cosmo_suite.pages.logs`, which registers itself under
the page key `pages.logs` on import. This module exists so Dash's `pages_folder`
discovery imports it after `Dash(...)` is instantiated (`register_page` must run
after app instantiation), and so the user documentation above stays app-owned —
`doc_generator` parses the docstring of *this* file.

Architecture (unchanged in the framework version): all filter components are
State, never Input. Only three Input triggers — the auto-poll interval tick, the
manual refresh button, and the live-mode switch. Its HTML ids come from
`cosmo_suite.constants`.
"""

import cosmo_suite.pages.logs  # noqa: F401
