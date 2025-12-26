import os
import math
import json
import logging
import re
import dash
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import dcc, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash_extensions.javascript import assign

from cosmonaut_app.config import WEB_WORK_DIR, osm_tags_mapping
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    NAVBAR_COLLAPSE_NAV_SHARED_ID,
    NAVBAR_TOGGLER_NAV_SHARED_ID,
    SEARCH_BUTTON_NAV_SHARED_ID,
    SEARCH_INPUT_NAV_SHARED_ID,
    SEARCH_RESULTS_DIV_NAV_SHARED_ID,
    URL_SHARED_ID,
    LOADING_OVERLAY_SHARED_ID,
)
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.error_handling import error_modal


# ============================================================================
# Helper Functions and Constants
# ============================================================================

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


def _coerce_nodes_list(features):
    """
    Ensure properties['nodes'] is a list[int] for every feature.
    Handles cases where nodes are stored as a JSON string or other iterables.
    """
    fixed = 0
    for feat in features:
        props = feat.get("properties") or {}
        nodes = props.get("nodes")
        if nodes is None:
            continue

        # Already a sequence: coerce items to int
        if isinstance(nodes, (list, tuple)):
            try:
                props["nodes"] = [int(n) for n in nodes]
            except Exception:
                # leave as-is if coercion fails
                pass
            continue

        # String case: try JSON first, then regex fallback
        if isinstance(nodes, str):
            parsed = None
            try:
                parsed = json.loads(nodes)
            except Exception:
                # extract integers from any string like "[1, 2, 3]" or "1,2,3"
                parsed = [int(m.group(0)) for m in re.finditer(r"-?\d+", nodes)]
            if isinstance(parsed, list):
                try:
                    props["nodes"] = [int(n) for n in parsed]
                    fixed += 1
                except Exception:
                    # leave original if conversion fails
                    pass
    logging.info("Normalized nodes lists for %d features", fixed)
    return features


def _coerce_osmid(props, feature_id=None, fallback=None):
    # Accept osmid, osm_id, id (props), or feature.id; return int if possible.
    candidates = [
        props.get("osmid"),
        props.get("osm_id"),
        props.get("id"),
        feature_id,
    ]
    for c in candidates:
        if c is None:
            continue
        # If list/tuple, take the first
        if isinstance(c, (list, tuple)):
            c = c[0] if c else None
        if c is None:
            continue
        # Extract first integer substring
        m = re.search(r"-?\d+", str(c))
        if m:
            try:
                return int(m.group(0))
            except Exception:
                pass
        if isinstance(c, int):
            return c
    return fallback


def _normalize_for_sensor_routing(features):
    """Ensure fields required by sensor-routing exist with expected types."""
    missing = 0
    for i, feat in enumerate(features):
        props = feat.get("properties") or {}
        # osmid: single int
        osmid = _coerce_osmid(props, feat.get("id"), fallback=i + 1)
        if "osmid" not in props:
            missing += 1
        props["osmid"] = osmid
        # nodes: list[int]
        nodes = props.get("nodes")
        if isinstance(nodes, str):
            try:
                nodes = json.loads(nodes)
            except Exception:
                nodes = [int(n) for n in re.findall(r"-?\d+", nodes)]
            props["nodes"] = nodes
        if isinstance(props.get("nodes"), (list, tuple)):
            try:
                props["nodes"] = [int(n) for n in props["nodes"]]
            except Exception:
                pass
        # oneway: normalize to "yes"/"no" strings
        ow = props.get("oneway")
        if isinstance(ow, bool):
            props["oneway"] = "yes" if ow else "no"
        elif ow is not None:
            s = str(ow).lower()
            if s in ("1", "true", "yes"):
                props["oneway"] = "yes"
            elif s in ("0", "false", "no", "-1"):
                props["oneway"] = "no"
        feat["properties"] = props
    logging.info(
        "Normalized %d features; added osmid to %d features", len(features), missing
    )


