"""Street Selection page: select streets for routing."""

from dash import html, register_page, dcc  # add dcc
import dash_bootstrap_components as dbc
from cosmonaut_app.config import osm_tags_mapping
from cosmonaut_app.ui.page import page_layout, progress_footer
from cosmonaut_app.constants.html_ids import (
    ACTION_ALERT_ALERT_STREET_SELECTION_ID,
    CANCEL_RESET_BUTTON_STREET_SELECTION_ID,
    CONFIRM_RESET_BUTTON_STREET_SELECTION_ID,
    LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
    REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID,
    RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID,
    RESET_ROADS_BUTTON_STREET_SELECTION_ID,
    SELECTION_COUNT_DIV_STREET_SELECTION_ID,
    STREET_SELECTION_NEXT_BUTTON_STREET_SELECTION_ID,
    STREET_SELECTION_PREV_BUTTON_STREET_SELECTION_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    TAGS_LAST_SELECTION_STORE_SHARED_ID,
    TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
    TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
    UNDO_BUTTON_BUTTON_STREET_SELECTION_ID,
)

register_page(
    __name__,
    path_template="/job/<job_id>/street-selection",
    name="Street Selection",
    title="Street Selection",
    description="Select streets for the routing process.",
    dynamic=True,
)


def layout(job_id=None, **kwargs):
    body = [
        html.P(
            "Wählen Sie die gewünschten Straßen im linken Kartenbereich aus. "
            "Klicken Sie eine Straße an, um sie zu markieren. Mit dem Button "
            "'Remove selected' entfernen Sie die Auswahl. 'Keep largest' behält die größte "
            "zusammenhängende Teilmenge innerhalb der aktuell gewählten Straßentypen.",
            className="text-muted",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Label(
                        "Straßenauswahl", html_for=TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, className="mt-2"
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.ButtonGroup(
                        [
                            dbc.Button(
                                "Select all",
                                id=TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
                                size="sm",
                                color="link",
                            ),
                            dbc.Button(
                                "Select none",
                                id=TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
                                size="sm",
                                color="link",
                            ),
                        ],
                        size="sm",
                        className="ms-2",
                    ),
                    width="auto",
                    className="d-flex align-items-end",
                ),
            ],
            className="g-0",
        ),
        dbc.Checklist(
            id=TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
            options=[{"label": tag, "value": tag} for tag in osm_tags_mapping.keys()],
            value=[],  # will be initialized via callback
            switch=True,
            inline=True,
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.ButtonGroup(
                        [
                            dbc.Button(
                                [
                                    html.I(className="bi bi-eraser me-1"),
                                    "Remove selected",
                                ],
                                id=REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID,
                                color="danger",
                                outline=True,
                            ),
                            dbc.Button(
                                [
                                    html.I(className="bi bi-diagram-3 me-1"),
                                    "Keep largest",
                                ],
                                id=LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
                                color="primary",
                                outline=True,
                            ),
                            dbc.Button(
                                [
                                    html.I(
                                        className="bi bi-arrow-counterclockwise me-1"
                                    ),
                                    "Reset edits",
                                ],
                                id=RESET_ROADS_BUTTON_STREET_SELECTION_ID,
                                color="secondary",
                                outline=True,
                            ),
                            dbc.Button(
                                [
                                    html.I(className="bi bi-arrow-90deg-left me-1"),
                                    "Undo",
                                ],
                                id=UNDO_BUTTON_BUTTON_STREET_SELECTION_ID,
                                color="secondary",
                                outline=True,
                            ),
                        ],
                        size="md",
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Badge(
                        "Selected: 0",
                        id=SELECTION_COUNT_DIV_STREET_SELECTION_ID,
                        color="info",
                        className="ms-2",
                    ),
                    width="auto",
                    className="d-flex align-items-center",
                ),
            ],
            className="g-2 align-items-center mt-2",
        ),
        # Reset confirmation modal
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Reset edits?")),
                dbc.ModalBody(
                    "This will restore the roads to the initial OSM state for this job."
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Cancel", id=CANCEL_RESET_BUTTON_STREET_SELECTION_ID, color="secondary", outline=True
                        ),
                        dbc.Button("Reset", id=CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, color="danger"),
                    ]
                ),
            ],
            id=RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID,
            is_open=False,
            backdrop="static",
            keyboard=False,
        ),
    ]

    footer = progress_footer(
        prev=dbc.Button(
            [html.I(className="bi bi-arrow-left me-1"), "Previous"],
            id=STREET_SELECTION_PREV_BUTTON_STREET_SELECTION_ID,
            color="secondary",
            outline=True,
        ),
        next_=dbc.Button(
            [html.I(className="bi bi-check2-circle me-1"), "Finish"],
            id=STREET_SELECTION_NEXT_BUTTON_STREET_SELECTION_ID,
            color="primary",
            href=f"/job/{job_id}/routing-params",
            disabled=not bool(job_id),
        ),
    )

    below = dbc.Alert(
        id=ACTION_ALERT_ALERT_STREET_SELECTION_ID,
        children="",
        color="info",
        is_open=False,
        dismissable=True,
        className="mt-3",
    )

    # Persist selected tags across pages
    body.append(dcc.Store(id=TAGS_LAST_SELECTION_STORE_SHARED_ID, storage_type="session"))

    return page_layout(
        title="Street Selection",
        body=body,
        job_id=job_id,
        footer=footer,
        below=below,
        step_index=3,
    )
