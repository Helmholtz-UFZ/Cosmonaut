"""Data Upload page for a specific job."""

import os
import logging
import dash
from dash import html, register_page, dcc, callback, Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from pyproj.exceptions import CRSError
from pyproj import CRS

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_DROPZONE_DIV_DATA_UPLOAD_ID,
    DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID,
    DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID,
    DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
    NEXT_BUTTON_DATA_UPLOAD_ID,
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    EPSG_STORE_SHARED_ID,
    FILE_PATH_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    OSM_FILE_PATH_STORE_SHARED_ID,
)
from cosmonaut_app.transformation import (
    OsmRoads,
)
from cosmonaut_app.classification_plot import ClassificationPlot
from cosmonaut_app.layout import (
    page_container_split_layout,
    create_card_input,
    progress_footer,
    create_map,
    build_url_step,
)

register_page(
    __name__,
    path_template="/job/<job_id>/data-upload",
    name="Data Upload",
    title="Data Upload",
    description="Upload data for this job.",
    dynamic=True,
)


def is_epsg_valid(epsg):
    try:
        if isinstance(epsg, str) and epsg.upper().startswith("EPSG:"):
            epsg = epsg[5:]
        epsg = int(epsg)
    except (TypeError, ValueError):
        return None, False

    # Validate with pyproj
    try:
        CRS.from_epsg(epsg)
    except (CRSError, ValueError, TypeError):
        return None, False

    return epsg, True


def layout(job_id):
    job = CosmonautJob(job_id=job_id)
    card_body = [
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
                    id=DATA_UPLOAD_DROPZONE_DIV_DATA_UPLOAD_ID,
                ),
                multiple=False,
                disabled=True,  # enabled after valid EPSG
            ),
            className="my-3",
        ),
        html.Div(
            job.model.classification_upload["file_name"],
            id=DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
            className="text-muted",
        ),
        # hidden holders required by callbacks
        html.Div(id=FILE_PATH_STORE_SHARED_ID, style={"display": "none"}),
        html.Div(id=OSM_FILE_PATH_STORE_SHARED_ID, style={"display": "none"}),
    ]

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

    epsg_input, epsg_valid = is_epsg_valid(epsg_input)
    if not epsg_valid:
        return (
            dash.no_upadte,
            "Please enter a valid EPSG code before uploading a file.",
            True,
            False,
        )

    job = CosmonautJob(job_id=job_id)
    try:
        classification_data, file_path, bounds = job.upload_file(
            filename, contents, epsg_input
        )
    except ValueError as e:
        return dash.no_update, str(e), True, False

    reposition_map = {
        "bounds": bounds,
        "transition": "flyTo",
    }
    logging.info(reposition_map)

    osm = OsmRoads(classification_data, epsg_output=epsg_input)
    osm.run_osm_query(job.input_dir)

    plot = ClassificationPlot(file_path, job_id, src_epsg=f"EPSG:{epsg_input}")
    plot.generate_plots()

    job.save()
    return reposition_map, f"Selected file: {os.path.basename(file_path)}", False, True


@callback(
    Output(DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID, "disabled"),
    Output(DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID, "children"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "valid"),
    Output(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "invalid"),
    Input(DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, "value"),
)
def validate_epsg(epsg):
    # Reset when empty/cleared
    logging.info("Validating EPSG code: %s", epsg)
    _epsg, valid = is_epsg_valid(epsg)
    if valid:
        return (
            False,
            "EPSG accepted",
            True,
            False,
        )
    else:
        return (
            True,
            "Invalid EPSG code",
            False,
            True,
        )
