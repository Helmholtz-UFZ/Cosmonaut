"""Callbacks for map display, GeoJSON handling, road selection, and removal."""

import os
import glob
import json
import time
import logging
import dash_leaflet as dl
from dash import ctx
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from cosmonaut_app.config import WEB_WORK_DIR, osm_tags_mapping
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

from cosmonaut_app.flask_routes import app

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


@app.callback(
    Output("map", "children"),
    Input("tags-dropdown", "value"),
    State("job-id", "data"),
    Input("routing-complete", "data"),
    State("map", "children"),
    State("epsg-store", "data"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def update_map(selected_roads, job_id, routing_complete, current_children, epsg_input):
    logging.info("=== UPDATE_MAP CALLBACK START ===")
    logging.info("Trigger ID: %s", ctx.triggered_id)
    logging.info("Selected roads: %s", selected_roads)
    logging.info("Routing complete: %s", routing_complete)

    current_children = [
        child
        for child in current_children
        if not (isinstance(child, dict) and child.get("type") == "GeoJSON")
    ]
    logging.info("Cleaned map children, remaining: %d", len(current_children))

    if routing_complete:
        logging.info("=== ROUTING SECTION ===")
        logging.info("Processing routing solution for job: %s", job_id)

        job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
        solution_path = os.path.join(job_working_dir, "transient", "solution.json")

        start_transform = time.time()
        transformed_solution = transform_solution(
            solution_path, epsg_input, 4326, False
        )
        transform_time = time.time() - start_transform

        logging.info("Solution transformed in %.3fs", transform_time)

        geojson_layer = dl.GeoJSON(
            data=transformed_solution,
            options={"style": {"color": "blue", "weight": 5}},
            id="route-geojson",
        )
        current_children.append(geojson_layer)
        logging.info("Route GeoJSON layer added to map")

    elif ctx.triggered_id == "tags-dropdown" and selected_roads is not None and job_id:
        logging.info("=== OPTIMIZED TAG FILTERING SECTION ===")
        filter_start_time = time.time()

        logging.info("Converting German road types: %s", selected_roads)
        osm_highway_types = set()
        for german_type in selected_roads:
            if german_type in osm_tags_mapping:
                osm_highway_types.update(osm_tags_mapping[german_type])
            else:
                logging.warning("Unknown German road type: %s", german_type)

        logging.info("Mapped to OSM highway types: %s", list(osm_highway_types))

        geojson_path = os.path.join(
            f"cosmonaut_app/work_dir/{job_id}/input/*_4326.geojson"
        )
        timeout = 30
        start_wait = time.time()
        geojson_files = glob.glob(geojson_path)

        while not geojson_files and (time.time() - start_wait) < timeout:
            time.sleep(0.5)
            geojson_files = glob.glob(geojson_path)

        if not geojson_files:
            error_msg = f"No GeoJSON file found at: {geojson_path} after {timeout}s"
            logging.error(error_msg)
            raise FileNotFoundError(error_msg)

        load_start = time.time()
        with open(geojson_files[0], encoding="utf-8") as f:
            data = json.load(f)
        load_time = time.time() - load_start

        original_count = len(data["features"])
        logging.info("Loaded %d features in %.3fs", original_count, load_time)

        filter_start = time.time()
        filtered_features = [
            feature
            for feature in data["features"]
            if feature["properties"].get("highway") in osm_highway_types
        ]
        filter_time = time.time() - filter_start

        filtered_count = len(filtered_features)
        reduction_pct = (
            round((1 - filtered_count / original_count) * 100, 1)
            if original_count > 0
            else 0
        )

        logging.info(
            "Filtering completed in %.3fs: %d -> %d features (%.1f%% reduction)",
            filter_time,
            original_count,
            filtered_count,
            reduction_pct,
        )

        filtered_data = {"type": "FeatureCollection", "features": filtered_features}

        tooltip_start = time.time()
        for feature in filtered_features:
            highway_type = feature["properties"]["highway"]
            name = feature["properties"].get("name") or feature["properties"].get("ref")
            tracktype = feature["properties"].get("tracktype")

            if highway_type == "track" and tracktype:
                feature["properties"]["tooltip"] = (
                    f"{name}, {highway_type}, {tracktype}"
                )
            else:
                feature["properties"]["tooltip"] = f"{name}, {highway_type}"

        tooltip_time = time.time() - tooltip_start
        logging.info("Added tooltips in %.3fs", tooltip_time)

        geojson_layer = dl.GeoJSON(
            data=filtered_data,
            options={"style": style_handle},
            hideout=dict(selected=[], zoom=10),
            id="osm-geojson",
        )
        current_children.append(geojson_layer)

        total_time = time.time() - filter_start_time
        logging.info("Total filtering operation completed in %.3fs", total_time)

    elif ctx.triggered_id == "tags-dropdown" and not job_id:
        logging.warning("Tag dropdown triggered but no job ID available")

    logging.info(
        "=== UPDATE_MAP CALLBACK END === Returning %d children", len(current_children)
    )
    return current_children


@app.callback(
    Output("osm-geojson", "hideout", allow_duplicate=True),
    Input("osm-geojson", "n_clicks"),
    State("osm-geojson", "clickData"),
    State("osm-geojson", "hideout"),
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
    Output("clicked-roads", "data"),
    [Input("osm-geojson", "clickData")],
    [State("clicked-roads", "data")],
    prevent_initial_call=True,
)
def update_clicked_roads(clickData, clicked_roads):
    if clickData is None:
        raise PreventUpdate
    id = clickData["id"]
    if id not in clicked_roads:
        clicked_roads.append(id)
    return clicked_roads


@app.callback(
    Output("osm-geojson", "data"),
    [Input("remove-button", "n_clicks")],
    [
        State("clicked-roads", "data"),
        State("osm-geojson", "data"),
        State("job-id", "data"),
        State("epsg-store", "data"),
    ],
    prevent_initial_call=True,
)
def remove_selected(n, clicked_roads, original_data, job_id, epsg_input):
    if n is None or clicked_roads is None or original_data is None:
        raise PreventUpdate

    logging.info("EPSG-Input while largest subnetwork: %s", epsg_input)

    all_roads = original_data["features"]

    G = build_graph(all_roads)

    for road_id in clicked_roads:
        all_roads = remove_dead_roads(road_id, all_roads, G)

    largest_subnetwork = get_largest_subnetwork(G)
    all_roads = remove_disconnected_roads(G, largest_subnetwork, all_roads)

    filtered_data = {
        "type": "FeatureCollection",
        "features": all_roads,
    }

    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
    filtered_geojson_path = os.path.join(
        job_working_dir, "input", "osm_data_4326.geojson"
    )
    os.rename(
        os.path.join(job_working_dir, "input", "osm_data_4326.geojson"),
        os.path.join(job_working_dir, "input", "osm_data_4326_old.geojson"),
    )
    os.remove(os.path.join(job_working_dir, "input", f"osm_data_{epsg_input}.geojson"))
    with open(filtered_geojson_path, "w", encoding="utf-8") as f:
        geojson.dump(filtered_data, f)
        logging.info("Filtered data saved to %s", filtered_geojson_path)
    transformed_geojson = transform_geojson(filtered_geojson_path, 4326, epsg_input)
    transformed_geojson = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": f"urn:ogc:def:crs:EPSG::{epsg_input}"},
        },
        "features": transformed_geojson["features"],
    }

    transformed_geojson_path = os.path.join(
        job_working_dir, "input", "osm_data.geojson"
    )
    for file in os.listdir(os.path.join(job_working_dir, "input")):
        if file.endswith(".geojson") and file != "osm_data.geojson":
            os.remove(os.path.join(job_working_dir, "input", file))
    with open(transformed_geojson_path, "w", encoding="utf-8") as f:
        geojson.dump(transformed_geojson, f, indent=2)
        logging.info("Transformed data saved to %s", transformed_geojson_path)

    return filtered_data
