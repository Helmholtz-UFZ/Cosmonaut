"""Callbacks for map display, GeoJSON handling, road selection, and removal."""

import os
import glob
import json
import time
import logging
import re
import shutil
import dash_leaflet as dl
from dash import ctx
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from cosmonaut_app.config import WEB_WORK_DIR, osm_tags_mapping
from cosmonaut_app.constants.html_ids import (
    ACTION_ALERT_ALERT_STREET_SELECTION_ID,
    CANCEL_RESET_BUTTON_STREET_SELECTION_ID,
    CLICKED_ROADS_STORE_SHARED_ID,
    CONFIRM_RESET_BUTTON_STREET_SELECTION_ID,
    EPSG_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
    MAIN_MAP_COMPONENT_MAP_SHARED_ID,
    MANAGED_LAYERS_GROUP_MAP_SHARED_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID,
    RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID,
    RESET_ROADS_BUTTON_STREET_SELECTION_ID,
    ROUTE_GEOJSON_LAYER_MAP_SHARED_ID,
    ROUTE_LAYER_LAYER_MAP_SHARED_ID,
    ROUTING_COMPLETE_STORE_SHARED_ID,
    SELECTION_COUNT_DIV_STREET_SELECTION_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    TAGS_LAST_SELECTION_STORE_SHARED_ID,
    TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
    TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
    UNDO_BUTTON_BUTTON_STREET_SELECTION_ID,
)
from cosmonaut_app.transformation import (
    transform_solution,
    transform_geojson,
)
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_dead_roads,
    remove_disconnected_roads,
)

import geojson

from cosmonaut_app.app import app

# Define a JavaScript function for styling the GeoJSON features
from dash_extensions.javascript import assign

style_handle = assign(
    """
function(feature, context){
    const {selected, zoom} = context.hideout;
    const lineWeight = zoom ? Math.max(1, 5 / zoom) : 2;
    if(selected.includes(feature.id)){
        return {color: 'yellow', weight: lineWeight};
    }
    return {color: 'red', weight: lineWeight};
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
def update_map(selected_roads, job_id, routing_complete, current_children, epsg_input):
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
                    options=dict(style=dict(color="#0066ff", weight=5, opacity=0.9)),
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

        if not selected_roads:
            selected_roads = list(osm_tags_mapping.keys())
            logging.info("No selection; defaulting to all tags: %s", selected_roads)

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
            name = feature["properties"].get("name") or feature["properties"].get("ref")
            tracktype = feature["properties"].get("tracktype")
            feature["properties"]["tooltip"] = (
                f"{name}, {highway_type}, {tracktype}"
                if highway_type == "track" and tracktype
                else f"{name}, {highway_type}"
            )
        logging.info("Added tooltips in %.3fs", time.time() - tooltip_start)

        osm_layer = dl.GeoJSON(
            data=filtered_data,
            options={"style": style_handle},
            hideout=dict(selected=[], zoom=10),
            id=OSM_GEOJSON_LAYER_MAP_SHARED_ID,
            zoomToBounds=True,
        )
        new_layers.append(osm_layer)

        logging.info(
            "Total filtering operation completed in %.3fs",
            time.time() - filter_start_time,
        )

    elif ctx.triggered_id == TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID and not job_id:
        logging.warning("Tag dropdown triggered but no job ID available")

    # Add/replace our managed group once
    if new_layers:
        current_children.append(
            dl.LayerGroup(id=MANAGED_LAYERS_GROUP_MAP_SHARED_ID, children=new_layers)
        )

    logging.info(
        "=== UPDATE_MAP CALLBACK END === Returning %d children", len(current_children)
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


# Legacy remove callback (file-renaming version) disabled to avoid duplicate outputs.
def remove_selected_legacy_disabled(*_args, **_kwargs):
    return None


@app.callback(
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


@app.callback(
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
    def _is_in_filtered(f):
        return f in filtered_subset or f.get("id") in {
            fs.get("id") for fs in filtered_subset
        }

    # Build a fast lookup for ids in filtered subset (covers case of dict identity change)
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


@app.callback(
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


@app.callback(
    Output(SELECTION_COUNT_DIV_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Input(CLICKED_ROADS_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def _update_selection_badge(clicked):
    n = len(clicked) if clicked else 0
    return f"Selected: {n}"


@app.callback(
    Output(REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID, "disabled", allow_duplicate=True),
    Input(CLICKED_ROADS_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def _toggle_remove_disabled(clicked):
    return not bool(clicked)


# Select all / none tags
@app.callback(
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
@app.callback(
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
@app.callback(
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
@app.callback(
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


# Undo: restore last snapshot from history
@app.callback(
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
@app.callback(
    Output(TAGS_LAST_SELECTION_STORE_SHARED_ID, "data", allow_duplicate=True),
    Input(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    prevent_initial_call=True,
)
def _persist_tags_selection(value):
    # If user clears, store "all" so map won’t be empty on next page
    return value or list(osm_tags_mapping.keys())
