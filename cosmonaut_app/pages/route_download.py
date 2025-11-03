"""Route & Download page: show route, QR code, and GPX download."""

from dash import html, register_page
import dash_bootstrap_components as dbc
from cosmonaut_app.ui.page import page_layout
from cosmonaut_app.constants.html_ids import (
    ROUTE_GPX_LINK_LINK_ROUTE_DOWNLOAD_ID,
    ROUTE_QRCODE_DIV_ROUTE_DOWNLOAD_ID,
    START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
)

register_page(
    __name__,
    path_template="/job/<job_id>/route-download",
    name="Route & Download",
    title="Route Download",
    description="View the calculated route and download the GPX file.",
    dynamic=True,
)


def layout(job_id=None, **kwargs):
    body = [
        html.P(
            "Bitte haben Sie Geduld, bis die Route berechnet ist.",
            style={"margin-bottom": "0.5rem", "font-size": "1.2rem"},
        ),
        html.P(
            "Wenn der 'Start Route'-Button gedrückt wird, erscheint ein QR-Code "
            "zum Download der GPX-Datei der finalen Route.",
            style={"margin-bottom": "1rem", "font-size": "1.2rem"},
        ),
        dbc.Button(
            "Start Route",
            id=START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID,
            color="success",
            className="me-2",
            n_clicks=0,
        ),
        html.Div(id=ROUTE_QRCODE_DIV_ROUTE_DOWNLOAD_ID),
        html.Div(id=ROUTE_GPX_LINK_LINK_ROUTE_DOWNLOAD_ID),
    ]
    return page_layout("Route & Download", body, job_id=job_id, step_index=5)
