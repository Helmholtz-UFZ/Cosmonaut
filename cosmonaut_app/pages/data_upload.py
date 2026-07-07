"""Upload membership and predictor data and configure coordinate reference system.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This page is where you upload your cosmic ray neutron sensor measurement locations
or sampling points that will be used to plan the navigation route. The workflow
on this page involves three key steps:

1. **Specify EPSG Code**: Enter the coordinate reference system (CRS) of your data.
   The application validates the EPSG code.

2. **Upload Membership File**: Drag and drop or select a CSV/TXT file containing your
   membership data with coordinate columns. The system will parse your file,
   transform coordinates to WGS84 (EPSG:4326) for map display, and visualize
   your locations on the interactive map. After uploading, the road network is
   downloaded from OpenStreetMap **in the background** — you can continue with
   the predictor upload while it runs. A status indicator shows the progress.

3. **Upload Predictor File**: Upload a CSV file containing the predictor data
   (e.g. environmental covariates) used by the routing algorithm. The predictor
   file must be consistent with the membership file. Hover over the upload
   button to see the exact format requirements in the tooltip.

**Membership File Requirements:**
- Format: CSV or TXT with delimiter-separated values
- Must include coordinate columns (latitude/longitude or projected coordinates)
- Coordinates should match the specified EPSG code
- Files are stored securely in your job's work directory

**Predictor File Requirements:**
- Format: CSV with delimiter-separated values
- Must be consistent with the uploaded membership file

Once both files are uploaded and validated, proceed to the street selection page
to choose which roads to include in your route.

# Notes (This section is for developer notes and will not appear in the user documentation.)

File upload uses dcc.Upload with base64 encoding. Coordinate transformation uses
pyproj with CRS validation via the pyproj.CRS class. Predictor upload is validated
via parse_predictor_file and cross-checked against the membership file using
validate_predictor_membership_consistency. The exact predictor file format is not
duplicated here — it is sourced at runtime from DESCRIPTION_PREDICTOR in the
sensor-routing package and displayed in the UI tooltip on the upload button.

**Road network background task flow:**

After a successful membership upload, a Celery task (process_upload_task) is
submitted to the ``upload`` queue via background_job_manager.submit_upload_job().
The task streams the road network from Overpass (``cosmonaut_app/osm/``) and
projects it to the user's EPSG. This runs in a worker to keep the download and
projection work off the web process.

membership_upload["street_processing"] state machine:
- ``"PENDING"``  — default, no task submitted yet
- *Celery task ID* — task queued or running
- ``"COMPLETED"`` — roads downloaded and saved
- ``"FAILED"``   — task failed; user must re-upload

A dcc.Interval polls every 3s. poll_street_processing calls
get_street_processing_status(), which checks AsyncResult and persists terminal
state to the database. Polling stops once terminal state is reached.
"""

import logging

import dash
import dash_bootstrap_components as dbc
from dash import (
    Input,
    Output,
    State,
    callback,
    ctx,
    dcc,
    html,
    no_update,
    register_page,
)
from dash.exceptions import PreventUpdate
from sensor_routing.full_pipeline_cli import (
    DESCRIPTION_MEMBERSHIP,
    DESCRIPTION_PREDICTOR,
)

from cosmonaut_app.background_job_manager import background_job_manager
from cosmonaut_app.classification_plot import ClassificationPlot
from cosmonaut_app.object_storage_manager import save_files
from cosmonaut_app.constants.general import (
    DEFAULT_MAP_CENTER,
    DEFAULT_MAP_ZOOM,
    JOB_STATUS_PENDING,
)
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID,
    DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID,
    DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
    DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID,
    DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID,
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID,
    DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID,
    JOB_ID_STORE_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MEMBERSHIP_ERROR_DIV_DATA_UPLOAD_ID,
    MEMBERSHIP_HELP_ICON_ID,
    MEMBERSHIP_TILE_LAYER_MAP_ID,
    MEMBERSHIP_UPLOAD_COLLAPSE_DATA_UPLOAD_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    PREDICTOR_ERROR_DIV_DATA_UPLOAD_ID,
    PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID,
    PREDICTOR_HELP_ICON_ID,
    PREDICTOR_UPLOAD_COLLAPSE_DATA_UPLOAD_ID,
    PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    STREET_PROCESSING_POLL_DATA_UPLOAD_ID,
    STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.error_handling import FileValidationError
