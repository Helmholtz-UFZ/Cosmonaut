import logging
import os

import dash
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import ctx, dcc, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash_extensions.javascript import _default_name_space, assign

from cosmonaut_app.constants.general import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_RUNNING,
    OSM_TAGS_MAPPING,
)
from cosmonaut_app.constants.html_ids import (
    CURRENT_JOB_ID_MAP_STORE_ID,
    JOB_ID_STORE_SHARED_ID,
    LOADING_OVERLAY_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MAP_INIT_INTERVAL_ID,
    MEMBERSHIP_TILE_LAYER_MAP_ID,
    NAVBAR_COLLAPSE_NAV_SHARED_ID,
    NAVBAR_TOGGLER_NAV_SHARED_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    RESET_BUTTON_SHARED_ID,
    RESET_MODAL_CANCEL_BUTTON_SHARED_ID,
    RESET_MODAL_CONFIRM_BUTTON_SHARED_ID,
    RESET_MODAL_SHARED_ID,
    ROUTE_POLYLINE_LAYER_MAP_ID,
    SEARCH_BUTTON_NAV_SHARED_ID,
    SEARCH_INPUT_NAV_SHARED_ID,
    SEARCH_RESULTS_DIV_NAV_SHARED_ID,
    URL_SHARED_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.error_handling import JobNotFound, error_modal
from cosmonaut_app.map_utils import get_tile_url
from cosmonaut_app.street_selector import StreetSelector

# ============================================================================
# Helper Functions and Constants
# ============================================================================

# Configure assign() to write to cosmonaut_app/assets/ instead of root assets/
_assets_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_original_dump = _default_name_space.dump
_default_name_space.dump = lambda assets_folder=_assets_folder: _original_dump(
    assets_folder
)

# Define a JavaScript function for styling the GeoJSON features
style_handle = assign(
    """
function(feature, context){
    const {selected, zoom} = context.hideout;
    // Increase base weight to make lines easier to click. Keep adaptive thinning on zoom in.
    const lineWeight = zoom ? Math.max(3, 18 / zoom) : 4; // at zoom=10 -> ~3
    const color = selected.includes(feature.id) ? 'yellow' : 'red';
    return {color: color, weight: lineWeight, opacity: 0.85};
}
"""
)

# Separate hover style with slight highlight and thicker stroke for better affordance
hover_style_handle = assign(
    """
function(feature, context){
    const {selected, zoom} = context.hideout;
    const lineWeight = zoom ? Math.max(4, 22 / zoom) : 5;
    const color = selected.includes(feature.id) ? 'orange' : '#ff6666';
    return {color: color, weight: lineWeight, opacity: 1.0};
}
"""
)

click_handler = assign("""function(e, ctx) {
    const id = e.layer.feature.id;
    const selected = [...(ctx.hideout.selected || [])];
    const idx = selected.indexOf(id);
    if (idx > -1) {
        selected.splice(idx, 1);
    } else {
        selected.push(id);
    }
    ctx.setProps({hideout: {...ctx.hideout, selected: selected}});
}""")


# ============================================================================
# Layout Components
# ============================================================================

osm_layer = dl.TileLayer(
    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution="© OpenStreetMap contributors",
)
default_map_layers = [osm_layer, dl.FullScreenControl()]
steps_jobs = {
    "user_info": ["Information", "Provide user information"],
    "data_upload": ["Upload", "Upload classification data"],
    "street_selection": ["Selection", "Select streets for routing"],
    "routing_params": ["Parameters", "Set routing parameters"],
    "route_computation": ["Computation", "Monitor routing computation"],
    "route_download": ["Download", "Download the computed route"],
}


loading_overlay = dbc.Modal(
    dbc.ModalBody(
        [dbc.Spinner(size="lg"), html.H4("Loading...", className="text-center mt-3")],
        className="text-center",
    ),
    id=LOADING_OVERLAY_SHARED_ID,
    is_open=False,
    backdrop="static",  # Prevents closing by clicking outside
    keyboard=False,  # Prevents closing with escape key
    centered=True,
    size="sm",
)


def create_reset_banner(job_id: str, status: str) -> dbc.Alert:
    """Create status banner with reset button for non-PENDING jobs.

    Args:
        job_id: Job ID for display
        status: Current job status

    Returns:
        dbc.Alert component with status info and reset button
    """
    # Color mapping
    color_map = {
        JOB_STATUS_RUNNING: "primary",
        JOB_STATUS_COMPLETED: "success",
        JOB_STATUS_FAILED: "danger",
    }

    # Status message
    message_map = {
        JOB_STATUS_RUNNING: "This job is currently running. Reset to cancel and restart.",
        JOB_STATUS_COMPLETED: "This job has been completed. Reset to clear results and restart.",
        JOB_STATUS_FAILED: "This job has failed. Reset to clear results and try again.",
    }

    return dbc.Alert(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Span(message_map[status]),
                        width="auto",
                        className="d-flex align-items-center",
                    ),
                    dbc.Col(
                        dbc.Button(
                            [
                                html.I(className="bi bi-arrow-counterclockwise me-1"),
                                "Reset Job",
                            ],
                            id=RESET_BUTTON_SHARED_ID,
                            color="warning",
                            size="sm",
                        ),
                        width="auto",
                    ),
                ],
                className="align-items-center justify-content-between",
            )
        ],
        color=color_map.get(status, "secondary"),
        className="mb-3",
    )


