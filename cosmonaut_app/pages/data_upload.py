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
   your locations on the interactive map. After uploading, the system automatically
   queries OpenStreetMap for road networks within your data's geographic extent.

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

File upload uses dcc.Upload with base64 encoding. The OsmDownloader class handles
OpenStreetMap downloading with proper buffering around the data extent. Coordinate
transformation uses pyproj with CRS validation via the pyproj.CRS class.
Predictor upload is validated via parse_predictor_file and cross-checked against
the membership file using validate_predictor_membership_consistency. The exact
predictor file format is not duplicated here — it is sourced at runtime from
DESCRIPTION_PREDICTOR in the sensor-routing package and displayed in the UI
tooltip on the upload button.
"""

import logging

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html, register_page
from dash.exceptions import PreventUpdate
from sensor_routing.full_pipeline_cli import (
    DESCRIPTION_MEMBERSHIP,
    DESCRIPTION_PREDICTOR,
)

from cosmonaut_app.background_job_manager import get_background_job_manager
from cosmonaut_app.classification_plot import ClassificationPlot
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
    LOADING_OVERLAY_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MEMBERSHIP_ERROR_DIV_DATA_UPLOAD_ID,
    MEMBERSHIP_TILE_LAYER_MAP_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    PREDICTOR_ERROR_DIV_DATA_UPLOAD_ID,
    PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID,
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


def _help_icon(description):
    """Create a question-mark icon with a native browser tooltip."""
    return html.Span(
        "\u24d8",  # ⓘ circled information source
        className="text-muted ms-1",
        title=description.strip(),
    )


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
    predictor_upload_disabled = not membership_uploaded
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
            html.P(
                "Please enter a valid EPSG code and then upload your membership data file.",
                className="text-muted",
            ),
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
                id=DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID, className="fw-semibold"
            ),
            # --- Membership upload section ---
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
                    _help_icon(DESCRIPTION_MEMBERSHIP),
                ],
            ),
            html.Div(
                id=MEMBERSHIP_ERROR_DIV_DATA_UPLOAD_ID, className="text-danger small"
            ),
            html.Div(
                "Uploaded" if membership_uploaded else "Not uploaded",
                id=DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
                className="text-muted",
            ),
            dbc.Button(
                "Delete Membership",
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
                        tooltip={"placement": "bottom", "always_visible": False},
                        disabled=slider_disabled,
                    ),
                ],
                className="mb-3",
            ),
            # --- Predictor upload section ---
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
                    _help_icon(DESCRIPTION_PREDICTOR),
                ],
            ),
            html.Div(
                id=PREDICTOR_ERROR_DIV_DATA_UPLOAD_ID, className="text-danger small"
            ),
            html.Div(
                "Uploaded" if predictor_uploaded else "Not uploaded",
                id=PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID,
                className="text-muted",
            ),
            dbc.Button(
                "Delete Predictor",
                id=DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID,
                color="danger",
                size="sm",
                className="mt-2",
                disabled=delete_predictor_disabled,
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
    )
    return page_container_fullscreen_layout(input_container)


# Clientside callback: open loading overlay instantly in the browser when a file
# is selected.  A server-side callback here would queue behind the slow processing
# callback (due to allow_duplicate), leaving the overlay stuck open.
dash.clientside_callback(
    """
    function(filename, predictor_filename) {
        return !!(filename || predictor_filename);
    }
    """,
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
    Input(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
    prevent_initial_call=True,
)


@callback(
    Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport"),
    Output(DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, "children"),
    Output(NEXT_BUTTON_DATA_UPLOAD_ID, "disabled"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "disabled"),
    Output(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Output(DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID, "disabled"),
    Output(MEMBERSHIP_TILE_LAYER_MAP_ID, "url", allow_duplicate=True),
    Output(DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID, "disabled"),
    Output(
        DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
    ),
    Output(MEMBERSHIP_ERROR_DIV_DATA_UPLOAD_ID, "children"),
    Output(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled"),
    Output(PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID, "children"),
    Output(PREDICTOR_ERROR_DIV_DATA_UPLOAD_ID, "children"),
    Output(DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "disabled"),
    Output(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"),
    Output(MEMBERSHIP_TILE_LAYER_MAP_ID, "opacity"),
    Output(
        STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True
    ),
    Output(
        STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID, "className", allow_duplicate=True
    ),
    Output(STREET_PROCESSING_POLL_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Input(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"),
    Input(DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID, "value"),
    Input(DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID, "data"),
    Input(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"),
    State(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
    State(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    State(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "value"),
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
    n_out = len(ctx.outputs_list)

    def _no_update(**overrides):
        """Build a no_update tuple, overriding specific output indices by name."""
        result = [dash.no_update] * n_out
        # Output index mapping (must match callback @Output order above)
        idx = {
            "viewport": 0,
            "file_info": 1,
            "next_disabled": 2,
            "epsg_disabled": 3,
            "upload_contents": 4,
            "loading": 5,
            "delete_membership_disabled": 6,
            "tile_url": 7,
            "slider_disabled": 8,
            "upload_disabled": 9,
            "membership_error": 10,
            "predictor_upload_disabled": 11,
            "predictor_file_info": 12,
            "predictor_error": 13,
            "delete_predictor_disabled": 14,
            "predictor_contents": 15,
            "tile_opacity": 16,
            "sp_text": 17,
            "sp_class": 18,
            "sp_poll_disabled": 19,
        }
        for key, value in overrides.items():
            result[idx[key]] = value
        return tuple(result)

    # --- Membership upload branch ---
    if triggered == DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID:
        if not contents or not filename:
            raise PreventUpdate

        logging.info(
            f"Uploading membership file {filename} for job {job_id} with EPSG {epsg_input}"
        )
        try:
            epsg_input = check_epsg(epsg_input)
        except ValueError as e:
            logging.debug(f"Invalid EPSG code {epsg_input}: {e}")
            return _no_update(
                next_disabled=True,
                epsg_disabled=False,
                upload_contents=None,
                loading=False,
                membership_error=str(e),
            )

        job = CosmonautJob(job_id=job_id)
        job.model.epsg = epsg_input
        # Delete old files just in case
        job.delete_membership()
        try:
            file_path, bounds, membership_df = job.upload_membership(
                filename, contents, epsg_input
            )
        except FileValidationError as e:
            return _no_update(
                file_info=str(e),
                next_disabled=True,
                epsg_disabled=False,
                upload_contents=None,
                loading=False,
                membership_error=str(e),
            )

        logging.debug("Upload finished, generating plots and submitting OSM task")

        reposition_map = {
            "bounds": bounds,
            "transition": "flyTo",
        }

        plot = ClassificationPlot(
            membership_df, job.working_dir, src_epsg=f"EPSG:{epsg_input}"
        )
        plot.generate_plots()
        logging.debug("Classification plots generated.")

        tile_url = get_tile_url(job_id, job.working_dir)

        # Submit heavy OSM download + street selection to Celery worker
        job_manager = get_background_job_manager()
        task_id, failed = job_manager.submit_upload_job(job, epsg_input)
        if not failed:
            job.model.membership_upload["street_processing"] = task_id
        else:
            job.model.membership_upload["street_processing"] = "FAILED"
        job.save()

        logging.debug(f"Membership file uploaded and processed for job {job_id}")

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

        return _no_update(
            viewport=reposition_map,
            file_info="Uploaded",
            next_disabled=True,
            epsg_disabled=True,
            upload_contents=None,
            loading=False,
            delete_membership_disabled=False,
            tile_url=tile_url,
            slider_disabled=False,
            upload_disabled=True,
            membership_error="",
            predictor_upload_disabled=False,
            predictor_file_info="Not uploaded",
            predictor_error="",
            delete_predictor_disabled=True,
            sp_text=sp_text,
            sp_class=sp_class,
            sp_poll_disabled=sp_poll_disabled,
        )

    # --- Predictor upload branch ---
    if triggered == PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID:
        if not predictor_contents or not predictor_filename:
            raise PreventUpdate

        logging.info(f"Uploading predictor file for job {job_id}")

        job = CosmonautJob(job_id=job_id)
        try:
            job.upload_predictor(predictor_contents)
        except FileValidationError as e:
            return _no_update(
                next_disabled=True,
                loading=False,
                predictor_file_info="Not uploaded",
                predictor_error=str(e),
                delete_predictor_disabled=True,
                predictor_contents=None,
            )

        return _no_update(
            next_disabled=False,
            loading=False,
            predictor_file_info="Uploaded",
            predictor_error="",
            delete_predictor_disabled=False,
            predictor_contents=None,
        )

    # --- Opacity slider branch ---
    if triggered == DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID:
        if not job_id:
            raise PreventUpdate

        return _no_update(tile_opacity=opacity)

    # --- Init store branch (page load with existing upload) ---
    if triggered == DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID:
        if init_trigger and job_id:
            return _no_update(
                slider_disabled=False,
                upload_disabled=True,
            )

        return _no_update(slider_disabled=True)

    raise PreventUpdate


@callback(
    Output(DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(NEXT_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport", allow_duplicate=True),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Output(MEMBERSHIP_TILE_LAYER_MAP_ID, "url", allow_duplicate=True),
    Output(DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(
        DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True
    ),
    Output(DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID, "data", allow_duplicate=True),
    Output(PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True),
    Output(DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(
        STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True
    ),
    Output(
        STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID, "className", allow_duplicate=True
    ),
    Output(STREET_PROCESSING_POLL_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Input(DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def delete_membership_file(n_clicks, job_id):
    """Delete membership file and cascade-delete predictor, reset upload state."""
    if n_clicks is None:
        raise PreventUpdate

    logging.info(f"Delete membership button clicked for job {job_id}")

    job = CosmonautJob(job_id=job_id)

    if job.model.status != JOB_STATUS_PENDING:
        logging.warning(
            f"Cannot delete upload - job {job_id} status is {job.model.status}"
        )
        raise PreventUpdate

    # Cascade: deletes predictor first, then membership
    job.delete_membership()

    default_viewport = {
        "center": DEFAULT_MAP_CENTER,
        "zoom": DEFAULT_MAP_ZOOM,
        "transition": "flyTo",
    }

    return (
        "Not uploaded",  # membership file info
        False,  # enable EPSG input
        True,  # disable delete membership button
        True,  # disable next button
        default_viewport,  # reset map viewport
        False,  # hide loading overlay
        "",  # clear tile URL
        True,  # disable opacity slider
        False,  # enable upload component
        False,  # reset init store
        True,  # disable predictor upload
        "Not uploaded",  # predictor file info
        True,  # disable delete predictor button
        "Road network will be constructed in the background",  # reset sp text
        "text-muted small",  # reset sp class
        True,  # disable sp polling
    )


@callback(
    Output(PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True),
    Output(DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(NEXT_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Input(DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def delete_predictor_file(n_clicks, job_id):
    """Delete predictor file and reset predictor upload state."""
    if n_clicks is None:
        raise PreventUpdate

    logging.info(f"Delete predictor button clicked for job {job_id}")

    job = CosmonautJob(job_id=job_id)

    if job.model.status != JOB_STATUS_PENDING:
        logging.warning(
            f"Cannot delete predictor - job {job_id} status is {job.model.status}"
        )
        raise PreventUpdate

    job.delete_predictor()

    return (
        "Not uploaded",  # predictor file info
        True,  # disable delete predictor button
        True,  # disable next button (predictor required)
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
    logging.info(f"Validating EPSG code: {epsg}")

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

    job = CosmonautJob(job_id=job_id)
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
