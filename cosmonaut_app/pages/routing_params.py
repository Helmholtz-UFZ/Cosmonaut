from dash import html, register_page, dcc
import dash_bootstrap_components as dbc
from cosmonaut_app.config import osm_tags_mapping
from cosmonaut_app.ui.page import page_layout, progress_footer

register_page(
    __name__,
    path_template="/job/<job_id>/routing-params",
    name="Routing Parameters",
    title="Routing Parameters",
    description="Tune parameters before route calculation.",
    dynamic=True,
)


def layout(job_id=None, **kwargs):
    body = [
        html.P(
            "Prüfen und ändern Sie die Parameter. Anschließend startet die Routenberechnung.",
            className="text-muted",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Segments per class"),
                            dbc.Input(id="cfg-sn", type="number", min=1, max=10),
                        ]
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Max distance [km]"),
                            dbc.Input(id="cfg-md", type="number", min=1),
                        ]
                    ),
                    md=6,
                ),
            ],
            className="g-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Time limit [h]"),
                            dbc.Input(id="cfg-tl", type="number", min=1),
                        ]
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Lower benefit limit"),
                            dbc.Input(
                                id="cfg-lbf", type="number", min=0, max=1, step=0.05
                            ),
                        ]
                    ),
                    md=6,
                ),
            ],
            className="g-2 mt-1",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Objective"),
                            dbc.Select(
                                id="cfg-oo",
                                options=[
                                    {"label": "Distance (d)", "value": "d"},
                                    {"label": "Time (t)", "value": "t"},
                                ],
                            ),
                        ]
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Max ACO iteration"),
                            dbc.Input(id="cfg-mai", type="number", min=1),
                        ]
                    ),
                    md=6,
                ),
            ],
            className="g-2 mt-1",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Ant number"),
                            dbc.Input(id="cfg-an", type="number", min=1),
                        ]
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Reversed network"),
                            dbc.Checklist(
                                id="cfg-ir",
                                options=[{"label": " yes", "value": True}],
                                value=[],
                            ),
                        ]
                    ),
                    md=6,
                ),
            ],
            className="g-2 mt-1",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Working dir"),
                            dbc.Input(id="cfg-wd", type="text", disabled=True),
                        ]
                    ),
                    md=12,
                ),
            ],
            className="g-2 mt-1",
        ),
        dcc.Interval(id="params-load", interval=100, n_intervals=0, max_intervals=1),
        dcc.Store(id="routing-complete", data=False),
        dcc.Store(id="tags-last-selection", storage_type="session"),
        dcc.Dropdown(
            id="tags-dropdown",
            options=[{"label": tag, "value": tag} for tag in osm_tags_mapping.keys()],
            value=[],
            multi=True,
            style={"display": "none"},
        ),
    ]

    footer = progress_footer(
        prev=dbc.Button(
            [html.I(className="bi bi-arrow-left me-1"), "Back"],
            color="secondary",
            outline=True,
            href=f"/job/{job_id}/street-selection",
        ),
        next_=dbc.Button(
            [html.I(className="bi bi-cpu me-1"), "Run routing"],
            id="run-routing",
            color="primary",
        ),
    )

    below = dbc.Alert(
        id="params-alert",
        children="",
        color="info",
        is_open=False,
        dismissable=True,
        className="mt-3",
    )

    return page_layout(
        title="Routing Parameters",
        body=body,
        job_id=job_id,
        footer=footer,
        below=below,
        step_index=4,
    )
