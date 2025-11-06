"""Street Selection page: select streets for routing."""

import os
import json
import time
import logging
import shutil
import re
from dash import (
    html,
    register_page,
    dcc,
    callback,
    Input,
    Output,
    State,
    ctx,
    no_update,
)
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import geojson

from cosmonaut_app.config import osm_tags_mapping, WEB_WORK_DIR
from cosmonaut_app.constants.html_ids import (
    ACTION_ALERT_ALERT_STREET_SELECTION_ID,
    CANCEL_RESET_BUTTON_STREET_SELECTION_ID,
    CLICKED_ROADS_STORE_SHARED_ID,
    CONFIRM_RESET_BUTTON_STREET_SELECTION_ID,
    EPSG_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
    NONE_DIV_SHARED_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID,
    RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID,
    RESET_ROADS_BUTTON_STREET_SELECTION_ID,
    SELECTION_COUNT_DIV_STREET_SELECTION_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    TAGS_LAST_SELECTION_STORE_SHARED_ID,
    TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
    TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
    UNDO_BUTTON_BUTTON_STREET_SELECTION_ID,
    NEXT_BUTTON_STREET_SELECTION_ID,
)
from cosmonaut_app.transformation import transform_geojson
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_dead_roads,
    remove_disconnected_roads,
)
from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.layout import (
    page_container_split_layout,
    create_card_input,
    progress_footer,
    default_map,
    build_url_step,
)

register_page(
    __name__,
    path_template="/job/<job_id>/street_selection",
    name="Street Selection",
    title="Street Selection",
    description="Select streets for the routing process.",
    dynamic=True,
)


def layout(job_id):
    card_body = [
        dcc.Store(id=TAGS_LAST_SELECTION_STORE_SHARED_ID, storage_type="session"),
        html.P(
            "Wählen Sie die gewünschten Straßen im linken Kartenbereich aus. "
            "Klicken Sie eine Straße an, um sie zu markieren. Mit dem Button "
            "'Remove selected' entfernen Sie die Auswahl. 'Keep largest' behält die größte "
            "zusammenhängende Teilmenge innerhalb der aktuell gewählten Straßentypen.",
            className="text-muted",
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Label(
                        "Straßenauswahl",
                        html_for=TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
                        className="mt-2",
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.ButtonGroup(
                        [
                            dbc.Button(
                                "Select all",
                                id=TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
                                size="sm",
                                color="link",
                            ),
                            dbc.Button(
                                "Select none",
                                id=TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
                                size="sm",
                                color="link",
                            ),
                        ],
                        size="sm",
                        className="ms-2",
                    ),
                    width="auto",
                    className="d-flex align-items-end",
                ),
            ],
            className="g-0",
        ),
        dbc.Checklist(
            id=TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
            options=[{"label": tag, "value": tag} for tag in osm_tags_mapping.keys()],
            value=[],  # will be initialized via callback
            switch=True,
            inline=True,
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.ButtonGroup(
                        [
                            dbc.Button(
                                [
                                    html.I(className="bi bi-eraser me-1"),
                                    "Remove selected",
                                ],
                                id=REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID,
                                color="danger",
                                outline=True,
                            ),
                            dbc.Button(
                                [
                                    html.I(className="bi bi-diagram-3 me-1"),
                                    "Keep largest",
                                ],
                                id=LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
                                color="primary",
                                outline=True,
                            ),
                            dbc.Button(
                                [
                                    html.I(
                                        className="bi bi-arrow-counterclockwise me-1"
                                    ),
                                    "Reset edits",
                                ],
                                id=RESET_ROADS_BUTTON_STREET_SELECTION_ID,
                                color="secondary",
                                outline=True,
                            ),
                            dbc.Button(
                                [
                                    html.I(className="bi bi-arrow-90deg-left me-1"),
                                    "Undo",
                                ],
                                id=UNDO_BUTTON_BUTTON_STREET_SELECTION_ID,
                                color="secondary",
                                outline=True,
                            ),
                        ],
                        size="md",
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Badge(
                        "Selected: 0",
                        id=SELECTION_COUNT_DIV_STREET_SELECTION_ID,
                        color="info",
                        className="ms-2",
                    ),
                    width="auto",
                    className="d-flex align-items-center",
                ),
            ],
            className="g-2 align-items-center mt-2",
        ),
        # Reset confirmation modal
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Reset edits?")),
                dbc.ModalBody(
                    "This will restore the roads to the initial OSM state for this job."
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button(
                            "Cancel",
                            id=CANCEL_RESET_BUTTON_STREET_SELECTION_ID,
                            color="secondary",
                            outline=True,
                        ),
                        dbc.Button(
                            "Reset",
                            id=CONFIRM_RESET_BUTTON_STREET_SELECTION_ID,
                            color="danger",
                        ),
                    ]
                ),
            ],
            id=RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID,
            is_open=False,
            backdrop="static",
            keyboard=False,
        ),
    ]

    user_info_path = build_url_step("data_upload", job_id)
    street_selection_path = build_url_step("routing_params", job_id)

    footer = progress_footer(
        prev_url=user_info_path,
        next_url=street_selection_path,
        next_id=NEXT_BUTTON_STREET_SELECTION_ID,
        next_disabled=True,
    )

    map = default_map
    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_split_layout(map, input_container)


