import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import dcc, html

from cosmonaut_app.config import osm_tags_mapping


def not_found_page():
    # Define the layout for the 404 Not Found page
    return html.Div(
        [
            html.H1("404 Not Found"),
            html.P("The page you are looking for does not exist."),
            dcc.Link(html.Button("Go back to the Home Page"), href="/"),
        ],
        style={"height": "100vh", "width": "100%"},
    )


def main_page_layout():
    return html.Div(
        [
            navbar,
            main_map,
            side_bar,
            html.Div(id="hidden-div", style={"display": "none"}),
            dcc.Store(id="current-stage", data=0),
            dcc.Store(id="job-loaded-flag", data=None),
            dcc.Store(id="email-store"),
            dcc.Store(id="epsg-store", data=None),
            dcc.Store(id="routing-complete"),
            dcc.Dropdown(
                id="tags-dropdown",
                options=[],
                value=None,
                disabled=True,
                style={"display": "none"},
            ),
            html.Div(id="upload-data-store", style={"display": "none"}),
            html.Div(id="dummy-output", style={"display": "none"}),
            html.Div(id="osm-file-path", style={"display": "none"}),
            html.Div(id="none", style={"display": "none"}),
        ],
        style={"height": "100vh", "width": "100%"},
    )


# Main Map
main_map = html.Div(
    dl.Map(
        [
            dl.LayersControl(
                [
                    dl.BaseLayer(
                        dl.TileLayer(),
                        name="OSM Standard",
                        checked=True,
                    ),
                    dl.Overlay(
                        dl.WMSTileLayer(
                            url="https://gdi-fs.ufz.de/geoserver/cosmic-routing/ows?service=WMS",  # noqa: E501
                            layers="20240410_8-col-4326_class-5",
                            styles="raster",
                            format="image/jpeg",
                            transparent=True,
                            attribution="WMS Layer",
                            crs="EPSG4326",
                            opacity=0.5,
                        ),
                        name="WMS Layer",
                        checked=False,
                        id="wms-layer",
                    ),
                ],
                id="lc",
            ),
            dl.FullScreenControl(),
            dl.LocateControl(locateOptions={"enableHighAccuracy": True}),
            dl.ScaleControl(position="bottomleft"),
            dl.EasyButton(
                icon="fa-edit", title="Remove selected road", id="remove-button"
            ),
            dl.GeoJSON(id="osm-geojson"),
            dl.GeoJSON(id="route-geojson"),
            dcc.Store(id="clicked-roads", data=[]),
            dcc.Store(id="routing-complete", data=False),
        ],
        center=[51.70, 11.20],
        zoom=10,
        style={"height": "100%"},
        id="map",
    ),
    id="main-map",
    style={"height": "calc(100% - 10vh)", "width": "calc(100% - 500px)"},
)

# Initial Sidebar for the Job Start
side_bar = dbc.Col(
    [
        dbc.Label(
            [
                html.H3(
                    "Welcome to the COSmic ray based soil MOisture prediction NAvigation Utility Tool."  # noqa: E501
                ),
                html.H4("Press the Button to start initializing the job."),
            ],
            id="welcome-label",
        ),
        dbc.Button(
            "Start Job",
            id="start-job",
            className="me-auto",
            size="lg",
        ),
        html.Div(id="stage-content"),
    ],
    id="offcanvas",
    style={
        "width": "500px",
        "backgroundColor": "#DBE2EF",
        "border": "2px solid #dee2e6",
        "position": "fixed",
        "top": "10vh",
        "right": 0,
        "bottom": 0,
        "padding": "2rem 1rem",
        "overflow": "auto",
    },
    className="responsive-sidebar",
)

# Search Bar
search_bar = dbc.Row(
    [
        dbc.Col(
            dbc.Input(
                type="search",
                placeholder="Job_ID",
                id="search",
            ),
            width=6,
        ),
        dbc.Col(
            dbc.Button(
                "Search",
                color="primary",
                id="search-button",
            ),
            width="auto",
        ),
    ],
    class_name="ml-auto flex-nowrap mt-2 mt-md-0",
    align="center",
)

navbar = dbc.Navbar(
    dbc.Container(
        [
            html.A(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Img(
                                src="/met/wg7/cosmonaut/static/sample_logo.svg",
                                height="50px",
                            ),
                        ),
                        dbc.Col(
                            dbc.NavbarBrand(
                                "COSMONAUT",
                                className="ml-2",
                                style={"fontSize": "6vh"},
                            ),
                        ),
                    ],
                    align="center",
                ),
                href="/met/wg7/cosmonaut",
                className="navbar-link",
            ),
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            dbc.Collapse(
                search_bar,
                id="navbar-collapse",
                navbar=True,
                is_open=False,
            ),
            html.Div(
                id="search-results",
                style={"color": "white"},
            ),
            dcc.Interval(
                id="redirect-interval", interval=3000, n_intervals=0, disabled=True
            ),
        ],
    ),
    color="dark",
    dark=True,
    style={"height": "10vh"},
)