def create_reset_modal() -> dbc.Modal:
    """Create confirmation modal for job reset.

    Returns:
        dbc.Modal component with confirmation dialog
    """
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Reset Job?")),
            dbc.ModalBody(
                [
                    html.P(
                        "This will delete all computation results (logs, routes, GPX files) "
                        "and reset the job status to PENDING. You will need to restart the "
                        "computation."
                    ),
                    html.P(
                        "Your uploaded data and selected streets will be preserved.",
                        className="text-muted mb-0",
                    ),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel",
                        id=RESET_MODAL_CANCEL_BUTTON_SHARED_ID,
                        color="secondary",
                        outline=True,
                    ),
                    dbc.Button(
                        [
                            html.I(className="bi bi-exclamation-triangle me-1"),
                            "Reset Job",
                        ],
                        id=RESET_MODAL_CONFIRM_BUTTON_SHARED_ID,
                        color="danger",
                    ),
                ]
            ),
        ],
        id=RESET_MODAL_SHARED_ID,
        is_open=False,
        backdrop="static",
        keyboard=False,
        centered=True,
    )


def create_navbar():
    """Create a navbar layout."""
    return dbc.Navbar(
        className="navbar navbar-expand-lg sticky-top navbar-dark bg-primary",
        children=dbc.Container(
            [
                dbc.NavbarBrand(
                    href=dash.page_registry["pages.home"]["relative_path"],
                    children=[
                        html.Img(
                            src="/static/sample_logo.svg",
                            width="30",
                            height="30",
                            className="d-inline-block align-text-top",
                            alt="Cosmopolitan Icon",
                        ),
                        " COSMONAUT",
                    ],
                ),
                dbc.NavbarToggler(id=NAVBAR_TOGGLER_NAV_SHARED_ID, n_clicks=0),
                dbc.Collapse(
                    dbc.Nav(
                        className="navbar-nav me-auto mb-2 mb-lg-0",
                        children=[
                            dbc.NavItem(
                                dbc.NavLink(
                                    [
                                        html.I(className="bi bi-book me-1"),
                                        "Documentation",
                                    ],
                                    href=dash.page_registry["pages.documentation"][
                                        "relative_path"
                                    ],
                                )
                            ),
                            dbc.NavItem(
                                dbc.NavLink(
                                    [
                                        html.I(className="bi bi-journal-text me-1"),
                                        "Logs",
                                    ],
                                    href=dash.page_registry["pages.logs"][
                                        "relative_path"
                                    ],
                                )
                            ),
                            dbc.NavItem(
                                dbc.NavLink(
                                    [
                                        html.I(className="bi bi-cpu me-1"),
                                        "Worker manager",
                                    ],
                                    href=dash.page_registry["pages.worker_management"][
                                        "relative_path"
                                    ],
                                )
                            ),
                            dbc.NavItem(
                                dbc.NavLink(
                                    [
                                        html.I(className="bi bi-list-task me-1"),
                                        "Job manager",
                                    ],
                                    href=dash.page_registry["pages.job_manager"][
                                        "relative_path"
                                    ],
                                )
                            ),
                            dbc.NavItem(
                                search_bar,
                            ),
                        ],
                    ),
                    id=NAVBAR_COLLAPSE_NAV_SHARED_ID,
                    navbar=True,
                    is_open=False,
                ),
                # Fixed-position container for toast notifications (does not affect layout)
                html.Div(
                    id=SEARCH_RESULTS_DIV_NAV_SHARED_ID,
                    style={
                        "position": "fixed",
                        "top": "1rem",
                        "right": "1rem",
                        "zIndex": 1100,
                        "maxWidth": "28rem",
                    },
                ),
            ],
        ),
    )