# ============================================================================
# Helper Functions
# ============================================================================


def _coerce_nodes_list(features):
    """Coerce nodes from str representation back to list."""
    for f in features:
        nodes = f.get("properties", {}).get("nodes")
        if isinstance(nodes, str):
            try:
                nodes = json.loads(nodes)
            except Exception:
                nodes = []
            f["properties"]["nodes"] = nodes


def _normalize_for_sensor_routing(features):
    """Ensure fields required by sensor-routing exist with expected types."""

    def _coerce_osmid(props, fallback_id, fallback):
        for c in (props.get("osmid"), props.get("id"), fallback_id):
            if isinstance(c, int):
                return c
        return fallback

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


def _snapshot_work_copy(in_dir, work_4326):
    """Save timestamped backup before modifying work file."""
    try:
        if os.path.exists(work_4326):
            hist_dir = os.path.join(in_dir, "history")
            os.makedirs(hist_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d-%H%M%S")
            dst = os.path.join(hist_dir, f"osm_data_work_4326_{ts}.geojson")
            shutil.copy2(work_4326, dst)
            return dst
    except Exception as e:
        logging.warning("Snapshot failed: %s", e)
    return None


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    [Input(REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [
        State(CLICKED_ROADS_STORE_SHARED_ID, "data"),
        State(JOB_ID_STORE_SHARED_ID, "data"),
        State(EPSG_STORE_SHARED_ID, "data"),
        State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    ],
    prevent_initial_call=True,
)
def remove_selected(n, clicked_roads, job_id, epsg_input, selected_roads):
    if not n or not job_id:
        raise PreventUpdate
    if not clicked_roads:
        logging.info("No roads selected; nothing to remove.")
        raise PreventUpdate

    in_dir, raw_4326, work_4326 = _paths(job_id)
    _snapshot_work_copy(in_dir, work_4326)
    if not os.path.exists(work_4326):
        # First-time edit: seed from raw
        if os.path.exists(raw_4326):
            with (
                open(raw_4326, encoding="utf-8") as fsrc,
                open(work_4326, "w", encoding="utf-8") as fdst,
            ):
                fdst.write(fsrc.read())
        else:
            logging.error("Missing baseline file: %s", raw_4326)
            raise PreventUpdate

    data = _load_fc(work_4326)
    all_roads = data.get("features", [])
    _coerce_nodes_list(all_roads)

    # Build graph and remove roads idempotently
    G = build_graph(all_roads)
    unique_ids = list(dict.fromkeys(clicked_roads))  # de-dup preserve order
    for road_id in unique_ids:
        try:
            all_roads = remove_dead_roads(road_id, all_roads, G)
            # Rebuild graph after each removal to keep consistency
            G = build_graph(all_roads)
        except Exception as e:
            logging.warning("remove_dead_roads failed for %s: %s", road_id, e)

    # Persist updated working copy (4326, no crs)
    updated_fc = {"type": "FeatureCollection", "features": all_roads}
    _save_fc_4326_no_crs(work_4326, updated_fc)

    # Re-export EPSG-specific file for downstream steps
    try:
        if epsg_input:
            transformed = transform_geojson(work_4326, 4326, epsg_input)
            # Ensure required fields for sensor-routing
            feats = transformed.get("features", [])
            _coerce_nodes_list(feats)
            _normalize_for_sensor_routing(feats)
            transformed = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_input}"},
                },
                "features": feats,
            }
            with open(
                os.path.join(in_dir, f"osm_data_{epsg_input}.geojson"),
                "w",
                encoding="utf-8",
            ) as f:
                geojson.dump(transformed, f)
    except Exception as e:
        logging.warning("Failed to write projected export: %s", e)

    # Return filtered view according to current tag selection
    visible = _filter_by_tags(all_roads, selected_roads)
    return {"type": "FeatureCollection", "features": visible}


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    [Input(LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [
        State(JOB_ID_STORE_SHARED_ID, "data"),
        State(EPSG_STORE_SHARED_ID, "data"),
        State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    ],
    prevent_initial_call=True,
)
def keep_largest_subnetwork(n, job_id, epsg_input, selected_roads):
    if not n or not job_id:
        raise PreventUpdate

    in_dir, raw_4326, work_4326 = _paths(job_id)
    _snapshot_work_copy(in_dir, work_4326)
    # Load from work; seed from raw if needed
    if not os.path.exists(work_4326):
        if os.path.exists(raw_4326):
            with (
                open(raw_4326, encoding="utf-8") as fsrc,
                open(work_4326, "w", encoding="utf-8") as fdst,
            ):
                fdst.write(fsrc.read())
        else:
            logging.error("Missing baseline file: %s", raw_4326)
            raise PreventUpdate

    data = _load_fc(work_4326)
    all_roads = data.get("features", [])
    _coerce_nodes_list(all_roads)

    # Work within the current tag filter for a user-friendly result
    filtered_subset = _filter_by_tags(all_roads, selected_roads)
    logging.info(
        "Largest-subnetwork on filtered subset: %d features", len(filtered_subset)
    )

    if not filtered_subset:
        logging.info("No features in current filter; nothing to keep.")
        raise PreventUpdate

    # Build graph on the filtered subset and keep only its largest component
    G = build_graph(filtered_subset)
    largest_subnetwork = get_largest_subnetwork(G)
    kept_subset = remove_disconnected_roads(G, largest_subnetwork, filtered_subset)
    kept_ids = {f.get("id") for f in kept_subset}
    logging.info(
        "Kept %d/%d features in largest component for current filter",
        len(kept_subset),
        len(filtered_subset),
    )

    # Persist: remove only the filtered features not in the largest component;
    # keep all non-filtered features unchanged.
    filtered_ids = {f.get("id") for f in filtered_subset}
    new_all_roads = []
    for f in all_roads:
        fid = f.get("id")
        if fid in filtered_ids:
            if fid in kept_ids:
                new_all_roads.append(f)
        else:
            # Not part of the filtered subset -> keep as-is
            new_all_roads.append(f)

    # Persist working copy (4326, no crs)
    updated_fc = {"type": "FeatureCollection", "features": new_all_roads}
    _save_fc_4326_no_crs(work_4326, updated_fc)

    # Re-export EPSG-specific file for downstream steps
    try:
        if epsg_input:
            transformed = transform_geojson(work_4326, 4326, epsg_input)
            # Ensure required fields for sensor-routing
            feats = transformed.get("features", [])
            _coerce_nodes_list(feats)
            _normalize_for_sensor_routing(feats)
            transformed = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_input}"},
                },
                "features": feats,
            }
            with open(
                os.path.join(in_dir, f"osm_data_{epsg_input}.geojson"),
                "w",
                encoding="utf-8",
            ) as f:
                geojson.dump(transformed, f)
    except Exception as e:
        logging.warning("Failed to write projected export: %s", e)

    # Return the currently-filtered view from the new working set
    visible = _filter_by_tags(new_all_roads, selected_roads)
    logging.info("Visible after largest-subnetwork: %d features", len(visible))
    return {"type": "FeatureCollection", "features": visible}


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    [Input(CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [
        State(JOB_ID_STORE_SHARED_ID, "data"),
        State(EPSG_STORE_SHARED_ID, "data"),
        State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    ],
    prevent_initial_call=True,
)
def reset_edits(n, job_id, epsg_input, selected_roads):
    if not n or not job_id:
        raise PreventUpdate

    in_dir, raw_4326, work_4326 = _paths(job_id)
    if not os.path.exists(raw_4326):
        logging.error("Missing baseline file: %s", raw_4326)
        raise PreventUpdate

    # Reset work from raw
    with (
        open(raw_4326, encoding="utf-8") as fsrc,
        open(work_4326, "w", encoding="utf-8") as fdst,
    ):
        fdst.write(fsrc.read())

    # Re-export EPSG-specific file
    try:
        if epsg_input:
            transformed = transform_geojson(work_4326, 4326, epsg_input)
            # Ensure required fields for sensor-routing
            feats = transformed.get("features", [])
            _coerce_nodes_list(feats)
            _normalize_for_sensor_routing(feats)
            transformed = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_input}"},
                },
                "features": feats,
            }
            with open(
                os.path.join(in_dir, f"osm_data_{epsg_input}.geojson"),
                "w",
                encoding="utf-8",
            ) as f:
                geojson.dump(transformed, f)
    except Exception as e:
        logging.warning("Failed to write projected export on reset: %s", e)

    # Return filtered raw view
    data = _load_fc(work_4326)
    all_roads = data.get("features", [])
    visible = _filter_by_tags(all_roads, selected_roads)
    return {"type": "FeatureCollection", "features": visible}