from cosmonaut_app.layout import (
    build_url_step,
    create_card_input,
    create_reset_banner,
    create_reset_modal,
    page_container_fullscreen_layout,
    progress_footer,
)
from cosmonaut_app.map_utils import get_tile_url
from cosmonaut_app.pydantic_models import check_epsg

log = logging.getLogger(__name__)

register_page(
    __name__,
    path_template="/job/<job_id>/data-upload",
    name="Data Upload",
    title="Data Upload",
    description="Upload data for this job.",
    dynamic=True,
)


def _first_sentence(text):
    """Return the first sentence from a multi-line description string."""
    stripped = text.strip()
    dot = stripped.find(".")
    if dot == -1:
        return stripped
    return stripped[: dot + 1]


def _help_icon(icon_id, description):
    """Create a question-mark icon with a dbc.Tooltip.

    Wrapped in an html.Span so the helper returns a single component, not a
    list. Returning a raw list and placing it inside another list (e.g. as a
    sibling inside html.Span's children) leaves React with a nested array
    that dash-renderer doesn't reliably flatten — crashes the page with
    React error #31 ("Objects are not valid as a React child").
    """
    return html.Span(
        [
            html.I(
                id=icon_id,  # nocheck dynamically passed constant
                className="bi bi-info-circle text-muted ms-1",
            ),
            dbc.Tooltip(description.strip(), target=icon_id),
        ]
    )


def _file_status(uploaded: bool):
    """Return a coloured icon + label for a file upload status row."""
    if uploaded:
        return [
            html.I(className="bi bi-check-circle-fill text-success me-1"),
            html.Span("Uploaded", className="text-success fw-semibold small"),
        ]
    return [
        html.I(className="bi bi-dash-circle text-muted me-1"),
        html.Span("Not uploaded", className="text-muted small"),
    ]