def build_global_map():
    """Build the global persistent map with empty layer slots.

    Layers are populated by register_map_callbacks after Leaflet has initialised.
    The dcc.Interval in app_layout() fires 300 ms after mount — by which point the
    Leaflet layer objects exist and can receive prop updates.
    """
    layers_control = dl.LayersControl(
        [
            dl.Overlay(
                dl.TileLayer(id=MEMBERSHIP_TILE_LAYER_MAP_ID, url="", opacity=0.7),
                name="Membership",
                checked=True,
            ),
            dl.Overlay(
                dl.GeoJSON(
                    id=OSM_GEOJSON_LAYER_MAP_SHARED_ID,
                    data={"type": "FeatureCollection", "features": []},
                    options={"style": style_handle},
                    hoverStyle=hover_style_handle,
                    eventHandlers=dict(click=click_handler),
                    hideout=dict(selected=[], zoom=10),
                ),
                name="Streets",
                checked=True,
            ),
            dl.Overlay(
                dl.GeoJSON(
                    id=ROUTE_POLYLINE_LAYER_MAP_ID,
                    data={"type": "FeatureCollection", "features": []},
                    options={
                        "style": {"color": "#1a73e8", "weight": 4, "opacity": 0.8}
                    },
                ),
                name="Route",
                checked=True,
            ),
        ],
        position="topright",
    )
    return dl.Map(
        [osm_layer, dl.FullScreenControl(), layers_control],
        id=MAIN_MAP_COMPONENT_MAP_SHARED_ID,
        center=[51.70, 11.20],
        zoom=10,
        style={"height": "100%"},
    )


def app_layout():
    """Create the main page layout with navbar and content."""
    return html.Div(
        className="d-flex flex-column min-vh-100 bg-light",
        children=[
            dcc.Store(id=CURRENT_JOB_ID_MAP_STORE_ID, data=None),
            dcc.Interval(id=MAP_INIT_INTERVAL_ID, interval=1000, max_intervals=1),
            loading_overlay,
            error_modal,
            create_navbar(),
            html.Div(
                className="d-flex flex-grow-1 app-panels overflow-hidden",
                children=[
                    html.Div(build_global_map(), className="map-panel col-7 p-0"),
                    html.Div(
                        dash.page_container,
                        className="content-panel col-5 p-0 d-flex flex-column",
                    ),
                ],
            ),
        ],
    )


def page_container_fullscreen_layout(content):
    """Create a page container with a fullscreen layout."""
    return html.Main(
        className="d-flex flex-column flex-grow-1 bg-white p-0 m-0", children=content
    )


def page_container_column_layout(content):
    """Create a page container with a single column layout."""
    # Content layout
    class_names_content = "col-md-11 col-lg-10 col-xl-9 bg-white border border-dark rounded p-0 mb-4 mt-2 d-flex flex-column"  # noqa
    page = html.Main(
        dbc.Row(
            dbc.Col(
                className=class_names_content,
                children=content,
            ),
            className="flex-grow-1 d-flex justify-content-center",
        ),
        className="d-flex flex-column flex-grow-1 no-map-page",
    )
    return page


def create_card_input(
    card_body, card_footer=None, name_step=None, title=None, job_id=None
):
    """Create a modern card input layout with optional progress steps."""
    if name_step is not None:
        if job_id is None:
            raise ValueError("job_id must be provided when name_step is used.")
        title = f"{steps_jobs[name_step][1]}({job_id})"

    if title is None:
        raise ValueError("Either title or name_step must be provided.")

    card_header = [html.H3(title)]

    if name_step is not None:
        card_header.append(steps_tab(name_step))

    card_content = [
        dbc.CardHeader(card_header),
        dbc.CardBody(card_body),
    ]

    if card_footer:
        card_content.append(card_footer)

    return dbc.Card(
        card_content,
        className="shadow-sm m-3 me-4",
    )


def build_url_step(step, job_id):
    base_path = dash.page_registry[f"pages.{step}"]["path_template"]
    return base_path.replace("<job_id>", job_id)


def create_header(title, subtitle, bg_color="bg-info", id="", rounded=True):
    """Create a header layout."""
    className = f"{bg_color} rounded-top py-2" if rounded else f"{bg_color} py-2"
    layout = html.Div(
        className=className,
        children=[
            html.H2(title, className="text-center", id=f"{id}-title"),  # nocheck
            (
                html.H3(
                    subtitle,
                    className="text-center",
                    id=f"{id}-subtitle",  # nocheck
                )
                if subtitle != ""
                else None
            ),
        ],
        id=id,
    )

    return layout


