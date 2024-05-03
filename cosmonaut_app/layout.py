from dash import dcc, html
import dash_leaflet as dl
from config import osm_tags_mapping
from flask_routes import app


# Generate the layout of the app
app.layout = html.Div(
    [
        html.Div(
            [
                html.H1(
                    "COSmic ray based soil MOisture prediction NAvigation Utility Tool"
                )  # ,
                # html.H3("or short"),
                # html.H2("COSMONAUT"),
            ],
            style={"text-align": "center", "padding-bottom": "20px"},
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
                        html.H2("Dateiliste"),
                        html.Ul(id="file-list"),
                        html.Div(id="output-data-upload"),
                        html.Div(id="output-osm-query"),
                        html.Div(id="file-path", style={"display": "none"}),
                        html.Div(id="osm-file-path", style={"display": "none"}),
                        html.H3("QR-Code zum Downloaden der Route als GPX-Datei"),
                        html.Div(
                            [
                                html.Img(id="qr-code"),
                                dcc.Store(id="qr-code-data"),
                            ],
                            style={"padding": "20px"},
                        ),
                        html.Div(
                            "Die heruntergeladene GPX-Datei enthält die Route, welche mit OsmAnd oder einer anderen Navigations-App geöffnet werden kann."
                        ),
                    ],
                    style={"flex": "1 1 20%", "padding-right": "20px"},
                ),
                html.Div(
                    [
                        dl.Map(
                            [
                                dl.LayersControl(
                                    [
                                        dl.BaseLayer(
                                            dl.TileLayer(),
                                            name="OpenStreetMap",
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
                                                layers="20240410_8-col-4326_class-1",
                                                styles="raster",
                                                format="image/jpeg",
                                                transparent=True,
                                                attribution="WMS Layer",
                                                crs="EPSG4326",
                                                opacity=0.5,
                                            ),
                                            name="WMS Layer",
                                            checked=True,
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
                                dl.LocateControl(
                                    locateOptions={"enableHighAccuracy": True}
                                ),
                                dl.ScaleControl(position="bottomleft"),
                            ],
                            center=[51.70, 11.20],
                            zoom=10,
                            style={"height": "50vh", "border": "2px solid black"},
                            id="map",
                        ),
                        dcc.Link(
                            html.Button(
                                "Nutzloser Knopf",
                                id="btn",
                                style={"margin-top": "10px"},
                            ),
                            href="https://i.gifer.com/7bTq.gif",
                            target="_blank",
                        ),
                        html.Button(
                            "Test Routing Knopf",
                            id="btn-route",
                            style={"margin-top": "10px"},
                        ),
                    ],
                    style={"flex": "1 1 80%", "margin-top": "10px"},
                ),
            ],
            style={"display": "flex", "justify-content": "center"},
        ),
        html.Div(
            [
                html.H4("Straßenauswahl"),
                dcc.Dropdown(
                    id="tags-dropdown",
                    options=[
                        {"label": tag, "value": tag} for tag in osm_tags_mapping.keys()
                    ],
                    value=list(osm_tags_mapping.keys()),
                    multi=True,
                    style={"width": "50%", "margin": "0 auto"},
                ),
            ],
            style={"text-align": "center", "padding-top": "20px"},
        ),
        html.Div(id="plot-generation-status", style={"display": "none"}),
    ],
    style={"padding": "20px"},
)
