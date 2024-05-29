from dash import dcc, html, Input, Output, State
import dash_leaflet as dl
from cosmonaut_app.config import osm_tags_mapping
# from cosmonaut_app.flask_routes import app
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
            dl.EasyButton(icon="fa-globe", title="So easy", id="open-offcanvas"),
            # dl.Popup(id="popup", autoPan=False, closeOnClick=False),
            dl.EasyButton(
                icon="fa-globe", title="Remove selected road", id="remove-button"
            ),
            dl.GeoJSON(id="geojson"),
            dcc.Store(id="clicked-roads", data=[]),
        ],
        center=[51.70, 11.20],
        zoom=10,
        style={"height": "100%"},
        id="map",
    ),
    style={"height": "100vh"},
)

# Sidebar
side_bar = dbc.Offcanvas(
    [
        dbc.Label(
            [
                html.H2(
                    "COSmic ray based soil MOisture prediction NAvigation Utility Tool"
                ),
                html.H4("Upload a CSV file with coordinates to start routing."),
            ]
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H2("Upload"),
                        dcc.Upload(
                            id="upload-data",
                            accept=".csv",
                            children=html.Div(
                                [
                                    "Ziehen Sie eine Datei per Drag-and-Drop oder klicken Sie, um eine Datei zum Hochladen auszuwählen."
                                ]
                            ),
                            multiple=False,
                        ),
                        html.Div(id="output-data-upload"),
                        html.Div(id="output-osm-query"),
                        html.Div(id="file-path"),
                        html.Div(id="osm-file-path"),
                        html.Div(
                            [
                                html.H4("Straßenauswahl"),
                                dbc.Checklist(
                                    id="tags-dropdown",
                                    options=[
                                        {"label": tag, "value": tag}
                                        for tag in osm_tags_mapping.keys()
                                    ],
                                    value=list(osm_tags_mapping.keys()),
                                    inline=True,
                                ),
                            ],
                        ),
                        html.H3("QR-Code zum Downloaden der Route als GPX-Datei"),
                        html.Div(
                            [
                                html.Img(id="qr-code"),
                                dcc.Store(id="qr-code-data"),
                            ],
                        ),
                        html.Div(
                            "Die heruntergeladene GPX-Datei enthält die Route, welche mit OsmAnd oder einer anderen Navigations-App geöffnet werden kann."
                        ),
                    ],
                ),
                html.Div(
                    [
                        dcc.Link(
                            html.Button(
                                "Nutzloser Knopf",
                                id="btn",
                            ),
                            href="https://i.gifer.com/7bTq.gif",
                            target="_blank",
                        ),
                        html.Button(
                            "Test Routing Knopf",
                            id="btn-route",
                        ),
                    ],
                ),
            ],
        ),
        html.Div(id="plot-generation-status"),
    ],
    id="offcanvas",
    scrollable=True,
    placement="end",
    is_open=False,
    autoFocus=False,
    style={
        "width": "500px",
        "background-color": "#DBE2EF",
        "border": "2px solid #dee2e6",
    },
    backdrop="static",
    close_button=True,
)
