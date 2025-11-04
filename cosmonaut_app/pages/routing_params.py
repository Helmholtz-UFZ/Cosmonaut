from dash import html, register_page, dcc
import dash_bootstrap_components as dbc
from cosmonaut_app.config import osm_tags_mapping
from cosmonaut_app.ui.page import page_layout, progress_footer
from cosmonaut_app.constants.html_ids import (
    CFG_AN_INPUT_ROUTING_PARAMS_ID,
    CFG_IR_INPUT_ROUTING_PARAMS_ID,
    CFG_LBF_INPUT_ROUTING_PARAMS_ID,
    CFG_MAI_INPUT_ROUTING_PARAMS_ID,
    CFG_OO_INPUT_ROUTING_PARAMS_ID,
    CFG_SN_INPUT_ROUTING_PARAMS_ID,
    CFG_TL_INPUT_ROUTING_PARAMS_ID,
    CFG_WD_INPUT_ROUTING_PARAMS_ID,
    PARAMS_ALERT_ALERT_ROUTING_PARAMS_ID,
    PARAMS_LOAD_BUTTON_ROUTING_PARAMS_ID,
    ROUTING_COMPLETE_STORE_SHARED_ID,
    RUN_ROUTING_BUTTON_ROUTING_PARAMS_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    TAGS_LAST_SELECTION_STORE_SHARED_ID,
)

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
                            dbc.Input(
                                id=CFG_SN_INPUT_ROUTING_PARAMS_ID,
                                type="number",
                                min=1,
                                max=10,
                            ),
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
                            dbc.Input(
                                id=CFG_TL_INPUT_ROUTING_PARAMS_ID, type="number", min=1
                            ),
                        ]
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Lower benefit limit"),
                            dbc.Input(
                                id=CFG_LBF_INPUT_ROUTING_PARAMS_ID,
                                type="number",
                                min=0,
                                max=1,
                                step=0.05,
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
                                id=CFG_OO_INPUT_ROUTING_PARAMS_ID,
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
                            dbc.Input(
                                id=CFG_MAI_INPUT_ROUTING_PARAMS_ID, type="number", min=1
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
                            dbc.InputGroupText("Ant number"),
                            dbc.Input(
                                id=CFG_AN_INPUT_ROUTING_PARAMS_ID, type="number", min=1
                            ),
                        ]
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.InputGroup(
                        [
                            dbc.InputGroupText("Reversed network"),
                            dbc.Checklist(
                                id=CFG_IR_INPUT_ROUTING_PARAMS_ID,
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
                            dbc.Input(
                                id=CFG_WD_INPUT_ROUTING_PARAMS_ID,
                                type="text",
                                disabled=True,
                            ),
                        ]
                    ),
                    md=12,
                ),
            ],
            className="g-2 mt-1",
        ),
        dcc.Interval(
            id=PARAMS_LOAD_BUTTON_ROUTING_PARAMS_ID,
            interval=100,
            n_intervals=0,
            max_intervals=1,
        ),
        dcc.Store(id=ROUTING_COMPLETE_STORE_SHARED_ID, data=False),
        dcc.Store(id=TAGS_LAST_SELECTION_STORE_SHARED_ID, storage_type="session"),
        dcc.Dropdown(
            id=TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
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
            id=RUN_ROUTING_BUTTON_ROUTING_PARAMS_ID,
            color="primary",
        ),
    )

    below = dbc.Alert(
        id=PARAMS_ALERT_ALERT_ROUTING_PARAMS_ID,
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
