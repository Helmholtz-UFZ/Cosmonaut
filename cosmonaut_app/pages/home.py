"""Landing page for starting a new job."""

from dash import html, register_page
import dash_bootstrap_components as dbc
from cosmonaut_app.ui.page import progress_steps
from cosmonaut_app.constants.html_ids import START_JOB_BUTTON_HOME_ID

register_page(
    __name__,
    path="/",
    name="Home",
    title="COSMONAUT - Start",
    description="Landing Page of COSMONAUT.",
)


def layout():
    return html.Main(
        [
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.H4("Welcome", className="mb-0"),
                                        xs=12,
                                        md="auto",
                                    ),
                                ],
                                className="g-2 align-items-center",
                                justify="between",
                            ),
                            html.Div(
                                progress_steps(current=1, variant="home"),
                                className="mt-2",
                            ),
                        ]
                    ),
                    dbc.CardBody(
                        [
                            html.P(
                                "Create a new routing job and follow the steps to upload your data, select streets, and download navigation.",
                                className="text-muted mb-3",
                            ),
                            dbc.Button(
                                [
                                    html.I(className="bi bi-rocket-takeoff me-2"),
                                    "Create new job",
                                ],
                                id=START_JOB_BUTTON_HOME_ID,
                                color="primary",
                                size="lg",
                            ),
                            html.Div(
                                "Or load an existing job using the search bar in the navbar.",
                                className="text-muted small mt-2",
                            ),
                        ]
                    ),
                ],
                className="shadow-sm modern-card",
            ),
        ],
        role="main",
        tabIndex=0,
        className="p-3 p-md-4",
    )