@callback(
    Output(SELECTION_COUNT_DIV_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Input(CLICKED_ROADS_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def _update_selection_badge(clicked):
    n = len(clicked) if clicked else 0
    return f"Selected: {n}"


@callback(
    Output(REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID, "disabled", allow_duplicate=True),
    Input(CLICKED_ROADS_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def _toggle_remove_disabled(clicked):
    return not bool(clicked)


# Select all / none tags
@callback(
    Output(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value", allow_duplicate=True),
    Input(TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    prevent_initial_call=True,
)
def tags_select_all_none(n_all, n_none):
    trig = ctx.triggered_id
    if trig == TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID:
        return list(osm_tags_mapping.keys())
    elif trig == TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID:
        return []
    raise PreventUpdate


# Open/close Reset confirmation modal
@callback(
    Output(
        RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID, "is_open", allow_duplicate=True
    ),
    Input(RESET_ROADS_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(CANCEL_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID, "is_open"),
    prevent_initial_call=True,
)
def toggle_reset_modal(n_open, n_cancel, n_confirm, is_open):
    if ctx.triggered_id in (
        RESET_ROADS_BUTTON_STREET_SELECTION_ID,
        CANCEL_RESET_BUTTON_STREET_SELECTION_ID,
        CONFIRM_RESET_BUTTON_STREET_SELECTION_ID,
    ):
        return (
            not is_open
            if ctx.triggered_id == RESET_ROADS_BUTTON_STREET_SELECTION_ID
            else False
        )
    raise PreventUpdate


# Clear selections after actions (use confirm-reset instead of reset-roads)
@callback(
    Output(CLICKED_ROADS_STORE_SHARED_ID, "data", allow_duplicate=True),
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout", allow_duplicate=True),
    Input(REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout"),
    prevent_initial_call=True,
)
def clear_selections(n_remove, n_largest, n_reset_confirm, hideout):
    if not any([n_remove, n_largest, n_reset_confirm]):
        raise PreventUpdate
    new_hideout = dict(hideout or {})
    new_hideout["selected"] = []
    return [], new_hideout


# Toast notifications
@callback(
    Output(ACTION_ALERT_ALERT_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Output(ACTION_ALERT_ALERT_STREET_SELECTION_ID, "color", allow_duplicate=True),
    Output(ACTION_ALERT_ALERT_STREET_SELECTION_ID, "is_open", allow_duplicate=True),
    Input(REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(UNDO_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(CLICKED_ROADS_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def show_action_alert(n_remove, n_largest, n_reset, n_undo, clicked):
    trig = ctx.triggered_id
    if trig == REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID:
        return f"Removed {len(clicked or [])} road(s).", "danger", True
    if trig == LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID:
        return "Kept largest subnetwork (within current filter).", "primary", True
    if trig == CONFIRM_RESET_BUTTON_STREET_SELECTION_ID:
        return "Edits reset to original OSM.", "secondary", True
    if trig == UNDO_BUTTON_BUTTON_STREET_SELECTION_ID:
        return "Last change undone.", "info", True
    raise PreventUpdate


# Undo: restore last snapshot from history
@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Input(UNDO_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    State(EPSG_STORE_SHARED_ID, "data"),
    State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    prevent_initial_call=True,
)
def undo_last(n, job_id, epsg_input, selected_roads):
    if not n or not job_id:
        raise PreventUpdate
    in_dir, raw_4326, work_4326 = _paths(job_id)
    hist_dir = os.path.join(in_dir, "history")
    if not os.path.isdir(hist_dir):
        raise PreventUpdate
    # pick newest snapshot
    snaps = sorted(
        (
            os.path.join(hist_dir, f)
            for f in os.listdir(hist_dir)
            if f.endswith(".geojson")
        ),
        key=os.path.getmtime,
        reverse=True,
    )
    if not snaps:
        raise PreventUpdate
    latest = snaps[0]
    try:
        shutil.copy2(latest, work_4326)
        if epsg_input:
            transformed = transform_geojson(work_4326, 4326, epsg_input)
            transformed = {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_input}"},
                },
                "features": transformed["features"],
            }
            with open(
                os.path.join(in_dir, f"osm_data_{epsg_input}.geojson"),
                "w",
                encoding="utf-8",
            ) as f:
                geojson.dump(transformed, f)
    except Exception as e:
        logging.warning("Undo failed: %s", e)
        raise PreventUpdate
    # return filtered view after undo
    data = _load_fc(work_4326)
    visible = _filter_by_tags(data.get("features", []), selected_roads)
    return {"type": "FeatureCollection", "features": visible}


# Persist chosen tags to session so the next page shows the same roads
@callback(
    Output(TAGS_LAST_SELECTION_STORE_SHARED_ID, "data", allow_duplicate=True),
    Input(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    prevent_initial_call=True,
)
def _persist_tags_selection(value):
    # If user clears, store "all" so map won't be empty on next page
    return value or list(osm_tags_mapping.keys())


# Update database with selected tags
@callback(
    Output(NONE_DIV_SHARED_ID, "children"),
    Input(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def update_tags_dropdown(tags, job_id):
    if tags is None:
        raise PreventUpdate

    try:
        DataBaseManager.update_column(job_id, {"selected_road_tags": tags})
        logging.info("Updated selected road tags with following tags: %s", tags)
    except JobNotFound:
        logging.error("Job with ID %s not found.", job_id)

    return no_update