def progress_footer(
    prev_id=None,
    prev_url=None,
    prev_disabled=False,
    next_url=None,
    next_id=None,
    next_disabled=False,
):
    """Create a footer with Previous and Next buttons for navigation between steps."""

    args_prev = [html.I(className="bi bi-arrow-left-circle me-1"), "Previous"]
    kwargs_prev = dict(color="primary", disabled=prev_disabled)
    if prev_id is None and prev_url is None:
        prev_button = html.Span()
    elif prev_url is not None:
        if prev_id is not None:
            kwargs_prev["id"] = prev_id
        prev_button = dcc.Link(dbc.Button(args_prev, **kwargs_prev), href=prev_url)
    else:
        kwargs_prev["id"] = prev_id
        prev_button = dbc.Button(args_prev, **kwargs_prev)

    args_next = [html.I(className="bi bi-arrow-right-circle me-1"), "Next"]
    kwargs_next = dict(color="primary", disabled=next_disabled)
    if next_id is None and next_url is None:
        next_button = html.Span()
    elif next_url is not None:
        if next_id is not None:
            kwargs_next["id"] = next_id
        next_button = dcc.Link(dbc.Button(args_next, **kwargs_next), href=next_url)
    else:
        kwargs_next["id"] = next_id
        next_button = dbc.Button(args_next, **kwargs_next)

    actions = html.Div(
        [prev_button, next_button],
        className="footer-actions d-flex gap-2 justify-content-end align-items-center flex-wrap",
    )
    return dbc.CardFooter(actions)


def steps_tab(name_step):
    """Create a progress steps component for the job steps."""
    # TODO dynamic enabling based on job progress
    list_tabs = []
    for step_name, step_info in steps_jobs.items():
        list_tabs.append(
            dbc.Tab(
                label=step_info[0],
                tab_id=step_name,  # nocheck
                disabled=True,
            )
        )

    return dbc.Tabs(
        list_tabs,
        active_tab=name_step,
    )


