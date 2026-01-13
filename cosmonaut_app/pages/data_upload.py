"""Upload membership data and configure coordinate reference system.

This page is where you upload your cosmic ray neutron sensor measurement locations
or sampling points that will be used to plan the navigation route. The workflow
on this page involves two key steps:

1. **Specify EPSG Code**: Enter the coordinate reference system (CRS) of your data.
   The application validates the EPSG code in real-time and displays the coordinate
   system description. Common choices include:
   - 4326 (WGS84 latitude/longitude - global standard)
   - 25832 (ETRS89 / UTM zone 32N - Germany)
   - 31468 (DHDN / Gauss-Kruger zone 4 - Germany legacy)
   - 3857 (Web Mercator - web mapping)

2. **Upload CSV File**: Drag and drop or select a CSV/TXT file containing your
   membership data with coordinate columns. The system will parse your file,
   transform coordinates to WGS84 (EPSG:4326) for map display, and visualize
   your locations on the interactive map.

After uploading, your data is validated and the system automatically queries
OpenStreetMap for road networks within your data's geographic extent. The buffered
bounding box of your points determines which street data is retrieved for the next
step (street selection).

**File Requirements:**
- Format: CSV or TXT with delimiter-separated values
- Must include coordinate columns (latitude/longitude or projected coordinates)
- Coordinates should match the specified EPSG code
- Files are stored securely in your job's work directory

Once your data is uploaded, validated, and displayed on the map, proceed to the
street selection page to choose which roads to include in your route.

NOTE: File upload uses dcc.Upload with base64 encoding. The OsmRoads class handles
OpenStreetMap querying with proper buffering around the data extent. Coordinate
transformation uses pyproj with CRS validation via the pyproj.CRS class.
"""

import os
import logging
import dash
from dash import html, register_page, dcc, callback, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.constants import (
    JOB_STATUS_PENDING,
    DEFAULT_MAP_CENTER,
    DEFAULT_MAP_ZOOM,
)
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID,
    DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID,
    DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
    DELETE_FILE_BUTTON_DATA_UPLOAD_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    EPSG_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    LOADING_OVERLAY_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
)
from cosmonaut_app.transformation import (
    OsmRoads,
)
from cosmonaut_app.classification_plot import ClassificationPlot
from cosmonaut_app.pydantic_models import check_epsg
from cosmonaut_app.layout import (
    page_container_split_layout,
    create_card_input,
    progress_footer,
    create_map,
    build_url_step,
    create_reset_banner,
    create_reset_modal,
)

register_page(
    __name__,
    path_template="/job/<job_id>/data-upload",
    name="Data Upload",
    title="Data Upload",
    description="Upload data for this job.",
    dynamic=True,
)


def layout(job_id):
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()
    is_active = status == JOB_STATUS_PENDING

    # Determine if file is uploaded and EPSG should be disabled
    file_uploaded = (
        job.model.classification_upload.get("file_name") != "No file uploaded"
    )
    epsg_disabled = (not is_active) or file_uploaded

    # Show delete button only if file uploaded AND job status is PENDING
    delete_button_visible = file_uploaded and is_active
    delete_button_style = (
        {"display": "block"} if delete_button_visible else {"display": "none"}
    )

    card_body = []

    # Add reset banner if not PENDING
    if not is_active:
        card_body.append(create_reset_banner(job_id, status))

    # Add stores and form components
    card_body.extend(
        [
            dcc.Store(id=EPSG_STORE_SHARED_ID),
            dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id),
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
                style={"background-color": "#e9ecef"} if epsg_disabled else {},
            ),
            dbc.FormText(
                "Common choices: 4326, 25832, 3857, …",
                color="secondary",
                className="mb-1",
            ),
            dbc.FormText(
                id=DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID, className="fw-semibold"
            ),
            html.Div(
                dcc.Upload(
                    id=DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
                    accept=".csv,.txt",
                    children=html.Div(
                        [
                            html.I(className="bi bi-cloud-arrow-up fs-4 me-2"),
                            "Drag & drop or click to select a .csv or .txt file",
                        ],
                    ),
                    multiple=False,
                    disabled=True
                    if not is_active
                    else True,  # enabled after valid EPSG when active
                    style=(
                        {"backgroundColor": "#e9ecef", "cursor": "not-allowed"}
                        if not is_active
                        else {}
                    ),
                ),
                className="my-3",
            ),
            html.Div(
                job.model.classification_upload["file_name"],
                id=DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
                className="text-muted",
            ),
            dbc.Button(
                "Delete File",
                id=DELETE_FILE_BUTTON_DATA_UPLOAD_ID,
                color="danger",
                size="sm",
                className="mt-2",
                style=delete_button_style,
                disabled=(not is_active),
            ),
        ]
    )

    # Add reset modal
    card_body.append(create_reset_modal())

    user_info_path = build_url_step("user_info", job_id)
    street_selection_path = build_url_step("street_selection", job_id)

    classification_file = job.model.classification_upload["file_name"]
    classification_file_path = os.path.join(job.input_dir, classification_file)
    next_disabled = not os.path.exists(classification_file_path)

    footer = progress_footer(
        prev_url=user_info_path,
        next_url=street_selection_path,
        next_id=NEXT_BUTTON_DATA_UPLOAD_ID,
        next_disabled=next_disabled,
    )

    map = create_map(job=job)
    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_split_layout(map, input_container)


