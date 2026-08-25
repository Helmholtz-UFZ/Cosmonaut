"""Calculate route and download GPX navigation file.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This is the final page of the workflow where you initiate the routing calculation
and download your optimized navigation route as a GPX file for use with GPS devices
or navigation applications.

**Page Features:**

- **Start Route Button**: Initiates the background routing calculation using
  your selected streets and configured parameters. The calculation runs as a
  Celery background task, so you can close your browser and check back later
  for results.

- **QR Code**: After the calculation completes successfully, a QR code is
  displayed that links directly to the GPX file download. This provides a
  convenient way to transfer the route to mobile devices - simply scan the
  code with your smartphone camera.

- **GPX Download**: Download the complete navigation route as a standard GPX
  (GPS Exchange Format) file compatible with most GPS devices, smartphone
  navigation apps, and mapping software.

- **Reverse Direction**: A switch flips the start and end of the route. The
  GPX file, the QR code and the on-map direction arrows update together.
  Only the order of the track points is reversed — the route itself does not
  change, and one-way restrictions are not re-validated for the opposite
  direction, so double-check the reversed route is legal to drive.

- **Route Visualization**: View the calculated route overlaid on the interactive
  map with all waypoints, turn-by-turn segments, and your original measurement
  locations. This allows you to preview the route before using it in the field.

**Processing Time:**

The routing calculation duration depends on several factors:
- Complexity and size of the selected street network
- Number of measurement points to visit
- Configured routing parameters and optimization settings
- Current system load and available worker capacity

You can monitor the job status and return to this page at any time to check
for completion and download your results.

**Using Your GPX File:**

The generated GPX file can be used in multiple ways:
- Transfer to a dedicated GPS device for field navigation
- Import into smartphone navigation apps (OsmAnd, Maps.me, etc.)
- Load into mapping software for route preview and analysis
- Share with field team members for coordinated sampling

The QR code provides the quickest way to get the route onto your mobile device
for immediate field use.

# Notes (This section is for developer notes and will not appear in the user documentation.)

Route calculation is triggered via background_job_manager using Celery tasks.
The QR code is generated using the qrcode library with an embedded download URL.
GPX files are stored in MinIO object storage and retrieved via Flask routes.
"""

import logging

import dash_bootstrap_components as dbc
from cosmo_suite.files_route import _download_href
from dash import Input, Output, State, callback, dcc, html, register_page
from dash.exceptions import PreventUpdate

from cosmonaut_app.config import get_download_url
from cosmonaut_app.constants.html_ids import (
    DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID,
    JOB_ID_STORE_SHARED_ID,
    REVERSE_ROUTE_SWITCH_ROUTE_DOWNLOAD_ID,
    ROUTE_DIRECTION_DECORATOR_MAP_ID,
    ROUTE_ENDPOINTS_GROUP_MAP_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.layout import (
    build_url_step,
    create_card_input,
    page_container_fullscreen_layout,
    progress_footer,
    route_endpoint_markers,
)

log = logging.getLogger(__name__)

register_page(
    __name__,
    path_template="/job/<job_id>/route-download",
    name="Route & Download",
    title="Route Download",
    description="View the calculated route and download the GPX file.",
    dynamic=True,
)


def layout(job_id):
    job = CosmonautJob(job_id=job_id)
    log.info(f"Route & Download layout called with job_id={job_id}")
    job.model.stage = max(job.model.stage, 5)
    job.save(sync_files=False)

    job.create_qr_code_routing()

    # Construct full download URL
    download_url = get_download_url(job_id)

    card_body = [
        html.P(
            "Download the GPX file of the route, or scan the QR code to transfer it to a phone.",
            className="mb-3",
        ),
        dbc.Switch(
            id=REVERSE_ROUTE_SWITCH_ROUTE_DOWNLOAD_ID,
            label="Reverse direction of travel",
            value=job.is_route_reversed(),
            className="mb-0",
        ),
        dbc.FormText(
            "Flips the start and end of the route. Updates the map, the GPX "
            "file, and the QR code together. Order only — one-way "
            "restrictions are not re-checked for the opposite direction.",
            className="d-block mb-3",
        ),
        html.A(
            [
                html.I(className="bi bi-download me-1"),
                "Download GPX File",
            ],
            href=f"/download/{job_id}/route.gpx",
            download="route.gpx",
            className="btn btn-primary btn-lg w-100",
        ),
        html.Div(
            html.Code(
                download_url,
                id=DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID,
            ),
            className="text-muted small d-block text-break my-2",
        ),
        dbc.Button(
            "Download work_dir",
            color="secondary",
            outline=True,
            href=_download_href(job_id),
            external_link=True,
            className="mt-2",
        ),
        html.Div(
            [
                # max-width:240px — no Bootstrap utility for exact px, mw-25/mw-50 are wrong granularity
                html.Img(
                    src=f"/pictures/{job_id}/qr_code.png",
                    style={"maxWidth": "240px"},
                    className="d-block mx-auto",
                ),
                html.Small(
                    "Scan to transfer to a phone.",
                    className="d-block text-muted text-center",
                ),
            ],
            className="mt-3",
        ),
        dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id),
    ]

    route_computation_path = build_url_step("route_computation", job_id)

    footer = progress_footer(
        prev_url=route_computation_path,
        next_url=None,
    )

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
        completed_steps=job.get_completed_steps(),
    )
    return page_container_fullscreen_layout(input_container)


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(ROUTE_DIRECTION_DECORATOR_MAP_ID, "positions", allow_duplicate=True),
    Output(ROUTE_ENDPOINTS_GROUP_MAP_ID, "children", allow_duplicate=True),
    Input(REVERSE_ROUTE_SWITCH_ROUTE_DOWNLOAD_ID, "value"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def toggle_route_direction(reversed_value, job_id):
    """Persist the chosen route direction and flip the on-map direction cues.

    Regenerates route.gpx + QR code and syncs to MinIO (the QR's presigned
    URL and the download route serve the MinIO copy). The route line itself
    is direction-agnostic — only arrowheads and start/end markers move.
    """
    if reversed_value is None or not job_id:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id, sync_files=False)
    # No-op when unchanged: page re-renders redeliver the current value.
    if job.is_route_reversed() == reversed_value:
        raise PreventUpdate

    job.set_route_reversed(reversed_value)
    positions = job.get_route_polyline() or []
    return [list(pos) for pos in positions], route_endpoint_markers(positions)
