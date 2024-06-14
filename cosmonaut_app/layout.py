from dash import dcc, html, Input, Output, State
import dash_leaflet as dl
from cosmonaut_app.config import osm_tags_mapping
import dash_bootstrap_components as dbc

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
                        dl.LayerGroup(),
                        name="points",
                        checked=False,
                        id="points",
                    ),
                    dl.Overlay(
                        dl.WMSTileLayer(
                            url="https://gdi-fs.ufz.de/geoserver/cosmic-routing/ows?service=WMS",
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
                    dl.Overlay(
                        dl.LayerGroup(id="route-layer"),
                        name="Route Layer",
                        checked=True,
                        id="route",
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
            dl.GeoJSON(id="geojson"),
            dcc.Store(id="clicked-roads", data=[]),
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
                    "Welcome to the COSmic ray based soil MOisture prediction NAvigation Utility Tool."
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
        dbc.Progress(id="progress-bar", label="0%", value=0),
    ],
    id="offcanvas",
    style={
        "width": "500px",
        "background-color": "#DBE2EF",
        "border": "2px solid #dee2e6",
        "position": "fixed",
        "top": "10vh",
        "right": 0,
        "bottom": 0,
        "padding": "2rem 1rem",
        "overflow-y": "auto",
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
                            html.Img(src="/static/sample_logo.svg", height="50px"),
                        ),
                        dbc.Col(
                            dbc.NavbarBrand(
                                "COSMONAUT",
                                className="ml-2",
                                style={"font-size": "6vh"},
                            ),
                        ),
                    ],
                    align="center",
                ),
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
        ],
    ),
    color="dark",
    dark=True,
    style={"height": "10vh"},
)
