import os
import glob
import math
import json
import time
import logging
import re
import dash
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import dcc, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash import ctx
from dash_extensions.javascript import assign

from cosmonaut_app.config import WEB_WORK_DIR, osm_tags_mapping
from cosmonaut_app.constants.html_ids import (
    CLICKED_ROADS_STORE_SHARED_ID,
    EMAIL_STORE_SHARED_ID,
    EPSG_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MAIN_MAP_DIV_MAP_SHARED_ID,
    MANAGED_LAYERS_GROUP_MAP_SHARED_ID,
    NAVBAR_COLLAPSE_NAV_SHARED_ID,
    NAVBAR_TOGGLER_NAV_SHARED_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    REDIRECT_INTERVAL_NAV_SHARED_ID,
    ROUTE_GEOJSON_LAYER_MAP_SHARED_ID,
    ROUTE_LAYER_LAYER_MAP_SHARED_ID,
    ROUTING_COMPLETE_STORE_SHARED_ID,
    SEARCH_BUTTON_NAV_SHARED_ID,
    SEARCH_INPUT_NAV_SHARED_ID,
    SEARCH_RESULTS_DIV_NAV_SHARED_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    URL_SHARED_ID,
    USER_INFO_EMAIL_INPUT_USER_INFO_ID,
)
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.transformation import transform_solution
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

steps_jobs = {
    "user_info": "User information",
    "data_upload": "Data upload",
    "street_selection": "Street selection",
    "routing_params": "Routing Parameters",
    "rout_download": "Route",
}


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
                    search_bar,
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
                dcc.Interval(
                    id=REDIRECT_INTERVAL_NAV_SHARED_ID,
                    interval=3000,
                    n_intervals=0,
                    disabled=True,
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
            error_modal,
            create_navbar(),
            dash.page_container,
        ],
    )


def page_container_fullscreen_layout(content):
    """Create a page container with a fullscreen layout."""
    return html.Div(
        className="d-flex flex-column flex-grow-1 bg-white p-0 m-0", children=content
    )


def page_container_split_layout(map, input):
    """Create a page container with a split layout (sidebar + main map)."""
    map_container = dbc.Col(
        map,
        className="col-7 p-0",
        id="map-container",
    )
    input_container = dbc.Col(
        input,
        className="col-5 p-0",
        id="input_container",
    )
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

    logging.info(card_header)
    card_content = [
        dbc.CardHeader(card_header),
        dbc.CardBody(card_body),
    ]

    if card_footer:
        card_content.append(card_footer)

    logging.info(
        dbc.Card(
            card_content,
            className="shadow-sm m-3 me-4",
        )
    )

    return dbc.Card(
        card_content,
        className="shadow-sm m-3 me-4",
    )


def build_url_step(step, job_id):
    base_path = dash.page_registry[f"pages.{step}"]["path_template"]
    return base_path.replace("<job_id>", job_id)


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
        logging.info(kwargs_next)
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
                tab_id=step_name,
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
osm_layer = dl.TileLayer(
    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution="© OpenStreetMap contributors",
)
default_map_layers = [osm_layer, dl.FullScreenControl()]
default_map = html.Div(
    dl.Map(
        default_map_layers,
        id=MAIN_MAP_COMPONENT_MAP_SHARED_ID,
        center=[51.70, 11.20],
        zoom=10,
        style={"height": "100%"},
    ),
    id=MAIN_MAP_DIV_MAP_SHARED_ID,
    style={"height": "100%", "width": "100%"},
)

