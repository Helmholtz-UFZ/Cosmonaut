# cosmonaut-app UI kit

Interactive recreation of the COSMONAUT 7-step routing wizard, plus the three
admin pages (Job Manager, Worker Management, Logs).

This is a **cosmetic recreation** built with React + inline JSX, styled with
the same Bootswatch Flatly + Bootstrap Icons stack the production app uses. It
is not connected to a backend; uploads, job creation, route computation and
log polling are all mocked.

## What's here

- `index.html` — entry point. Loads React + Flatly + Bootstrap Icons and
  mounts `<App>`.
- `components.jsx` — shared primitives: `Navbar`, `WizardCard`,
  `WizardTabs`, `ProgressFooter`, `PageHeader`, `Alert`, `FauxMap`,
  `LoadingModal`, `ResetConfirmModal`. Each one mirrors a real
  `cosmonaut_app/layout.py` helper.
- `pages.jsx` — the seven wizard step pages: Home, UserInfo, DataUpload,
  StreetSelection, RoutingParams, Computation, RouteDownload.
- `admin.jsx` — JobManager, WorkerManagement, Logs.

## Screens recreated

| # | Screen | Source page | Notes |
|---|---|---|---|
| 1 | Welcome / Home | `pages/home.py` | Hero card with rocket CTA |
| 2 | Provide user information | `pages/user_info.py` | Email input + warning banner |
| 3 | Upload classification data | `pages/data_upload.py` | EPSG + 2× upload + opacity slider |
| 4 | Select streets for routing | `pages/street_selection.py` | Switch grid + edit/remove |
| 5 | Set routing parameters | `pages/routing_params.py` | 5 essential + advanced toggle |
| 6 | Monitor routing computation | `pages/route_computation.py` | Status pill + log stream |
| 7 | Download the computed route | `pages/route_download.py` | QR + GPX download |
| — | Job Manager | `pages/job_manager.py` | Full-cell coloured status bars |
| — | Worker Management | `pages/worker_management.py` | Empty-state AgGrid table |
| — | Logs | `pages/logs.py` | Filter strip + live placeholder |

## What's mocked / cut

- **The map** is a static SVG that mimics OpenStreetMap's tile pattern + the
  red street GeoJSON layer. In production this is dash-leaflet with live
  OSM tiles.
- **Uploads** flip state but don't actually parse files. The classification
  preview tile uses a generated heatmap-like overlay.
- **Computation logs** stream in a fixed sequence on a setTimeout, mirroring
  the cadence of the real Celery task.
- **AgGrid tables** are recreated as plain `<table>`s with the same column
  layout, padding and zebra-row style.

## How to navigate

The navbar in the kit exposes every admin page; the wizard's *Previous /
Next* buttons walk through the 7-step flow. A floating breadcrumb shows the
current step number. Switching pages **does not reset** the job-id, so the
header stays `b56ee901` throughout the wizard for continuity.