def layout(job_id):
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()
    is_active = status == JOB_STATUS_PENDING

    # --- Disabled-state logic (all in one place) ---
    membership_uploaded = job.model.membership_upload["file_name"] != "No file uploaded"
    predictor_uploaded = job.model.predictor_upload["file_name"] != "No file uploaded"
    street_processing = job.model.membership_upload["street_processing"]
    epsg_disabled = (not is_active) or membership_uploaded
    next_disabled = not (membership_uploaded and predictor_uploaded)
    delete_membership_disabled = not (membership_uploaded and is_active)
    delete_predictor_disabled = not (predictor_uploaded and is_active)
    predictor_upload_disabled = not membership_uploaded or predictor_uploaded
    slider_disabled = not membership_uploaded

    # Determine street processing display state
    if street_processing == "COMPLETED":
        sp_text = "Road network is constructed"
        sp_class = "text-muted small"
        sp_poll_disabled = True
    elif street_processing == "FAILED":
        sp_text = (
            "Road network construction failed! Re-upload membership file. "
            "If the problem persists, contact the maintainer."
        )
        sp_class = "text-danger small"
        sp_poll_disabled = True
    elif street_processing == "PENDING":
        sp_text = "Road network will be constructed in the background"
        sp_class = "text-muted small"
        sp_poll_disabled = True
    else:
        # Task ID — still running
        sp_text = "Road network is being built..."
        sp_class = "text-info small"
        sp_poll_disabled = False

    card_body = []

    # Add reset banner if not PENDING
    if not is_active:
        card_body.append(create_reset_banner(job_id, status))

    # Add stores and form components
    card_body.extend(
        [
            dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id),
            dcc.Store(
                id=DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID, data=membership_uploaded
            ),
            dbc.Card(
                [
                    dbc.CardHeader(
                        "Coordinate system",
                        className="cn-card-legend bg-white border-0 fw-bold",
                    ),
                    dbc.CardBody(
                        [
                            dbc.Label(
                                "EPSG code",
                                html_for=DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID,
                                className="mt-2",
                            ),
                            dbc.Input(
                                id=DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID,
                                type="text",
                                value=job.model.epsg,
                                disabled=epsg_disabled,
                            ),
                            dbc.FormText(
                                "Common choices: 4326, 25832, 3857, …",
                                color="secondary",
                                className="mb-1",
                            ),
                            dbc.FormText(
                                id=DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID,
                                className="fw-semibold",
                            ),
                        ]
                    ),
                ],
                className="mb-3 shadow-sm",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(
                        "Membership data",
                        className="cn-card-legend bg-white border-0 fw-bold",
                    ),
                    dbc.CardBody(
                        [
                            dbc.Collapse(
                                [
                                    dcc.Upload(
                                        id=DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
                                        accept=".csv,.txt",
                                        children=dbc.Button(
                                            [
                                                html.I(className="bi bi-upload me-2"),
                                                "Upload membership file",
                                            ],
                                            color="primary",
                                        ),
                                        multiple=False,
                                        disabled=True,
                                        className="my-3",
                                    ),
                                    html.Span(
                                        [
                                            html.Small(
                                                _first_sentence(DESCRIPTION_MEMBERSHIP),
                                                className="text-muted",
                                            ),
                                            _help_icon(MEMBERSHIP_HELP_ICON_ID, DESCRIPTION_MEMBERSHIP),
                                        ],
                                    ),
                                ],
                                id=MEMBERSHIP_UPLOAD_COLLAPSE_DATA_UPLOAD_ID,
                                is_open=not membership_uploaded,
                            ),
                            html.Div(
                                id=MEMBERSHIP_ERROR_DIV_DATA_UPLOAD_ID,
                                className="text-danger small",
                            ),
                            html.Div(
                                _file_status(membership_uploaded),
                                id=DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
                            ),
                            dbc.Button(
                                [
                                    html.I(className="bi bi-trash me-1"),
                                    "Delete Membership",
                                ],
                                id=DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID,
                                color="danger",
                                size="sm",
                                className="mt-2",
                                disabled=delete_membership_disabled,
                            ),
                            html.Div(
                                sp_text,
                                id=STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID,
                                className=sp_class,
                            ),
                            dcc.Interval(
                                id=STREET_PROCESSING_POLL_DATA_UPLOAD_ID,
                                interval=3000,
                                disabled=sp_poll_disabled,
                            ),
                            html.Div(
                                [
                                    dbc.Label("Map Opacity:", className="fw-bold mt-3"),
                                    dcc.Slider(
                                        id=DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID,
                                        min=0,
                                        max=1,
                                        step=0.1,
                                        value=0.7,
                                        marks={0: "0%", 0.5: "50%", 1: "100%"},
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": False,
                                        },
                                        disabled=slider_disabled,
                                    ),
                                ],
                                className="mb-3",
                            ),
                        ]
                    ),
                ],
                className="mb-3 shadow-sm",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(
                        "Predictor data",
                        className="cn-card-legend bg-white border-0 fw-bold",
                    ),
                    dbc.CardBody(
                        [
                            dbc.Collapse(
                                [
                                    dcc.Upload(
                                        id=PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
                                        accept=".csv,.txt",
                                        children=dbc.Button(
                                            [
                                                html.I(className="bi bi-upload me-2"),
                                                "Upload predictor file",
                                            ],
                                            color="primary",
                                        ),
                                        multiple=False,
                                        disabled=predictor_upload_disabled,
                                        className="my-3",
                                    ),
                                    html.Span(
                                        [
                                            html.Small(
                                                _first_sentence(DESCRIPTION_PREDICTOR),
                                                className="text-muted",
                                            ),
                                            _help_icon(PREDICTOR_HELP_ICON_ID, DESCRIPTION_PREDICTOR),
                                        ],
                                    ),
                                ],
                                id=PREDICTOR_UPLOAD_COLLAPSE_DATA_UPLOAD_ID,
                                is_open=not predictor_uploaded,
                            ),
                            html.Div(
                                id=PREDICTOR_ERROR_DIV_DATA_UPLOAD_ID,
                                className="text-danger small",
                            ),
                            html.Div(
                                _file_status(predictor_uploaded),
                                id=PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID,
                            ),
                            dbc.Button(
                                [
                                    html.I(className="bi bi-trash me-1"),
                                    "Delete Predictor",
                                ],
                                id=DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID,
                                color="danger",
                                size="sm",
                                className="mt-2",
                                disabled=delete_predictor_disabled,
                            ),
                        ]
                    ),
                ],
                className="mb-3 shadow-sm",
            ),
        ]
    )

    # Add reset modal
    card_body.append(create_reset_modal())

    user_info_path = build_url_step("user_info", job_id)
    street_selection_path = build_url_step("street_selection", job_id)

    footer = progress_footer(
        prev_url=user_info_path,
        next_url=street_selection_path,
        next_id=NEXT_BUTTON_DATA_UPLOAD_ID,
        next_disabled=next_disabled,
    )

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
        completed_steps=job.get_completed_steps(),
    )
    return page_container_fullscreen_layout(input_container)