# TODO
main_map = html.Div(
    dl.Map(
        default_map_layers,
        id=MAIN_MAP_COMPONENT_MAP_SHARED_ID,
        center=[51.70, 11.20],
        zoom=10,
        style={"height": "100%"},
    ),
    id=MAIN_MAP_DIV_MAP_SHARED_ID,
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
            job = CosmonautJob(job_id=job_id, download_from_minio=True)
            job.load()

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


def register_shared_store_callbacks(app):
    """Register callbacks for shared stores (email, etc.)."""

    @app.callback(
        Output(EMAIL_STORE_SHARED_ID, "data"),
        Input(USER_INFO_EMAIL_INPUT_USER_INFO_ID, "value"),
        prevent_initial_call=True,
    )
    def store_email(email):
        return email


def register_map_callbacks(app):
    """Register callbacks for map display and interaction."""

    @app.callback(
        Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "children"),
        Input(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
        State(JOB_ID_STORE_SHARED_ID, "data"),
        Input(ROUTING_COMPLETE_STORE_SHARED_ID, "data"),
        State(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "children"),
        State(EPSG_STORE_SHARED_ID, "data"),
        prevent_initial_call=True,
        allow_duplicate=True,
    )
    def update_map(
        selected_roads, job_id, routing_complete, current_children, epsg_input
    ):
        logging.info("=== UPDATE_MAP CALLBACK START ===")
        logging.info("Trigger ID: %s", ctx.triggered_id)
        logging.info("Selected roads: %s", selected_roads)
        logging.info("Routing complete: %s", routing_complete)

        # Normalize children
        current_children = list(current_children or [])

        # Remove our entire managed group (safer than removing individual layers)
        managed_ids = {
            OSM_GEOJSON_LAYER_MAP_SHARED_ID,
            ROUTE_GEOJSON_LAYER_MAP_SHARED_ID,
            ROUTE_LAYER_LAYER_MAP_SHARED_ID,
            MANAGED_LAYERS_GROUP_MAP_SHARED_ID,
        }
        cleaned_children, removed = [], 0
        for child in current_children:
            comp_id = None
            if isinstance(child, dict):
                props = child.get("props") or {}
                comp_id = props.get("id")
            else:
                comp_id = getattr(child, "id", None)
            if comp_id in managed_ids:
                removed += 1
                continue
            cleaned_children.append(child)
        current_children = cleaned_children
        logging.info(
            "Cleaned map children, removed %d managed item(s), remaining: %d",
            removed,
            len(current_children),
        )

        # Collect new managed layers, then add them as one LayerGroup
        new_layers = []

        if routing_complete:
            logging.info("=== ROUTING SECTION ===")
            logging.info("Processing routing solution for job: %s", job_id)

            job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
            solution_path = os.path.join(job_working_dir, "transient", "solution.json")

            start_transform = time.time()
            transformed_solution = transform_solution(
                solution_path, epsg_input, 4326, False
            )
            logging.info("Solution transformed in %.3fs", time.time() - start_transform)

            route_geojson = dl.GeoJSON(
                data=transformed_solution,
                options={"style": {"color": "blue", "weight": 5}},
                id=ROUTE_GEOJSON_LAYER_MAP_SHARED_ID,
                zoomToBounds=True,
            )
            new_layers.append(route_geojson)

            workdir = os.path.join(WEB_WORK_DIR, job_id)
            transient_dir = os.path.join(workdir, "transient")
            route_path = os.path.join(transient_dir, "solution_route_4326.geojson")
            if os.path.isfile(route_path):
                try:
                    route_fc = _load_geojson(route_path)
                    route_layer = dl.GeoJSON(
                        data=route_fc,
                        id=ROUTE_LAYER_LAYER_MAP_SHARED_ID,
                        zoomToBounds=True,
                        options=dict(
                            style=dict(color="#0066ff", weight=5, opacity=0.9)
                        ),
                    )
                    new_layers.append(route_layer)
                    logging.info("Added route layer to map.")
                except Exception as e:
                    logging.warning("Could not add route layer: %s", e)

        elif (
            ctx.triggered_id == TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID
            and selected_roads is not None
            and job_id
        ):
            logging.info("=== OPTIMIZED TAG FILTERING SECTION ===")
            filter_start_time = time.time()

            # Distinguish between None (no value yet -> show all) and empty list (user explicitly selected none -> show none)
            if selected_roads is None:
                selected_roads = list(osm_tags_mapping.keys())
                logging.info(
                    "Selection is None; defaulting to all tags: %s", selected_roads
                )
            elif selected_roads == []:
                logging.info("Empty selection provided; will show zero features.")

            logging.info("Converting German road types: %s", selected_roads)
            osm_highway_types = set()
            for german_type in selected_roads:
                if german_type in osm_tags_mapping:
                    osm_highway_types.update(osm_tags_mapping[german_type])
                else:
                    logging.warning("Unknown German road type: %s", german_type)
            logging.info("Mapped to OSM highway types: %s", list(osm_highway_types))

            in_dir = os.path.join(WEB_WORK_DIR, job_id, "input")
            preferred_candidates = [
                os.path.join(in_dir, "osm_data_work_4326.geojson"),
                os.path.join(in_dir, "osm_data_raw_4326.geojson"),
                os.path.join(in_dir, "osm_data.geojson"),
            ]
            timeout = 30
            start_wait = time.time()
            chosen_path = None

            while (time.time() - start_wait) < timeout and chosen_path is None:
                for candidate in preferred_candidates:
                    if os.path.exists(candidate):
                        chosen_path = candidate
                        break
                if chosen_path is None:
                    matches = glob.glob(os.path.join(in_dir, "*_4326.geojson"))
                    if matches:
                        chosen_path = matches[0]
                if chosen_path is None:
                    time.sleep(0.5)

            if not chosen_path:
                logging.error("No GeoJSON file found in %s after %ss", in_dir, timeout)
                raise FileNotFoundError(
                    f"No GeoJSON file found in {in_dir} after {timeout}s"
                )

            load_start = time.time()
            with open(chosen_path, encoding="utf-8") as f:
                data = json.load(f)
            logging.info(
                "Loaded GeoJSON from %s in %.3fs", chosen_path, time.time() - load_start
            )

            original_count = len(data["features"])
            filtered_features = [
                feature
                for feature in data["features"]
                if feature.get("properties", {}).get("highway") in osm_highway_types
            ]
            logging.info(
                "Filtering completed in %.3fs: %d -> %d features (%.1f%% reduction)",
                time.time() - filter_start_time,
                original_count,
                len(filtered_features),
                (
                    round((1 - len(filtered_features) / original_count) * 100, 1)
                    if original_count
                    else 0
                ),
            )

            filtered_data = {"type": "FeatureCollection", "features": filtered_features}
            _coerce_nodes_list(filtered_data["features"])

            tooltip_start = time.time()
            for feature in filtered_features:
                highway_type = feature["properties"]["highway"]
                name = feature["properties"].get("name") or feature["properties"].get(
                    "ref"
                )
                tracktype = feature["properties"].get("tracktype")
                feature["properties"]["tooltip"] = (
                    f"{name}, {highway_type}, {tracktype}"
                    if highway_type == "track" and tracktype
                    else f"{name}, {highway_type}"
                )
            logging.info("Added tooltips in %.3fs", time.time() - tooltip_start)

            osm_layer = dl.GeoJSON(
                data=filtered_data,
                options={"style": style_handle, "hoverStyle": hover_style_handle},
                hideout=dict(selected=[], zoom=10),
                id=OSM_GEOJSON_LAYER_MAP_SHARED_ID,
                # Do not re-zoom on tag changes; initial page load already zooms
                zoomToBounds=False,
            )
            new_layers.append(osm_layer)

            logging.info(
                "Total filtering operation completed in %.3fs",
                time.time() - filter_start_time,
            )

        elif (
            ctx.triggered_id == TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID
            and not job_id
        ):
            logging.warning("Tag dropdown triggered but no job ID available")

        # Add/replace our managed group once
        if new_layers:
            current_children.append(
                dl.LayerGroup(
                    id=MANAGED_LAYERS_GROUP_MAP_SHARED_ID, children=new_layers
                )
            )

        logging.info(
            "=== UPDATE_MAP CALLBACK END === Returning %d children",
            len(current_children),
        )
        return current_children

    @app.callback(
        Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout", allow_duplicate=True),
        Input(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "n_clicks"),
        State(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "clickData"),
        State(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout"),
        prevent_initial_call=True,
    )
    def toggle_select(_, clickData, hideout):
        if clickData is None or hideout is None or _ is None:
            raise PreventUpdate

        selected = hideout["selected"]
        id = clickData["id"]
        if id in selected:
            selected.remove(id)
        else:
            selected.append(id)
        return hideout

    @app.callback(
        Output(CLICKED_ROADS_STORE_SHARED_ID, "data", allow_duplicate=True),
        [Input(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "clickData")],
        [State(CLICKED_ROADS_STORE_SHARED_ID, "data")],
        prevent_initial_call=True,
    )
    def update_clicked_roads(clickData, clicked_roads):
        if clickData is None:
            raise PreventUpdate
        id = clickData["id"]
        if id not in clicked_roads:
            clicked_roads.append(id)
        return clicked_roads
