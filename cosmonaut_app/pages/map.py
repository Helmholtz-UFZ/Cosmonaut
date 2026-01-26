"""Landing page for starting a new job."""

from dash import html, register_page
from cosmonaut_app.layout import main_map, side_bar

register_page(
    __name__,
    path="/map",
    name="Map",
    title="COSMONAUT – Map",
    description="Start a new COSMONAUT job.",
)

# add some random text to the page
layout = html.Div(
    [
        main_map,
        side_bar,
    ],
    className="container",
    style={
        "height": "100vh",
        "display": "flex",
        "flexDirection": "column",
        "justifyContent": "center",
    },
)
