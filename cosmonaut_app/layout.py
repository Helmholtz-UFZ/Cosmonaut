import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import dcc, html


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
    style={"height": "100%", "width": "100%"},
)

# Initial Sidebar for the Job Start
side_bar = dbc.Col(
    [
        html.Div(id="stage-content"),
    ],
    id="offcanvas",
    style={
        "width": "500px",
        "backgroundColor": "#DBE2EF",
        "border": "2px solid #dee2e6",
        # "position": "fixed",
        # "top": "10vh",
        # "right": 0,
        # "bottom": 0,
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
                                src="/static/sample_logo.svg",
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
                href="/",
                className="navbar-link",
            ),
            dbc.NavbarToggler(id="navbar-toggler", n_clicks=0),
            dbc.Collapse(
                search_bar,
                id="navbar-collapse",
                navbar=True,
                is_open=False,
            ),
            # Fixed-position container for toast notifications (does not affect layout)
            html.Div(
                id="search-results",
                style={
                    "position": "fixed",
                    "top": "1rem",
                    "right": "1rem",
                    "zIndex": 1100,
                    "maxWidth": "28rem",
                },
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