def _filter_by_tags(features, selected_roads):
    # Default to all available tags if none are selected so we render a network
    if not selected_roads:
        selected_roads = list(osm_tags_mapping.keys())
    osm_highway_types = set()
    for german_type in selected_roads:
        if german_type in osm_tags_mapping:
            osm_highway_types.update(osm_tags_mapping[german_type])
    return [
        f
        for f in features
        if (f.get("properties") or {}).get("highway") in osm_highway_types
    ]


def _paths(job_id):
    in_dir = os.path.join(WEB_WORK_DIR, job_id, "input")
    return (
        in_dir,
        os.path.join(in_dir, "osm_data_raw_4326.geojson"),
        os.path.join(in_dir, "osm_data_work_4326.geojson"),
        os.path.join(in_dir, "osm_data.geojson"),
    )


def _load_fc(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_fc_4326_no_crs(path, feature_collection):
    # ensure no 'crs' member (RFC 7946)
    data = dict(feature_collection)
    data.pop("crs", None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _load_geojson(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# Layout Components
# ============================================================================

osm_layer = dl.TileLayer(
    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution="© OpenStreetMap contributors",
)
default_map_layers = [osm_layer, dl.FullScreenControl()]
# TODO That is a dupliation each page has a name this could be looked up dynamically
steps_jobs = {
    "user_info": "User information",
    "data_upload": "Data upload",
    "street_selection": "Street selection",
    "routing_params": "Routing Parameters",
    "route_download": "Route",
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


def create_navbar():
    """Create a navbar layout."""
    return dbc.Navbar(
        color="dark",
        dark=True,
        sticky="top",
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
                                    "Logs",
                                    href=dash.page_registry["pages.logs"][
                                        "relative_path"
                                    ],
                                )
                            ),
                            dbc.NavItem(
                                dbc.NavLink(
                                    "Worker manager",
                                    href=dash.page_registry["pages.worker_management"][
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


def app_layout():
    """Create the main page layout with navbar and content."""
    return html.Div(
        className="d-flex flex-column min-vh-100 bg-light",
        children=[
            dcc.Location(id=URL_SHARED_ID, refresh=True),
            loading_overlay,
            error_modal,
            create_navbar(),
            dash.page_container,
        ],
    )


def page_container_fullscreen_layout(content):
    """Create a page container with a fullscreen layout."""
    return html.Main(
        className="d-flex flex-column flex-grow-1 bg-white p-0 m-0", children=content
    )


def page_container_split_layout(map, input):
    """Create a page container with a split layout (sidebar + main map)."""
    map_container = dbc.Col(
        map,
        className="col-7 p-0",
    )
    input_container = dbc.Col(input, className="col-5 p-0")
    return page_container_fullscreen_layout(
        dbc.Row(
            [
                map_container,
                input_container,
            ],
            className="flex-grow-1 d-flex",
        ),
    )


def create_card_input(
    card_body, card_footer=None, name_step=None, title=None, job_id=None
):
    """Create a modern card input layout with optional progress steps."""
    if name_step is not None:
        if job_id is None:
            raise ValueError("job_id must be provided when name_step is used.")
        title = f"{steps_jobs[name_step]}({job_id})"

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
            html.H2(title, className="text-center", id=f"{id}-title"),
            (
                html.H3(subtitle, className="text-center", id=f"{id}-subtitle")
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

    args_prev = [html.I(className="bi bi-arrow-right-circle me-1"), "Previous"]
    kwargs_prev = dict(color="primary", disabled=prev_disabled)
    if prev_id is None and prev_url is None:
        prev_button = html.Span()
    else:
        if prev_url is not None:
            kwargs_prev["href"] = prev_url
        if prev_id is not None:
            kwargs_prev["id"] = prev_id
        prev_button = dbc.Button(args_prev, **kwargs_prev)

    args_next = [html.I(className="bi bi-arrow-right-circle me-1"), "Next"]
    kwargs_next = dict(color="primary", disabled=next_disabled)
    if next_id is None and next_url is None:
        next_button = html.Span()
    else:
        if next_url is not None:
            kwargs_next["href"] = next_url
        if next_id is not None:
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
    for step_name, step_label in steps_jobs.items():
        list_tabs.append(
            dbc.Tab(
                label=step_label,
                tab_id=step_name,  # nocheck
                disabled=True,
            )
        )

    return dbc.Tabs(
        list_tabs,
        active_tab=name_step,
    )


def progress_steps(current: int, variant: str = "default") -> html.Div:
    """Render a 5-step progress rail with labeled nodes.

    variant: 'default' (in-flow) or 'home' (pre-start: no fill, all upcoming).
    """

    steps = [
        ("User information", "user_info"),
        ("Data upload", "data_upload"),
        ("Street selection", "street_selection"),
        ("Routing Parameters", "routing_params"),
        ("Route", "rout_download"),
    ]
    total = len(steps)
    # Use internal points: positions at k/(n+1) for k=1..n (exclude 0 and 1).
    if variant == "home" or total <= 1:
        width_value = "0%"
    else:
        # Cosine-spaced internal points: x_i = ((1 - cos(i*pi/(n+1))) / 2) * 100
        widths = [
            (1 - math.cos(math.pi * i / (total + 1))) * 50.0
            for i in range(1, total + 1)
        ]
        width_value = f"{widths[current - 1]:.6f}%"

    nodes = []
    for i, (label, _icon) in enumerate(steps, start=1):
        if variant == "home":
            state_cls = "upcoming"
        else:
            state_cls = (
                "done" if i < current else ("current" if i == current else "upcoming")
            )
        nodes.append(
            html.Div(
                [html.Span(className="dot"), html.Span(label, className="label")],
                className=f"node {state_cls}",
                role="listitem",
            )
        )

    return html.Div(
        [
            html.Div(
                [html.Div(className="rail-fill", style={"width": width_value})],
                className="rail",
            ),
            html.Div(nodes, className="nodes", role="list"),
        ],
        className=f"progress-steps{' home' if variant == 'home' else ''}",
        role="group",
        **{"aria-label": "Progress steps"},
    )


def create_map(job=None, extra_layers=None):
    map_layers = default_map_layers
    if extra_layers is not None:
        map_layers += extra_layers

    if job is not None:
        zoom = job.model.classification_upload["zoom"]
        center = job.model.classification_upload["center"]
    else:
        zoom = 10
        center = [51.70, 11.20]

    return dl.Map(
        map_layers,
        id=MAIN_MAP_COMPONENT_MAP_SHARED_ID,
        center=center,
        zoom=zoom,
        style={"height": "100%"},
    )


def page_layout(
    title: str,
    body,
    job_id: str | None = None,
    footer=None,
    below=None,
    step_index: int | None = None,
) -> html.Main:
    """Standard page layout used by all job pages.

    step_index is 1-based and, when provided, will render a 5-step progress
    header across the app (User Info → Data Upload → Street Selection →
    Navigation Selection → QR Code Navigation). Completed steps are shown in
    green (light), current in primary, upcoming in secondary outline.
    """

    # use shared renderer; include optional stepper in header for consistent placement
    header_children = [
        dbc.Row(
            [
                dbc.Col(html.H4(title, className="mb-0"), xs=12, md="auto"),
                dbc.Col(
                    dbc.Badge(
                        f"Job: {job_id or '—'}", color="primary", className="ms-md-3"
                    ),
                    xs=12,
                    md="auto",
                ),
            ],
            className="g-2 align-items-center",
            justify="between",
        )
    ]
    if step_index is not None:
        header_children.append(html.Div(progress_steps(step_index), className="mt-2"))
    header = dbc.CardHeader(header_children)

    # Build card children; include stepper (if any) at the top of the body
    body_children = []
    body_children.extend(body if isinstance(body, list) else [body])

    card_children = [header, dbc.CardBody(body_children)]
    if footer is not None:
        card_children.append(footer)  # footer is a CardFooter (see below)

    content = [dbc.Card(card_children, className="shadow-sm modern-card")]
    if below is not None:
        content.append(below)

    return html.Main(content, role="main", tabIndex=0, className="p-3 p-md-4 page-main")


# Main Map

# TODO
main_map = html.Div(
    dl.Map(
        default_map_layers,
        id=MAIN_MAP_COMPONENT_MAP_SHARED_ID,
        center=[51.70, 11.20],
        zoom=10,
        style={"height": "100%"},
    ),
    style={"height": "100%", "width": "100%"},
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
                "Search",
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
