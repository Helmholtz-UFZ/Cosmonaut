"""Data Upload page for a specific job."""

from dash import html, register_page, dcc
import dash_bootstrap_components as dbc
from cosmonaut_app.ui.page import page_layout, progress_footer
from cosmonaut_app.constants.html_ids import (
    DATA_UPLOAD_DROPZONE_DIV_DATA_UPLOAD_ID,
    DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID,
    DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID,
    DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID,
    DATA_UPLOAD_NEXT_BUTTON_DATA_UPLOAD_ID,
    DATA_UPLOAD_PREV_BUTTON_DATA_UPLOAD_ID,
    DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID,
    FILE_PATH_STORE_SHARED_ID,
    OSM_FILE_PATH_STORE_SHARED_ID,
    OUTPUT_DATA_UPLOAD_DIV_DATA_UPLOAD_ID,
    OUTPUT_MINIO_STATUS_DIV_DATA_UPLOAD_ID,
    OUTPUT_OSM_QUERY_DIV_DATA_UPLOAD_ID,
    PLOT_GENERATION_STATUS_DIV_DATA_UPLOAD_ID,
    TOAST_STACK_CONTAINER_DATA_UPLOAD_ID,
)

register_page(
    __name__,
    path_template="/job/<job_id>/data-upload",
    name="Data Upload",
    title="Data Upload",
    description="Upload data for this job.",
    dynamic=True,
)


def layout(job_id=None, **kwargs):
    body = [
        html.P(
            "Please enter a valid EPSG code and then upload your membership data file.",
            className="text-muted",
        ),
        dbc.Label("EPSG code", html_for=DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID, className="mt-2"),
        dbc.Input(
            id=DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID,
            type="number",
            placeholder="e.g., 25832",
            min=1000,
            step=1,
            inputMode="numeric",
        ),
        dbc.FormText(
            "Common choices: 4326, 25832, 3857, …",
            color="secondary",
            className="mb-1",
        ),
        dbc.FormText(id=DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID, className="fw-semibold"),
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
        html.Div(id=DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID, className="text-muted"),
        # hidden holders required by callbacks
        html.Div(id=FILE_PATH_STORE_SHARED_ID, style={"display": "none"}),
        html.Div(id=OSM_FILE_PATH_STORE_SHARED_ID, style={"display": "none"}),
    ]

    footer = progress_footer(
        prev=dbc.Button(
            [html.I(className="bi bi-arrow-left me-1"), "Previous"],
            id=DATA_UPLOAD_PREV_BUTTON_DATA_UPLOAD_ID,
            color="secondary",
            outline=True,
        ),
        next_=dbc.Button(
            [html.I(className="bi bi-arrow-right-circle me-1"), "Next"],
            id=DATA_UPLOAD_NEXT_BUTTON_DATA_UPLOAD_ID,
            color="primary",
            disabled=True,
        ),
    )

    below = html.Div(
        [
            html.Div(id=OUTPUT_DATA_UPLOAD_DIV_DATA_UPLOAD_ID),
            html.Div(id=OUTPUT_OSM_QUERY_DIV_DATA_UPLOAD_ID),
            html.Div(id=PLOT_GENERATION_STATUS_DIV_DATA_UPLOAD_ID),
            html.Div(id=OUTPUT_MINIO_STATUS_DIV_DATA_UPLOAD_ID),
        ],
        id=TOAST_STACK_CONTAINER_DATA_UPLOAD_ID,
        className="toast-stack",
    )

    return page_layout(
        title="Data Upload",
        body=body,
        job_id=job_id,
        footer=footer,
        below=below,
        step_index=2,
    )