@callback(
    Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport"),
    Output(DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, "children"),
    Output(NEXT_BUTTON_DATA_UPLOAD_ID, "disabled"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "disabled"),
    Output(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Output(DELETE_FILE_BUTTON_DATA_UPLOAD_ID, "style"),
    Input(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "contents"),
    State(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "filename"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    State(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "value"),
    prevent_initial_call=True,
)
def upload_file(contents, filename, job_id, epsg_input):
    """Upload a file to the server and save it in the job working directory."""
    if not contents or not filename:
        raise PreventUpdate

    try:
        epsg_input = check_epsg(epsg_input)
    except ValueError as e:
        return (
            dash.no_update,
            str(e),
            True,
            False,
            None,
            False,
            dash.no_update,
        )

    job = CosmonautJob(job_id=job_id)
    job.model.epsg = epsg_input
    try:
        classification_data, file_path, bounds = job.upload_file(
            filename, contents, epsg_input
        )
    except ValueError as e:
        return dash.no_update, str(e), True, False, None, False, dash.no_update

    reposition_map = {
        "bounds": bounds,
        "transition": "flyTo",
    }

    osm = OsmRoads(classification_data, epsg_output=epsg_input)
    osm.run_osm_query(job.input_dir)

    plot = ClassificationPlot(file_path, job_id, src_epsg=f"EPSG:{epsg_input}")
    plot.generate_plots()

    job.save()
    return (
        reposition_map,
        f"Selected file: {os.path.basename(file_path)}",
        False,  # Enable next button
        True,  # Disable EPSG input
        None,  # Clear upload contents
        False,  # Hide loading overlay
        {"display": "block"},  # Show delete button
    )


@callback(
    Output(DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, "children", allow_duplicate=True),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(DELETE_FILE_BUTTON_DATA_UPLOAD_ID, "style", allow_duplicate=True),
    Output(NEXT_BUTTON_DATA_UPLOAD_ID, "disabled", allow_duplicate=True),
    Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport", allow_duplicate=True),
    Output(LOADING_OVERLAY_SHARED_ID, "is_open", allow_duplicate=True),
    Input(DELETE_FILE_BUTTON_DATA_UPLOAD_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def delete_uploaded_file(n_clicks, job_id):
    """Delete uploaded file and reset upload state.

    When user clicks delete button:
    1. Verify job status is PENDING (safety check)
    2. Call job.delete_upload() to remove file and reset data
    3. Update UI to show "No file uploaded"
    4. Re-enable EPSG input field
    5. Hide delete button
    6. Disable next button (can't proceed without file)
    7. Reset map to default view

    Parameters
    ----------
    n_clicks : int
        Number of times delete button clicked
    job_id : str
        Current job ID

    Returns
    -------
    tuple
        (file_info_text, epsg_disabled, delete_button_style,
         next_button_disabled, map_viewport, loading_overlay)
    """
    if n_clicks is None:
        raise PreventUpdate

    logging.info(f"Delete file button clicked for job {job_id}")

    # Load job and verify status
    job = CosmonautJob(job_id=job_id)

    # Safety check: Only allow deletion if job status is PENDING
    if job.model.status != JOB_STATUS_PENDING:
        logging.warning(
            f"Cannot delete upload - job {job_id} status is {job.model.status}"
        )
        raise PreventUpdate

    # Delete upload
    job.delete_upload()

    # File info text
    file_info_text = "No file uploaded"

    # Reset map to default view (using constants)
    default_viewport = {
        "center": DEFAULT_MAP_CENTER,
        "zoom": DEFAULT_MAP_ZOOM,
        "transition": "flyTo",
    }

    return (
        file_info_text,
        False,  # Enable EPSG input
        {"display": "none"},  # Hide delete button
        True,  # Disable next button (no file uploaded)
        default_viewport,  # Reset map
        False,  # Hide loading overlay
    )


@callback(
    Output(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled"),
    Output(DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID, "children"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "valid"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "invalid"),
    Input(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "value"),
)
def validate_epsg(epsg):
    # Reset when empty/cleared
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
    return (
        False,
        "EPSG accepted",
        True,
        False,
    )