# Clientside callbacks: show "Uploading..." in the status row immediately when a
# file is selected — before the slow server-side processing callback completes.
dash.clientside_callback(
    """
    function(filename) {
        if (!filename) { return window.dash_clientside.no_update; }
        return "Uploading...";
    }
    """,
    Output(DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True),
    Input(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(filename) {
        if (!filename) { return window.dash_clientside.no_update; }
        return "Uploading...";
    }
    """,
    Output(PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True),
    Input(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
    prevent_initial_call=True,
)


def _no_update_upload():
    """Return a dict with no_update for all data_upload_manager outputs."""
    return {
        "viewport": no_update,
        "file_info": no_update,
        "next_disabled": no_update,
        "epsg_disabled": no_update,
        "upload_contents": no_update,
        "delete_membership_disabled": no_update,
        "tile_url": no_update,
        "slider_disabled": no_update,
        "upload_disabled": no_update,
        "membership_error": no_update,
        "membership_collapse_open": no_update,
        "predictor_upload_disabled": no_update,
        "predictor_file_info": no_update,
        "predictor_error": no_update,
        "delete_predictor_disabled": no_update,
        "predictor_contents": no_update,
        "predictor_collapse_open": no_update,
        "tile_opacity": no_update,
        "sp_text": no_update,
        "sp_class": no_update,
        "sp_poll_disabled": no_update,
    }


def _handle_membership_upload(contents, filename, job_id, epsg_input):
    """Process membership file upload."""
    if not contents or not filename:
        raise PreventUpdate

    log.info(
        f"Uploading membership file {filename} for job {job_id} with EPSG {epsg_input}"
    )
    try:
        epsg_input = check_epsg(epsg_input)
    except ValueError as e:
        log.debug(f"Invalid EPSG code {epsg_input}: {e}")
        result = _no_update_upload()
        result.update(
            {
                "next_disabled": True,
                "epsg_disabled": False,
                "upload_contents": None,
                "membership_error": str(e),
            }
        )
        return result

    job = CosmonautJob(job_id=job_id, sync_files=False)
    job.model.epsg = epsg_input
    job.delete_membership(sync_files=False)
    try:
        file_path, bounds, membership_df = job.upload_membership(
            filename, contents, epsg_input, sync_files=False
        )
    except FileValidationError as e:
        result = _no_update_upload()
        result.update(
            {
                "file_info": str(e),
                "next_disabled": True,
                "epsg_disabled": False,
                "upload_contents": None,
                "membership_error": str(e),
            }
        )
        return result

    # Single sync to object storage before plot generation — the worker pulls
    # files via get_files() so the membership CSV must be in MinIO before the
    # task starts.  Syncing here (before plots) keeps the payload small and fast.
    # Previous intermediate saves used sync_files=False to avoid redundant rclone
    # calls that blocked this synchronous callback for minutes on large uploads.
    save_files(job.model.job_id)

    log.debug("Upload finished, generating plots and submitting OSM task")

    plot = ClassificationPlot(
        membership_df, job.working_dir, src_epsg=f"EPSG:{epsg_input}"
    )
    plot.generate_plots()
    log.debug("Classification plots generated.")

    tile_url = get_tile_url(job_id, job.working_dir)

    task_id, failed = background_job_manager.submit_upload_job(job, epsg_input)
    if not failed:
        job.model.membership_upload["street_processing"] = task_id
    else:
        job.model.membership_upload["street_processing"] = "FAILED"
    # Skip sync — the worker's save() will sync everything when it finishes
    job.save(sync_files=False)

    log.debug(f"Membership file uploaded and processed for job {job_id}")

    if failed:
        sp_text = (
            "Road network construction failed! Re-upload membership file. "
            "If the problem persists, contact the maintainer."
        )
        sp_class = "text-danger small"
        sp_poll_disabled = True
    else:
        sp_text = "Road network is being built..."
        sp_class = "text-info small"
        sp_poll_disabled = False

    result = _no_update_upload()
    result.update(
        {
            "viewport": {"bounds": bounds, "transition": "flyTo"},
            "file_info": _file_status(True),
            "next_disabled": True,
            "epsg_disabled": True,
            "upload_contents": None,
            "delete_membership_disabled": False,
            "tile_url": tile_url,
            "slider_disabled": False,
            "upload_disabled": True,
            "membership_error": "",
            "membership_collapse_open": False,
            "predictor_upload_disabled": False,
            "predictor_file_info": _file_status(False),
            "predictor_error": "",
            "delete_predictor_disabled": True,
            "predictor_collapse_open": True,
            "sp_text": sp_text,
            "sp_class": sp_class,
            "sp_poll_disabled": sp_poll_disabled,
        }
    )
    return result


def _handle_predictor_upload(predictor_contents, predictor_filename, job_id):
    """Process predictor file upload."""
    if not predictor_contents or not predictor_filename:
        raise PreventUpdate

    log.info(f"Uploading predictor file for job {job_id}")

    job = CosmonautJob(job_id=job_id, sync_files=False)
    try:
        job.upload_predictor(predictor_contents)
    except FileValidationError as e:
        result = _no_update_upload()
        result.update(
            {
                "next_disabled": True,
                "predictor_file_info": _file_status(False),
                "predictor_error": str(e),
                "delete_predictor_disabled": True,
                "predictor_contents": None,
            }
        )
        return result

    result = _no_update_upload()
    result.update(
        {
            "next_disabled": False,
            "predictor_file_info": _file_status(True),
            "predictor_error": "",
            "delete_predictor_disabled": False,
            "predictor_contents": None,
            "predictor_upload_disabled": True,
            "predictor_collapse_open": False,
        }
    )
    return result


def _handle_opacity_change(opacity, job_id):
    """Process opacity slider change."""
    if not job_id:
        raise PreventUpdate

    result = _no_update_upload()
    result["tile_opacity"] = opacity
    return result


def _handle_init_store(init_trigger, job_id):
    """Handle initial page load with existing upload."""
    result = _no_update_upload()
    if init_trigger and job_id:
        result.update(
            {
                "slider_disabled": False,
                "upload_disabled": True,
                "membership_collapse_open": False,
            }
        )
    else:
        result["slider_disabled"] = True
    return result


@callback(
    output={
        "viewport": Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport"),
        "file_info": Output(DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, "children"),
        "next_disabled": Output(NEXT_BUTTON_DATA_UPLOAD_ID, "disabled"),
        "epsg_disabled": Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "disabled"),
        "upload_contents": Output(
            DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"
        ),
        "delete_membership_disabled": Output(
            DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID, "disabled"
        ),
        "tile_url": Output(MEMBERSHIP_TILE_LAYER_MAP_ID, "url", allow_duplicate=True),
        "slider_disabled": Output(
            DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID, "disabled"
        ),
        "upload_disabled": Output(
            DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
            "disabled",
            allow_duplicate=True,
        ),
        "membership_error": Output(MEMBERSHIP_ERROR_DIV_DATA_UPLOAD_ID, "children"),
        "membership_collapse_open": Output(
            MEMBERSHIP_UPLOAD_COLLAPSE_DATA_UPLOAD_ID, "is_open"
        ),
        "predictor_upload_disabled": Output(
            PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled"
        ),
        "predictor_file_info": Output(
            PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID, "children"
        ),
        "predictor_error": Output(PREDICTOR_ERROR_DIV_DATA_UPLOAD_ID, "children"),
        "delete_predictor_disabled": Output(
            DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "disabled"
        ),
        "predictor_contents": Output(
            PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"
        ),
        "predictor_collapse_open": Output(
            PREDICTOR_UPLOAD_COLLAPSE_DATA_UPLOAD_ID, "is_open"
        ),
        "tile_opacity": Output(MEMBERSHIP_TILE_LAYER_MAP_ID, "opacity"),
        "sp_text": Output(
            STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID,
            "children",
            allow_duplicate=True,
        ),
        "sp_class": Output(
            STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID,
            "className",
            allow_duplicate=True,
        ),
        "sp_poll_disabled": Output(
            STREET_PROCESSING_POLL_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
    },
    inputs={
        "contents": Input(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"),
        "opacity": Input(DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID, "value"),
        "init_trigger": Input(DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID, "data"),
        "predictor_contents": Input(
            PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"
        ),
    },
    state={
        "filename": State(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
        "predictor_filename": State(
            PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"
        ),
        "job_id": State(JOB_ID_STORE_SHARED_ID, "data"),
        "epsg_input": State(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "value"),
    },
    prevent_initial_call="initial_duplicate",
)
def data_upload_manager(
    contents,
    opacity,
    init_trigger,
    predictor_contents,
    filename,
    predictor_filename,
    job_id,
    epsg_input,
):
    """Manage data uploads: membership, predictor, opacity changes, and initial page load."""
    triggered = ctx.triggered_id

    if triggered == DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID:
        return _handle_membership_upload(contents, filename, job_id, epsg_input)

    if triggered == PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID:
        return _handle_predictor_upload(predictor_contents, predictor_filename, job_id)

    if triggered == DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID:
        return _handle_opacity_change(opacity, job_id)

    if triggered == DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID:
        return _handle_init_store(init_trigger, job_id)

    raise PreventUpdate


@callback(
    output={
        "file_info": Output(
            DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True
        ),
        "epsg_disabled": Output(
            DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
        "delete_membership_disabled": Output(
            DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
        "next_disabled": Output(
            NEXT_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
        "viewport": Output(
            MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport", allow_duplicate=True
        ),
        "tile_url": Output(MEMBERSHIP_TILE_LAYER_MAP_ID, "url", allow_duplicate=True),
        "slider_disabled": Output(
            DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
        "upload_disabled": Output(
            DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
            "disabled",
            allow_duplicate=True,
        ),
        "init_store": Output(
            DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID, "data", allow_duplicate=True
        ),
        "membership_collapse_open": Output(
            MEMBERSHIP_UPLOAD_COLLAPSE_DATA_UPLOAD_ID, "is_open", allow_duplicate=True
        ),
        "predictor_upload_disabled": Output(
            PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
        "predictor_file_info": Output(
            PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True
        ),
        "delete_predictor_disabled": Output(
            DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
        "predictor_collapse_open": Output(
            PREDICTOR_UPLOAD_COLLAPSE_DATA_UPLOAD_ID, "is_open", allow_duplicate=True
        ),
        "sp_text": Output(
            STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID,
            "children",
            allow_duplicate=True,
        ),
        "sp_class": Output(
            STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID,
            "className",
            allow_duplicate=True,
        ),
        "sp_poll_disabled": Output(
            STREET_PROCESSING_POLL_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
        ),
    },
    inputs={"n_clicks": Input(DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID, "n_clicks")},
    state={"job_id": State(JOB_ID_STORE_SHARED_ID, "data")},
    prevent_initial_call=True,
)
def delete_membership_file(n_clicks, job_id):
    """Delete membership file and cascade-delete predictor, reset upload state."""
    if n_clicks is None:
        raise PreventUpdate

    log.info(f"Delete membership button clicked for job {job_id}")

    job = CosmonautJob(job_id=job_id, sync_files=False)

    if job.model.status != JOB_STATUS_PENDING:
        log.warning(f"Cannot delete upload - job {job_id} status is {job.model.status}")
        raise PreventUpdate

    job.delete_membership()

    return {
        "file_info": _file_status(False),
        "epsg_disabled": False,
        "delete_membership_disabled": True,
        "next_disabled": True,
        "viewport": {
            "center": DEFAULT_MAP_CENTER,
            "zoom": DEFAULT_MAP_ZOOM,
            "transition": "flyTo",
        },
        "tile_url": "",
        "slider_disabled": True,
        "upload_disabled": False,
        "init_store": False,
        "membership_collapse_open": True,
        "predictor_upload_disabled": True,
        "predictor_file_info": _file_status(False),
        "delete_predictor_disabled": True,
        "predictor_collapse_open": True,
        "sp_text": "Road network will be constructed in the background",
        "sp_class": "text-muted small",
        "sp_poll_disabled": True,
    }


@callback(
    Output(PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True),
    Output(DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(NEXT_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(PREDICTOR_UPLOAD_COLLAPSE_DATA_UPLOAD_ID, "is_open", allow_duplicate=True),
    Input(DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def delete_predictor_file(n_clicks, job_id):
    """Delete predictor file and reset predictor upload state."""
    if n_clicks is None:
        raise PreventUpdate

    log.info(f"Delete predictor button clicked for job {job_id}")

    job = CosmonautJob(job_id=job_id, sync_files=False)

    if job.model.status != JOB_STATUS_PENDING:
        log.warning(
            f"Cannot delete predictor - job {job_id} status is {job.model.status}"
        )
        raise PreventUpdate

    job.delete_predictor()

    return (
        _file_status(False),  # predictor file info
        True,  # disable delete predictor button
        True,  # disable next button (predictor required)
        False,  # re-enable predictor upload button
        True,  # show predictor upload collapse again
    )


@callback(
    Output(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled"),
    Output(DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID, "children"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "valid"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "invalid"),
    Input(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "value"),
    State(DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID, "data"),
)
def update_upload_state(epsg, file_uploaded):
    log.info(f"Validating EPSG code: {epsg}")

    try:
        check_epsg(epsg)
    except ValueError:
        return (
            True,
            "Please enter a valid EPSG code.",
            False,
            True,
        )
    if file_uploaded:
        return (
            True,
            "EPSG accepted",
            True,
            False,
        )
    return (
        False,
        "EPSG accepted",
        True,
        False,
    )


@callback(
    Output(STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID, "children"),
    Output(STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID, "className"),
    Output(STREET_PROCESSING_POLL_DATA_UPLOAD_ID, "disabled"),
    Input(STREET_PROCESSING_POLL_DATA_UPLOAD_ID, "n_intervals"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def poll_street_processing(n_intervals, job_id):
    """Poll street processing status and update the status hint."""
    if not job_id:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id, sync_files=False)
    status = job.get_street_processing_status()

    if status == "COMPLETED":
        return "Road network is constructed", "text-muted small", True
    elif status == "FAILED":
        return (
            "Road network construction failed! Re-upload membership file. "
            "If the problem persists, contact the maintainer.",
            "text-danger small",
            True,
        )
    # Still running
    return "Road network is being built...", "text-info small", False