# Search Bar
search_bar = dbc.Row(
    [
        dbc.Col(
            dbc.Input(
                type="search",
                placeholder="Job_ID",
                id=SEARCH_INPUT_NAV_SHARED_ID,
            ),
            width=6,
        ),
        dbc.Col(
            dbc.Button(
                [
                    html.I(className="bi bi-search me-1"),
                    "Search",
                ],
                color="primary",
                id=SEARCH_BUTTON_NAV_SHARED_ID,
            ),
            width="auto",
        ),
    ],
    class_name="ml-auto flex-nowrap mt-2 mt-md-0",
    align="center",
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

# ============================================================================
# Callback Registration Functions
# ============================================================================


def register_navbar_callbacks(app):
    """Register callbacks for the navbar."""

    @app.callback(
        Output(SEARCH_RESULTS_DIV_NAV_SHARED_ID, "children"),
        Output(JOB_ID_STORE_SHARED_ID, "data", allow_duplicate=True),
        Output(URL_SHARED_ID, "pathname", allow_duplicate=True),
        Input(SEARCH_BUTTON_NAV_SHARED_ID, "n_clicks"),
        State(SEARCH_INPUT_NAV_SHARED_ID, "value"),
        prevent_initial_call=True,
    )
    def search_job_id(n_clicks, job_id):
        if n_clicks is None:
            raise PreventUpdate

        if DataBaseManager.check_existence(job_id):
            CosmonautJob(job_id=job_id)

            return (
                dbc.Toast(
                    [html.Div(f"Job {job_id} found and loaded successfully.")],
                    header="Job loaded",
                    icon="success",
                    is_open=True,
                    duration=3000,
                    dismissable=True,
                    style={
                        "maxWidth": "26rem",
                        "wordWrap": "break-word",
                        "whiteSpace": "normal",
                    },
                ),
                job_id,
                f"/job/{job_id}/user-info",
            )
        else:
            return (
                dbc.Toast(
                    [html.Div(f"Job {job_id} not found")],
                    header="Not found",
                    icon="danger",
                    is_open=True,
                    duration=3000,
                    dismissable=True,
                    style={
                        "maxWidth": "26rem",
                        "wordWrap": "break-word",
                        "whiteSpace": "normal",
                    },
                ),
                no_update,
                no_update,
            )

    @app.callback(
        Output(NAVBAR_COLLAPSE_NAV_SHARED_ID, "is_open"),
        [Input(NAVBAR_TOGGLER_NAV_SHARED_ID, "n_clicks")],
        [State(NAVBAR_COLLAPSE_NAV_SHARED_ID, "is_open")],
    )
    def toggle_navbar_collapse(n, is_open):
        if n:
            return not is_open
        return is_open


def register_reset_callbacks(app):
    """Register callbacks for job reset functionality."""

    @app.callback(
        Output(RESET_MODAL_SHARED_ID, "is_open", allow_duplicate=True),
        Input(RESET_BUTTON_SHARED_ID, "n_clicks"),
        Input(RESET_MODAL_CANCEL_BUTTON_SHARED_ID, "n_clicks"),
        Input(RESET_MODAL_CONFIRM_BUTTON_SHARED_ID, "n_clicks"),
        State(RESET_MODAL_SHARED_ID, "is_open"),
        prevent_initial_call=True,
    )
    def toggle_reset_modal(n_open, n_cancel, n_confirm, is_open):
        """Toggle reset confirmation modal."""
        triggered_id = ctx.triggered_id

        if triggered_id == RESET_BUTTON_SHARED_ID:
            return True  # Open modal
        elif triggered_id in (
            RESET_MODAL_CANCEL_BUTTON_SHARED_ID,
            RESET_MODAL_CONFIRM_BUTTON_SHARED_ID,
        ):
            return False  # Close modal

        return is_open

    @app.callback(
        Output(URL_SHARED_ID, "pathname", allow_duplicate=True),
        Input(RESET_MODAL_CONFIRM_BUTTON_SHARED_ID, "n_clicks"),
        State(URL_SHARED_ID, "pathname"),
        prevent_initial_call=True,
    )
    def perform_reset(n_clicks, pathname):
        """Perform job reset and reload page."""
        if n_clicks is None:
            raise PreventUpdate

        # Extract job_id from pathname
        # Expected format: /job/{job_id}/{page_name}
        path_parts = pathname.split("/")
        if len(path_parts) >= 3 and path_parts[1] == "job":
            job_id = path_parts[2]
        else:
            logging.error(f"Could not extract job_id from pathname: {pathname}")
            raise PreventUpdate

        # Load job and reset
        try:
            job = CosmonautJob(job_id=job_id)
            job.reset()
            logging.info(f"Job {job_id} reset successfully from {pathname}")
        except Exception as e:
            logging.error(f"Failed to reset job {job_id}: {e}")
            raise PreventUpdate

        # Return same pathname to reload page with new state
        return pathname


def register_map_callbacks(app):
    """Register the global map layer callback.

    Populates all three map layers (membership tile, streets, route) and
    repositions the viewport when the job changes.

    Triggered by URL_SHARED_ID on every SPA pathname change.
    """

    @app.callback(
        Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport", allow_duplicate=True),
        Output(MEMBERSHIP_TILE_LAYER_MAP_ID, "url", allow_duplicate=True),
        Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
        Output(ROUTE_POLYLINE_LAYER_MAP_ID, "data"),
        Output(CURRENT_JOB_ID_MAP_STORE_ID, "data"),
        Input(URL_SHARED_ID, "pathname"),
        State(CURRENT_JOB_ID_MAP_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_map_layers(pathname, prev_job_id):
        logging.info(f"Map update triggered by {ctx.triggered_id}: {pathname}")
        empty_fc = {"type": "FeatureCollection", "features": []}
        parts = pathname.split("/")
        if len(parts) < 3 or parts[1] != "job":
            logging.info("Not a job page, returning empty")
            return no_update, "", empty_fc, empty_fc, None

        job_id = parts[2]
        try:
            job = CosmonautJob(job_id=job_id)
        except JobNotFound:
            logging.info(f"Job {job_id} not found, returning empty")
            return no_update, "", empty_fc, empty_fc, None

        # Only recentre the map when the job changes
        if job_id != prev_job_id:
            viewport = {
                "center": job.model.membership_upload["center"],
                "zoom": job.model.membership_upload["zoom"],
                "transition": "flyTo",
            }
        else:
            viewport = no_update

        tile_url = get_tile_url(job_id, job.working_dir)
        streets_fc = StreetSelector(job).initial_fc(list(OSM_TAGS_MAPPING.keys()))
        raw_positions = job.get_route_polyline() or []
        route_fc = {"type": "FeatureCollection", "features": []}
        if raw_positions:
            route_fc["features"] = [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[lon, lat] for lat, lon in raw_positions],
                    },
                    "properties": {},
                }
            ]
        logging.info(
            f"Returning tile_url={tile_url!r}, streets={len(streets_fc['features'])}, route_pts={len(raw_positions)}"
        )
        return viewport, tile_url, streets_fc, route_fc, job_id
