"""Data Upload page for a specific job."""

from dash import html, register_page, dcc
import dash_bootstrap_components as dbc
from cosmonaut_app.ui.page import page_layout, progress_footer

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
        dbc.Label("EPSG code", html_for="data-upload-epsg", className="mt-2"),
        dbc.Input(
            id="data-upload-epsg",
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
        dbc.FormText(id="data-upload-epsg-helper", className="fw-semibold"),
        html.Div(
            dcc.Upload(
                id="data-upload-upload",
                accept=".csv,.txt",
                children=html.Div(
                    [
                        html.I(className="bi bi-cloud-arrow-up fs-4 me-2"),
                        "Drag & drop or click to select a .csv or .txt file",
                    ],
                    id="data-upload-dropzone",
                ),
                multiple=False,
                disabled=True,  # enabled after valid EPSG
            ),
            className="my-3",
        ),
        html.Div(id="data-upload-file-info", className="text-muted"),
        # hidden holders required by callbacks
        html.Div(id="file-path", style={"display": "none"}),
        html.Div(id="osm-file-path", style={"display": "none"}),
    ]

    footer = progress_footer(
        prev=dbc.Button(
            [html.I(className="bi bi-arrow-left me-1"), "Previous"],
            id="data-upload-prev",
            color="secondary",
            outline=True,
        ),
        next_=dbc.Button(
            [html.I(className="bi bi-arrow-right-circle me-1"), "Next"],
            id="data-upload-next",
            color="primary",
            disabled=True,
        ),
    )

    below = html.Div(
        [
            html.Div(id="output-data-upload"),
            html.Div(id="output-osm-query"),
            html.Div(id="plot-generation-status"),
            html.Div(id="output-minIO-status"),
        ],
        id="toast-stack",
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
