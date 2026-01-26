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
from dash import html, register_page, callback, Input, Output, State, dcc
from dash.exceptions import PreventUpdate

from cosmonaut_app.config import get_download_url
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.constants.html_ids import (
    DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID,
    JOB_ID_STORE_SHARED_ID,
    QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID,
    START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
)
from cosmonaut_app.layout import (
    create_map,
    page_container_split_layout,
    create_card_input,
    progress_footer,
    build_url_step,
)

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
    logging.info(f"Route & Download layout called with job_id={job_id}")

    # Construct full download URL
    download_url = get_download_url(job_id)

    card_body = [
        html.P(
            "Scan the QR code to download the GPX file of the final route.",
            className="mb-3 fs-5",
        ),
        html.Div(
            [
                html.Img(
                    src=f"/pictures/{job_id}/qr_code.png",
                    className="mt-3 mw-100",
                ),
                html.Div(
                    [
                        html.A(
                            "Download GPX File",
                            href=f"/download/{job_id}/route.gpx",
                            download="route.gpx",
                            className="btn btn-primary mt-3",
                        ),
                        html.Br(),
                        html.Code(
                            download_url,
                            id=DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID,
                        ),
                    ],
                    className="text-center mt-3",
                ),
            ],
            className="text-center",
        ),
        dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id),
    ]

    route_computation_path = build_url_step("route_computation", job_id)

    footer = progress_footer(
        prev_url=route_computation_path,
        next_url=None,
    )

    map = create_map(job=job)

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_split_layout(map, input_container)


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID, "src"),
    Input(START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def update_qr_code(n_clicks, job_id):
    logging.info(f"Generating QR code for job_id={job_id} on click {n_clicks}")
    if n_clicks is None:
        raise PreventUpdate
    job = CosmonautJob(job_id=job_id)
    return job.create_qr_code_routing()
