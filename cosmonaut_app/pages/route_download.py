"""Route & Download page: show route, QR code, and GPX download."""

from dash import html, register_page
import dash_bootstrap_components as dbc
from cosmonaut_app.ui.page import page_layout

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
            id="start-route",
            color="success",
            className="me-2",
            n_clicks=0,
        ),
        html.Div(id="route-qrcode"),
        html.Div(id="route-gpx-link"),
    ]
    return page_layout("Route & Download", body, job_id=job_id, step_index=5)
