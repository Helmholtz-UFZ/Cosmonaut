import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import dcc, html
from cosmonaut_app.constants.html_ids import (
    CLICKED_ROADS_STORE_SHARED_ID,
    CURRENT_STAGE_STORE_SHARED_ID,
    DUMMY_OUTPUT_DIV_SHARED_ID,
    EMAIL_STORE_SHARED_ID,
    EPSG_STORE_SHARED_ID,
    JOB_LOADED_FLAG_STORE_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MAIN_MAP_DIV_MAP_SHARED_ID,
    NAVBAR_COLLAPSE_NAV_SHARED_ID,
    NAVBAR_TOGGLER_NAV_SHARED_ID,
    NONE_DIV_SHARED_ID,
    OSM_FILE_PATH_STORE_SHARED_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    ROUTE_GEOJSON_LAYER_MAP_SHARED_ID,
    ROUTING_COMPLETE_STORE_SHARED_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    UPLOAD_DATA_STORE_SHARED_ID,
)


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
            dcc.Store(id=CURRENT_STAGE_STORE_SHARED_ID, data=0),
            dcc.Store(id=JOB_LOADED_FLAG_STORE_SHARED_ID, data=None),
            dcc.Store(id=EMAIL_STORE_SHARED_ID),
            dcc.Store(id=EPSG_STORE_SHARED_ID, data=None),
            dcc.Dropdown(
                id=TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
                options=[],
                value=None,
                disabled=True,
                style={"display": "none"},
            ),
            html.Div(id=UPLOAD_DATA_STORE_SHARED_ID, style={"display": "none"}),
            html.Div(id=DUMMY_OUTPUT_DIV_SHARED_ID, style={"display": "none"}),
            html.Div(id=OSM_FILE_PATH_STORE_SHARED_ID, style={"display": "none"}),
            html.Div(id=NONE_DIV_SHARED_ID, style={"display": "none"}),
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
                    ),
                ],
            ),
            dl.FullScreenControl(),
            dl.LocateControl(locateOptions={"enableHighAccuracy": True}),
            dl.ScaleControl(position="bottomleft"),
            dl.GeoJSON(id=OSM_GEOJSON_LAYER_MAP_SHARED_ID),
            dl.GeoJSON(id=ROUTE_GEOJSON_LAYER_MAP_SHARED_ID),
            dcc.Store(id=CLICKED_ROADS_STORE_SHARED_ID, data=[]),
            dcc.Store(id=ROUTING_COMPLETE_STORE_SHARED_ID, data=False),
        ],
        id=MAIN_MAP_COMPONENT_MAP_SHARED_ID,
        center=[51.70, 11.20],
        zoom=10,
        style={"height": "100%"},
    ),
    id=MAIN_MAP_DIV_MAP_SHARED_ID,
    style={"height": "100%", "width": "100%"},
)

# Initial Sidebar for the Job Start
side_bar = dbc.Col(
    [
        html.Div(),
    ],
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
            dbc.NavbarToggler(id=NAVBAR_TOGGLER_NAV_SHARED_ID, n_clicks=0),
            dbc.Collapse(
                search_bar,
                id=NAVBAR_COLLAPSE_NAV_SHARED_ID,
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
