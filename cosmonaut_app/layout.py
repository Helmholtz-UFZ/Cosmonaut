from dash import dcc, html
import dash_leaflet as dl
from config import osm_tags_mapping
from routes import app


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
                            html.Button("Nutzloser Knopf", id="btn", style={"margin-top": "10px"}),
                            href="https://i.gifer.com/7bTq.gif",
                            target="_blank"
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
