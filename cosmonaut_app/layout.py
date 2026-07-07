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
)
from cosmonaut_app.constants.html_ids import (
    CURRENT_JOB_ID_MAP_STORE_ID,
    JOB_ID_KICKER_CODE_SHARED_ID,
    LOADING_OVERLAY_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MAP_LEGEND_COLLAPSE_SHARED_ID,
    MAP_LEGEND_TOGGLE_BUTTON_SHARED_ID,
    MAP_INIT_INTERVAL_SHARED_ID,
    MEMBERSHIP_TILE_LAYER_MAP_ID,
    NAVBAR_COLLAPSE_NAV_SHARED_ID,
    NAVBAR_TOGGLER_NAV_SHARED_ID,
    NEW_JOB_LINK_NAV_SHARED_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    RESET_BUTTON_SHARED_ID,
    RESET_MODAL_CANCEL_BUTTON_SHARED_ID,
    RESET_MODAL_CONFIRM_BUTTON_SHARED_ID,
    RESET_MODAL_SHARED_ID,
    ROUTE_CASING_LAYER_MAP_ID,
    ROUTE_DIRECTION_DECORATOR_MAP_ID,
    ROUTE_ENDPOINTS_GROUP_MAP_ID,
    ROUTE_POLYLINE_LAYER_MAP_ID,
    STREETS_REFRESH_TRIGGER_STORE_SHARED_ID,
    URL_SHARED_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.error_handling import JobNotFound, error_modal
from cosmonaut_app.map_utils import get_tile_url
from cosmonaut_app.street_selector import StreetSelector

log = logging.getLogger(__name__)

# ============================================================================
# Helper Functions and Constants
# ============================================================================

# Configure assign() to write to cosmonaut_app/assets/ instead of root assets/
_assets_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_original_dump = _default_name_space.dump
_default_name_space.dump = lambda assets_folder=_assets_folder: _original_dump(
    assets_folder
)

# Map layer colors — single source of truth for the clientside style handlers,
# the route layer styles and the map legend below.
STREET_COLOR = "#d32f2f"  # in-network roads
STREET_SELECTED_COLOR = "#f9a825"  # roads marked by click (pending removal)
STREET_HOVER_COLOR = "#ff6666"
STREET_SELECTED_HOVER_COLOR = "#ffb300"
# Deep violet over a white casing: nothing else on the base maps (incl.
# satellite) or in the network uses violet, it stays distinguishable from the
# red network under red-, green- AND blue-deficient color vision (magenta-
# leaning hues collapse toward red under tritanopia), and it is calmer than
# the magenta tried first (user feedback: too garish). 8:1 contrast on the
# white casing.
ROUTE_COLOR = "#5e35b1"
ROUTE_CASING_COLOR = "#ffffff"

# Define a JavaScript function for styling the GeoJSON features.
# f-string: the color constants above are baked into the JS source (doubled
# braces are literal braces in the emitted JS).
# Weights are constants: an earlier zoom-adaptive formula read hideout.zoom,
# but that value was never updated after map creation (always 10), so it
# always evaluated to these numbers. On non-editing pages (dimmed) the network
# is fainter so the route stays dominant, but keeps the full weight —
# weight 2 / opacity 0.3 proved too faint over the membership overlay.
# Marked roads get a dash pattern on top of the amber color: red vs amber
# hue separation collapses under red-/green-deficient vision, so the dash is
# the color-independent second cue.
style_handle = assign(
    f"""
function(feature, context){{
    const {{selected, dimmed}} = context.hideout;
    const isMarked = selected.includes(feature.id);
    const color = isMarked ? '{STREET_SELECTED_COLOR}' : '{STREET_COLOR}';
    const opacity = dimmed ? 0.6 : 0.85;
    return {{color: color, weight: 3, opacity: opacity,
             dashArray: isMarked ? '6, 4' : null}};
}}
"""
)

# Hover: thicker stroke as the primary (color-independent) affordance — but
# only on the street-selection page. On dimmed pages streets are not
# interactive (click_handler guards on dimmed), so hover shows no change.
hover_style_handle = assign(
    f"""
function(feature, context){{
    const {{selected, dimmed}} = context.hideout;
    const isMarked = selected.includes(feature.id);
    if (dimmed) {{
        const color = isMarked ? '{STREET_SELECTED_COLOR}' : '{STREET_COLOR}';
        return {{color: color, weight: 3, opacity: 0.6,
                 dashArray: isMarked ? '6, 4' : null}};
    }}
    const color = isMarked ? '{STREET_SELECTED_HOVER_COLOR}' : '{STREET_HOVER_COLOR}';
    return {{color: color, weight: 4, opacity: 1.0,
             dashArray: isMarked ? '6, 4' : null}};
}}
"""
)

click_handler = assign("""function(e, ctx) {
    // Streets are only clickable on the street-selection page. Without this
    // guard, clicks on any other page would silently mark roads that
    // "Remove clicked roads" later deletes. Guard on the URL, NOT on
    // ctx.hideout.dimmed: event handlers keep a snapshot of hideout from
    // binding time and never see server-side hideout updates (verified —
    // the style functions DO read hideout dynamically, events don't).
    if (!window.location.pathname.includes('street-selection')) { return; }
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

# Selectable base maps (radio buttons in the LayersControl). All three are
# free, keyless tile services; attribution per provider terms.
def _base_layers():
    return [
        dl.BaseLayer(
            dl.TileLayer(
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                attribution="© OpenStreetMap contributors",
            ),
            name="OpenStreetMap",
            checked=True,
        ),
        dl.BaseLayer(
            dl.TileLayer(
                url="https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attribution=(
                    "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, "
                    "and the GIS User Community"
                ),
                maxZoom=19,
            ),
            name="Satellite",
            checked=False,
        ),
        dl.BaseLayer(
            dl.TileLayer(
                url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                attribution=(
                    "© OpenStreetMap contributors, SRTM | "
                    "Style: © OpenTopoMap (CC-BY-SA)"
                ),
                # OpenTopoMap serves tiles up to z17 only
                maxZoom=17,
            ),
            name="Terrain",
            checked=False,
        ),
    ]
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
        color=color_map[status],
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
                            alt="COSMONAUT Icon",
                        ),
                        " COSMONAUT",
                    ],
                ),
                dbc.NavbarToggler(id=NAVBAR_TOGGLER_NAV_SHARED_ID, n_clicks=0),
                dbc.Collapse(
                    # Item order mirrors COSMOPOLITAN's navbar (New Job,
                    # Documentation, Job, Worker, Logs) for cross-app consistency.
                    dbc.Nav(
                        className="navbar-nav me-auto mb-2 mb-lg-0",
                        children=[
                            dbc.NavItem(
                                dbc.NavLink(
                                    [
                                        html.I(className="bi bi-plus-circle me-1"),
                                        "New job",
                                    ],
                                    id=NEW_JOB_LINK_NAV_SHARED_ID,
                                    n_clicks=0,
                                    # cursor: no Bootstrap utility class in v5.2;
                                    # this NavLink has no href — it creates the
                                    # job via callback like the home-page button.
                                    style={"cursor": "pointer"},
                                )
                            ),
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
                                        html.I(className="bi bi-list-task me-1"),
                                        "Job manager",
                                    ],
                                    href=dash.page_registry["pages.job_manager"][
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
                                        html.I(className="bi bi-journal-text me-1"),
                                        "Logs",
                                    ],
                                    href=dash.page_registry["pages.logs"][
                                        "relative_path"
                                    ],
                                )
                            ),
                        ],
                    ),
                    id=NAVBAR_COLLAPSE_NAV_SHARED_ID,
                    navbar=True,
                    is_open=False,
                ),
            ],
        ),
    )


def route_endpoint_markers(positions):
    """Start/end CircleMarkers for the route ([] when there is no route).

    Start: violet fill / white ring. End: white fill / violet ring. Shared by
    ``update_map_layers`` and the reverse-direction toggle on Route Download.
    """
    if not positions:
        return []
    return [
        dl.CircleMarker(
            center=positions[0],
            radius=7,
            pathOptions=dict(
                color=ROUTE_CASING_COLOR,
                weight=2,
                fillColor=ROUTE_COLOR,
                fillOpacity=1.0,
                interactive=False,
            ),
            children=dl.Tooltip("Route start"),
        ),
        dl.CircleMarker(
            center=positions[-1],
            radius=7,
            pathOptions=dict(
                color=ROUTE_COLOR,
                weight=3,
                fillColor=ROUTE_CASING_COLOR,
                fillOpacity=1.0,
                interactive=False,
            ),
            children=dl.Tooltip("Route end"),
        ),
    ]


def _map_legend():
    """Static color legend overlaid on the map (bottom-left)."""

    def row(color, label, casing=None):
        # inline style: swatch colors come from the map color constants —
        # there is no Bootstrap utility for arbitrary hex values.
        swatch_style = {
            "backgroundColor": color,
            "width": "1.4rem",
            "height": "0.35rem",
        }
        if casing:
            swatch_style["boxShadow"] = f"0 0 0 2px {casing}"
        return html.Div(
            [
                html.Span(style=swatch_style, className="d-inline-block rounded me-2"),
                html.Small(label),
            ],
            className="d-flex align-items-center",
        )

    return html.Div(
        [
            dbc.Collapse(
                html.Div(
                    [
                        row(ROUTE_COLOR, "Route", casing=ROUTE_CASING_COLOR),
                        row(STREET_COLOR, "Road network"),
                        row(STREET_SELECTED_COLOR, "Marked for removal"),
                    ],
                    className="px-2 py-1 bg-white bg-opacity-75 rounded shadow-sm mb-1",
                ),
                id=MAP_LEGEND_COLLAPSE_SHARED_ID,
                is_open=True,
            ),
            dbc.Button(
                [html.I(className="bi bi-map me-1"), "Legend"],
                id=MAP_LEGEND_TOGGLE_BUTTON_SHARED_ID,
                size="sm",
                color="light",
                className="border shadow-sm py-0",
            ),
        ],
        className="position-absolute bottom-0 start-0 m-3 map-legend",
    )


def build_global_map():
    """Build the global persistent map with empty layer slots.

    Layers are populated by register_map_callbacks after Leaflet has initialised.
    The dcc.Interval in app_layout() fires 300 ms after mount — by which point the
    Leaflet layer objects exist and can receive prop updates.
    """
    layers_control = dl.LayersControl(
        [
            *_base_layers(),
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
                    hideout=dict(selected=[], dimmed=True),
                ),
                name="Streets",
                checked=True,
            ),
            dl.Overlay(
                # LayerGroup so the "Route" toggle hides casing + line together.
                dl.LayerGroup(
                    [
                        # White casing under the route line keeps it readable on
                        # top of the base map and the red road network.
                        dl.GeoJSON(
                            id=ROUTE_CASING_LAYER_MAP_ID,
                            data={"type": "FeatureCollection", "features": []},
                            options={
                                "style": {
                                    "color": ROUTE_CASING_COLOR,
                                    "weight": 9,
                                    "opacity": 0.9,
                                },
                                # The route must not swallow clicks meant for
                                # the street layer underneath.
                                "interactive": False,
                            },
                        ),
                        dl.GeoJSON(
                            id=ROUTE_POLYLINE_LAYER_MAP_ID,
                            data={"type": "FeatureCollection", "features": []},
                            options={
                                "style": {
                                    "color": ROUTE_COLOR,
                                    "weight": 5,
                                    "opacity": 1.0,
                                },
                                "interactive": False,
                            },
                        ),
                        # Driving-direction arrowheads: violet fill + thin
                        # white keyline, so they read both on the white
                        # casing and on the violet line itself.
                        dl.PolylineDecorator(
                            id=ROUTE_DIRECTION_DECORATOR_MAP_ID,
                            positions=[],
                            patterns=[
                                dict(
                                    offset="5%",
                                    repeat="120px",
                                    arrowHead=dict(
                                        pixelSize=13,
                                        polygon=True,
                                        pathOptions=dict(
                                            color=ROUTE_CASING_COLOR,
                                            weight=1.5,
                                            fill=True,
                                            fillColor=ROUTE_COLOR,
                                            fillOpacity=1.0,
                                            opacity=1.0,
                                            interactive=False,
                                        ),
                                    ),
                                )
                            ],
                        ),
                        # Start/end markers — populated by update_map_layers
                        # and the reverse-direction toggle.
                        dl.LayerGroup(id=ROUTE_ENDPOINTS_GROUP_MAP_ID),
                    ]
                ),
                name="Route",
                checked=True,
            ),
        ],
        position="topright",
    )
    return dl.Map(
        [dl.FullScreenControl(title="Toggle full screen"), layers_control],
        id=MAIN_MAP_COMPONENT_MAP_SHARED_ID,
        center=[51.70, 11.20],
        zoom=10,
        className="h-100",
        preferCanvas=True,
    )


def app_layout():
    """Create the main page layout with navbar and content."""
    return html.Div(
        className="d-flex flex-column min-vh-100 bg-light app-root",
        children=[
            dcc.Store(id=CURRENT_JOB_ID_MAP_STORE_ID, data=None),
            dcc.Store(id=STREETS_REFRESH_TRIGGER_STORE_SHARED_ID, data=0),
            dcc.Interval(
                id=MAP_INIT_INTERVAL_SHARED_ID, interval=1000, max_intervals=1
            ),
            loading_overlay,
            error_modal,
            create_navbar(),
            html.Div(
                className="d-flex flex-grow-1 app-panels overflow-hidden",
                children=[
                    html.Div(
                        [build_global_map(), _map_legend()],
                        className="map-panel col-7 p-0 position-relative",
                    ),
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
    card_body,
    card_footer=None,
    name_step=None,
    title=None,
    job_id=None,
    completed_steps=None,
):
    """Create a modern card input layout with optional progress steps."""
    if name_step is not None:
        if job_id is None:
            raise ValueError("job_id must be provided when name_step is used.")
        title = steps_jobs[name_step][1]

    if title is None:
        raise ValueError("Either title or name_step must be provided.")

    card_header = []

    if name_step is not None:
        card_header.append(
            html.Code(
                job_id,
                id=JOB_ID_KICKER_CODE_SHARED_ID,
                className="text-muted small d-inline-block mb-1 bg-light px-2 py-1 rounded",
                title="Copy job ID",
                # cursor-pointer: no Bootstrap utility class in v5.2 for cursor
                style={"cursor": "pointer"},
            )
        )

    card_header.append(html.H3(title))

    if name_step is not None:
        card_header.append(steps_tab(name_step, job_id, completed_steps or []))

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


def steps_tab(name_step, job_id, completed_steps):
    """Render a numbered stepper showing wizard progress.

    Completed steps are clickable links (teal). Current step is highlighted
    (navy). Future steps are muted and non-interactive.
    """
    step_items = []
    for i, (step_name, step_info) in enumerate(steps_jobs.items(), start=1):
        is_done = step_name in completed_steps
        is_current = step_name == name_step

        if is_current:
            circle = html.Span(str(i), className="badge rounded-circle bg-primary")
            label = html.Span(step_info[0], className="small ms-1 fw-semibold")
            step_el = html.Span([circle, label], className="d-flex align-items-center")
        elif is_done:
            circle = html.Span(
                html.I(className="bi bi-check-lg"),
                className="badge rounded-circle bg-success",
            )
            label = html.Span(step_info[0], className="small ms-1 text-success")
            step_el = dcc.Link(
                [circle, label],
                href=build_url_step(step_name, job_id),
                className="d-flex align-items-center text-decoration-none",
            )
        else:
            circle = html.Span(
                str(i), className="badge rounded-circle bg-light text-muted border"
            )
            label = html.Span(step_info[0], className="small ms-1 text-muted")
            step_el = html.Span([circle, label], className="d-flex align-items-center")

        step_items.append(step_el)
        if i < len(steps_jobs):
            step_items.append(
                html.I(className="bi bi-chevron-right text-muted mx-2 align-middle")
            )

    return html.Div(
        step_items,
        className="d-flex flex-wrap align-items-center py-2",
    )


# ============================================================================
# Callback Registration Functions
# ============================================================================


def register_navbar_callbacks(app):
    """Register callbacks for the navbar."""

    @app.callback(
        Output(NAVBAR_COLLAPSE_NAV_SHARED_ID, "is_open"),
        [Input(NAVBAR_TOGGLER_NAV_SHARED_ID, "n_clicks")],
        [State(NAVBAR_COLLAPSE_NAV_SHARED_ID, "is_open")],
    )
    def toggle_navbar_collapse(n, is_open):
        if n:
            return not is_open
        return is_open

    @app.callback(
        Output(URL_SHARED_ID, "pathname", allow_duplicate=True),
        Input(NEW_JOB_LINK_NAV_SHARED_ID, "n_clicks"),
        prevent_initial_call=True,
    )
    def start_job_from_navbar(n_clicks):
        """Create a new job and jump to its first wizard step.

        Same flow as the home page's "Create new job" button.
        """
        if not n_clicks:
            raise PreventUpdate

        log.info("Initializing new CosmonautJob from navbar")
        job = CosmonautJob()

        return build_url_step("user_info", job.model.job_id)


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
            log.error(f"Could not extract job_id from pathname: {pathname}")
            raise PreventUpdate

        # Load job and reset
        try:
            job = CosmonautJob(job_id=job_id)
            job.reset()
            log.info(f"Job {job_id} reset successfully from {pathname}")
        except Exception as e:
            log.error(f"Failed to reset job {job_id}: {e}")
            raise PreventUpdate

        # Return same pathname to reload page with new state
        return pathname


def register_map_callbacks(app):
    """Register the global map layer callbacks.

    ``update_map_layers`` handles viewport repositioning, membership tile,
    route polyline, and job-id tracking on every SPA navigation.

    ``update_viewport_streets`` is the single callback that populates the
    street GeoJSON layer.  It fires when:
    - the map viewport moves (``bounds`` change on moveend),
    - an edit bumps the refresh trigger, or
    - the active job changes.
    """

    # Dict-style: 5 outputs (see docs/conventions/callbacks.md, 5+ threshold)
    @app.callback(
        output={
            "viewport": Output(
                MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport", allow_duplicate=True
            ),
            "tile_url": Output(
                MEMBERSHIP_TILE_LAYER_MAP_ID, "url", allow_duplicate=True
            ),
            "route_data": Output(ROUTE_POLYLINE_LAYER_MAP_ID, "data"),
            "route_casing_data": Output(ROUTE_CASING_LAYER_MAP_ID, "data"),
            "route_direction_positions": Output(
                ROUTE_DIRECTION_DECORATOR_MAP_ID, "positions"
            ),
            "route_endpoints_children": Output(
                ROUTE_ENDPOINTS_GROUP_MAP_ID, "children"
            ),
            "job_id": Output(CURRENT_JOB_ID_MAP_STORE_ID, "data"),
        },
        inputs={"pathname": Input(URL_SHARED_ID, "pathname")},
        state={"prev_job_id": State(CURRENT_JOB_ID_MAP_STORE_ID, "data")},
        prevent_initial_call=True,
    )
    def update_map_layers(pathname, prev_job_id):
        log.info(f"Map update triggered by {ctx.triggered_id}: {pathname}")
        empty_fc = {"type": "FeatureCollection", "features": []}
        empty_result = {
            "viewport": no_update,
            "tile_url": "",
            "route_data": empty_fc,
            "route_casing_data": empty_fc,
            "route_direction_positions": [],
            "route_endpoints_children": [],
            "job_id": None,
        }
        parts = pathname.split("/")
        if len(parts) < 3 or parts[1] != "job":
            log.info("Not a job page, returning empty")
            return empty_result

        job_id = parts[2]
        try:
            job = CosmonautJob(job_id=job_id, sync_files=False)
        except JobNotFound:
            log.info(f"Job {job_id} not found, returning empty")
            return empty_result

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
        log.info(f"Returning tile_url={tile_url!r}, route_pts={len(raw_positions)}")
        return {
            "viewport": viewport,
            "tile_url": tile_url,
            "route_data": route_fc,
            # Casing gets the same geometry — it renders as the white halo
            # under the route line.
            "route_casing_data": route_fc,
            # Decorator takes Leaflet [lat, lon] positions directly.
            "route_direction_positions": [list(pos) for pos in raw_positions],
            "route_endpoints_children": route_endpoint_markers(raw_positions),
            "job_id": job_id,
        }

    @app.callback(
        Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
        Input(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "bounds"),
        Input(STREETS_REFRESH_TRIGGER_STORE_SHARED_ID, "data"),
        Input(CURRENT_JOB_ID_MAP_STORE_ID, "data"),
        State(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "zoom"),
        prevent_initial_call=True,
    )
    def update_viewport_streets(bounds, _data_version, job_id, zoom):
        """Load street features for the current viewport and zoom level."""
        empty_fc = {"type": "FeatureCollection", "features": []}
        if not job_id or not bounds:
            return empty_fc

        try:
            job = CosmonautJob(job_id=job_id, sync_files=False)
        except JobNotFound:
            return empty_fc

        return StreetSelector(job).viewport_fc(bounds, zoom or 10)

    @app.callback(
        Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout", allow_duplicate=True),
        Input(URL_SHARED_ID, "pathname"),
        State(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout"),
        # "initial_duplicate": guarantee the dim styling is computed on a
        # HARD page load too (browser refresh), independent of whether the
        # pages hydration happens to fire pathname callbacks initially.
        prevent_initial_call="initial_duplicate",
    )
    def toggle_map_dim_on_page(pathname, current_hideout):
        """Dim the map on all pages except street_selection."""
        if not pathname or not current_hideout:
            # leave hideout untouched — returning None would clobber the
            # GeoJSON layer's state and the style_handle would crash on
            # context.hideout.dimmed
            raise PreventUpdate
        dimmed = not pathname.endswith("/street-selection")
        log.info(f"Map dim toggle: {pathname} -> dimmed={dimmed}")
        return {**current_hideout, "dimmed": dimmed}

    @app.callback(
        Output(MAP_LEGEND_COLLAPSE_SHARED_ID, "is_open"),
        Input(MAP_LEGEND_TOGGLE_BUTTON_SHARED_ID, "n_clicks"),
        State(MAP_LEGEND_COLLAPSE_SHARED_ID, "is_open"),
        prevent_initial_call=True,
    )
    def toggle_map_legend(n_clicks, is_open):
        """Collapse/expand the map color legend."""
        if n_clicks:
            return not is_open
        return is_open


# Copy job ID to clipboard on click, flash background to confirm.
dash.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) { return window.dash_clientside.no_update; }
        var el = document.getElementById('""" + JOB_ID_KICKER_CODE_SHARED_ID + """');
        if (!el) { return window.dash_clientside.no_update; }
        navigator.clipboard.writeText(el.innerText).then(function() {
            el.classList.add('bg-success', 'bg-opacity-25');
            setTimeout(function() {
                el.classList.remove('bg-success', 'bg-opacity-25');
            }, 600);
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output(JOB_ID_KICKER_CODE_SHARED_ID, "className"),
    Input(JOB_ID_KICKER_CODE_SHARED_ID, "n_clicks"),
    prevent_initial_call=True,
)