def stage1(job_id):
    return (
        html.Div(
            [
                html.H2(f"Job ID: {job_id}"),
                dbc.Input(id="email-input", type="email", placeholder="Enter email"),
                dbc.FormFeedback("Please enter a valid email.", id="email-feedback"),
                dbc.Button(
                    "Previous Step",
                    id="prev-button",
                    className="me-auto",
                    size="lg",
                    disabled=True,
                ),
                dbc.Button(
                    "Next Step",
                    id="next-button",
                    className="me-auto",
                    size="lg",
                    disabled=True,
                ),
                dbc.Progress(
                    id="progress-bar",
                    label="1/3",
                    value=33,
                    style={"margin-top": "1rem"},
                ),
                html.Div(id="upload-data-dcc", style={"display": "none"}),
            ],
        ),
    )


def stage2(job_id):
    return (
        html.Div(
            [
                html.H2(f"Job ID: {job_id}"),
                html.H3("Upload"),
                dbc.Input(
                    id="epsg-input",
                    type="number",
                    placeholder="Please Enter a valid EPSG Code for your data.",
                    style={"margin-top": "1rem"},
                ),
                dbc.Form(
                    [
                        dcc.Upload(
                            id="upload-data-dcc",
                            accept=".csv,.txt",
                            children=html.Div(
                                [
                                    dbc.Button(
                                        "Click to select a file to upload.",
                                        # TODO FIXME the drag and drop does not work with the Form wrapper
                                        # "Drag and drop a file or click to select a file to upload.",
                                        color="primary",
                                        className="mt-2",
                                    )
                                ]
                            ),
                            multiple=False,
                        ),
                    ],
                    className="mt-3 mb-3",
                ),
                dbc.Button(
                    "Previous Step",
                    id="prev-button",
                    className="me-auto",
                    size="lg",
                    disabled=True,
                ),
                dbc.Button(
                    "Next Step",
                    id="next-button",
                    className="me-auto",
                    size="lg",
                    disabled=True,
                ),
                dbc.Progress(
                    id="progress-bar",
                    label="2/3",
                    value=67,
                    style={"margin-top": "1rem"},
                ),
                html.Div(id="output-data-upload"),
                html.Div(id="output-osm-query"),
                html.Div(id="plot-generation-status"),
                html.Div(id="output-minIO-status"),
                html.Div(id="file-path", style={"display": "none"}),
                dbc.Input(id="email-input", type="email", style={"display": "none"}),
            ],
        ),
    )


def stage3(job_id):
    return (
        html.Div(
            [
                html.H2(f"Job ID: {job_id}"),
                html.H4("Straßenauswahl"),
                dbc.Checklist(
                    id="tags-dropdown",
                    options=[
                        {"label": tag, "value": tag} for tag in osm_tags_mapping.keys()
                    ],
                    value=list(osm_tags_mapping.keys()),
                    inline=True,
                ),
                dbc.Button(
                    "Previous Step",
                    id="prev-button",
                    className="me-auto",
                    size="lg",
                    disabled=True,
                ),
                dbc.Button(
                    "Confirm Input",
                    id="confirm-button",
                    className="me-auto",
                    size="lg",
                ),
                dbc.Progress(
                    id="progress-bar",
                    label="3/3",
                    value=100,
                    style={"margin-top": "1rem"},
                ),
                dbc.Input(id="email-input", type="email", style={"display": "none"}),
                html.Div(id="upload-data-dcc", style={"display": "none"}),
            ],
        ),
    )


def stage4(job_id):
    confirm_side_bar = dbc.Col(
        [
            dbc.Label(
                [
                    html.H2(f"Job ID: {job_id}"),
                    html.H3(
                        "Your input has been confirmed. The route(s) are being computed."  # noqa: E501
                    ),
                    html.H4(
                        "Choose a Route on the map.", style={"color": "grey"}
                    ),  # TODO sollte erst nach kalkulation der Routen erscheinen
                    dbc.Button(
                        "Start Route",
                        id="start-route",
                        className="me-auto",
                        size="lg",
                    ),
                    dcc.Loading(
                        id="loading-qr-code",
                        type="default",
                        children=html.Img(
                            id="qr-code",
                            src="",
                            style={
                                "width": "100%",
                                "padding-top": "1rem",
                                "padding-bottom": "1rem",
                            },
                        ),
                    ),
                ],
                id="welcome-label",
            ),
            html.Div(id="stage-content"),
        ],
        id="offcanvas",
        style={
            "width": "500px",
            "backgroundColor": "#DBE2EF",
            "border": "2px solid #dee2e6",
            "position": "fixed",
            "top": "10vh",
            "right": 0,
            "bottom": 0,
            "padding": "2rem 1rem",
            "overflow": "auto",
        },
        className="responsive-sidebar",
    )

    return html.Div(
        [
            navbar,
            main_map,
            confirm_side_bar,
            html.Div(id="hidden-div", style={"display": "none"}),
            dcc.Store(id="current-stage", data=0),
            # dcc.Store(id="job-id", data=None),
            dcc.Store(id="job-loaded-flag", data=None),
            dcc.Store(id="email-store"),
            dcc.Store(id="epsg-store"),
            dcc.Dropdown(
                id="tags-dropdown",
                options=[],
                value=list(osm_tags_mapping.keys()),
                # disabled=True,
                style={"display": "none"},
            ),
            html.Div(id="upload-data-store", style={"display": "none"}),
            html.Div(id="dummy-output", style={"display": "none"}),
            html.Div(id="osm-file-path", style={"display": "none"}),
        ],
        style={"height": "100vh", "width": "100%"},
    )
