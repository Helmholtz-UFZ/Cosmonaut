"""Select and refine street networks for route planning.

This interactive page allows you to choose which OpenStreetMap roads should be
included in your navigation route. The page provides multiple selection tools to
help you build an optimal connected road network that covers your measurement
locations.

**Selection Features:**

- **Tag Filtering**: Select road types using dropdown filters organized by
  German road classifications:
  - Autobahn (highways)
  - Bundesstraßen (federal roads)
  - Landstraße (country roads)
  - Kreisstraße (district roads)
  - Gemeindestraße (municipal roads)
  - Sonstige (other roads including residential, service, tracks)

  Use "Select All" / "Select None" buttons for quick bulk operations.

- **Interactive Clicking**: Click individual road segments on the map to toggle
  them in or out of your route network. Selected roads are highlighted in a
  distinct color for visual feedback.

- **Network Tools**:
  - **Keep Largest**: Automatically select only the largest connected road network
    component, removing isolated segments
  - **Remove Disconnected**: Filter out road segments that aren't connected to
    your main network
  - **Undo**: Revert your last selection action using snapshot-based history
  - **Reset**: Clear all selections and start over with a clean slate

The map displays selected roads with real-time visual feedback as you make
selections. Your goal is to create a connected network of streets that efficiently
covers your measurement locations while being traversable by your vehicle.

**Tips for Effective Selection:**
- Start by selecting appropriate road types for your vehicle and terrain
- Use "Keep Largest" to remove small disconnected segments automatically
- Verify all measurement points are reachable from your selected network
- Click individual segments to fine-tune network boundaries
- Use Undo if you make a mistake

When satisfied with your street selection, proceed to configure routing parameters
for the final route calculation.

NOTE: Street selection state is persisted to the job's work directory as GeoJSON.
Undo functionality uses snapshot files stored in work_dir/snapshots/. Interactive
callbacks use Dash Leaflet click events with feature_id tracking. The utils module
handles graph connectivity analysis and road network processing.
"""

import os
import json
import logging
import shutil  # required for undo
from typing import Any, Dict, List, Optional, Tuple
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
import dash_leaflet as dl
import dash_bootstrap_components as dbc
import geojson

from cosmonaut_app.config import osm_tags_mapping
from cosmonaut_app.constants import JOB_STATUS_PENDING
from cosmonaut_app.constants.html_ids import (
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
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
    TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
    UNDO_BUTTON_BUTTON_STREET_SELECTION_ID,
    NEXT_BUTTON_STREET_SELECTION_ID,
)
from cosmonaut_app.db_manager import DataBaseManager, JobNotFound
from cosmonaut_app.road_network_utils import (
    build_graph,
    get_largest_subnetwork,
    remove_dead_roads,
    remove_disconnected_roads,
)
from cosmonaut_app.transformation import transform_geojson
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.layout import (
    create_map,
    page_container_split_layout,
    create_card_input,
    progress_footer,
    build_url_step,
    style_handle,  # reuse dynamic style so colors stay consistent after filtering
    create_reset_banner,
    create_reset_modal,
)
from cosmonaut_app.utils.street_selection_utils import (
    initial_features,
    paths as _paths,
    ensure_feature_ids as _ensure_feature_ids,
    filter_by_tags as _filter_by_tags,
    load_fc as _load_fc,
    coerce_nodes_list as _coerce_nodes_list,
    safe_projected_export as _safe_export,
    save_fc_4326_no_crs as _save,
    snapshot_work_copy as _snapshot,
)

register_page(
    __name__,
    path_template="/job/<job_id>/street_selection",
    name="Street Selection",
    title="Street Selection",
    description="Select streets for the routing process.",
    dynamic=True,
)


def layout(job_id: str):
    """Build the Street Selection UI.

    Args:
        job_id: Current job identifier from the URL.

    Returns:
        A composed layout with the map on the left and controls on the right.
    """
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()
    is_active = status == JOB_STATUS_PENDING

    logging.info(f"Street selection layout called with job_id={job_id}")
    logging.info(job.model.classification_upload)

    card_body = []

    # Add reset banner if not PENDING
    if not is_active:
        card_body.append(create_reset_banner(job_id, status))

    # Add form components
    card_body.extend(
        [
            # Shared stores required by cross-page callbacks (map, routing, etc.)
            dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id, storage_type="session"),
            dcc.Store(id=EPSG_STORE_SHARED_ID, storage_type="session"),
            dcc.Store(
                id=CLICKED_ROADS_STORE_SHARED_ID, data=[], storage_type="session"
            ),
            # Local store to remember last tag selection
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
                                    disabled=not is_active,
                                ),
                                dbc.Button(
                                    "Select none",
                                    id=TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
                                    size="sm",
                                    color="link",
                                    disabled=not is_active,
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
                options=[
                    {"label": tag, "value": tag} for tag in osm_tags_mapping.keys()
                ],
                # Initialize with all tags so we immediately render the network once data exists
                value=list(osm_tags_mapping.keys()),
                switch=True,
                inline=True,
                input_class_name="form-check-input"
                if is_active
                else "form-check-input disabled",
                style={"pointer-events": "none", "opacity": "0.6"}
                if not is_active
                else {},
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
                                    disabled=not is_active,
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-diagram-3 me-1"),
                                        "Keep largest",
                                    ],
                                    id=LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
                                    color="primary",
                                    outline=True,
                                    disabled=not is_active,
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
                                    disabled=not is_active,
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-arrow-90deg-left me-1"),
                                        "Undo",
                                    ],
                                    id=UNDO_BUTTON_BUTTON_STREET_SELECTION_ID,
                                    color="secondary",
                                    outline=True,
                                    disabled=not is_active,
                                ),
                            ],
                            size="md",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.Badge(
                            "Selected: 0",
                            color="info",
                            className="ms-2",
                        ),
                        width="auto",
                        className="d-flex align-items-center",
                    ),
                ],
                className="g-2 align-items-center mt-2",
            ),
            # Reset confirmation modal (for reset edits button)
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
    )

    # Add job reset modal
    card_body.append(create_reset_modal())

    user_info_path = build_url_step("data_upload", job_id)
    street_selection_path = build_url_step("routing_params", job_id)

    footer = progress_footer(
        prev_url=user_info_path,
        next_url=street_selection_path,
        next_id=NEXT_BUTTON_STREET_SELECTION_ID,
        next_disabled=False,
    )

    initial_fc = initial_features(job_id)

    # TEMPORARY DIAGNOSTIC LOGGING - TODO: REMOVE
    logging.info(f"initial_fc type: {type(initial_fc)}")
    logging.info(
        f"initial_fc keys: {initial_fc.keys() if isinstance(initial_fc, dict) else 'NOT A DICT'}"
    )
    logging.info(f"Number of features: {len(initial_fc.get('features', []))}")
    if initial_fc.get("features"):
        first_feature = initial_fc["features"][0]
        logging.info(f"First feature keys: {first_feature.keys()}")
        logging.info(f"First feature id: {first_feature.get('id')}")
        logging.info(f"First feature id type: {type(first_feature.get('id'))}")
        # Check all features have IDs
        features_without_ids = [
            i for i, f in enumerate(initial_fc.get("features", [])) if "id" not in f
        ]
        if features_without_ids:
            logging.error(
                f"Features missing IDs at indices: {features_without_ids[:10]}"
            )
        else:
            logging.info("All features have IDs")
    # END TEMPORARY LOGGING

    extra_layer = dl.GeoJSON(
        id=OSM_GEOJSON_LAYER_MAP_SHARED_ID,
        data=initial_fc,
        # Use same dynamic style function used after first interaction for consistency
        options={"style": style_handle},
        hideout=dict(selected=[], zoom=10),
        # Set zoomToBounds on initial layout; later we will disable on updates
        zoomToBounds=True if initial_fc.get("features") else False,
    )

    map = create_map(job=job, extra_layers=[extra_layer])

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_split_layout(map, input_container)


"""
Callbacks with business logic are intentionally kept minimal here. Complex
operations (filtering, id assignment, normalization, exports) live in
cosmonaut_app/utils/street_selection_utils.py and shared map callback lives in layout.
"""


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
def remove_selected(
    n: Optional[int],
    clicked_roads: Optional[List[int]],
    job_id: Optional[str],
    epsg_input: Optional[int | str],
    selected_roads: Optional[List[str]],
) -> Dict[str, Any]:
    """Remove the currently selected roads and update the working GeoJSON.

    Args:
        n: Click count for the Remove button.
        clicked_roads: Road ids selected on the map.
        job_id: Current job id.
        epsg_input: Optional target EPSG code for projected export.
        selected_roads: Current tag selection used to filter visible features.

    Returns:
        FeatureCollection dict with filtered visible features after removal.
    """
    if not n or not job_id:
        raise PreventUpdate

    # Prevent interaction if job is not in PENDING state
    job = CosmonautJob(job_id=job_id)
    if job.get_status() != JOB_STATUS_PENDING:
        logging.warning(f"Remove selected prevented: job {job_id} not in PENDING state")
        raise PreventUpdate

    if not clicked_roads:
        logging.info("No roads selected; nothing to remove.")
        raise PreventUpdate

    in_dir, raw_4326, work_4326 = _paths(job_id)
    # snapshot handled by lower-level utils in dedicated service (left out here for simplicity)
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

    _snapshot(in_dir, work_4326)
    data = _load_fc(work_4326)
    all_roads = data.get("features", [])
    _ensure_feature_ids(all_roads)
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
    _save(work_4326, updated_fc)

    # Re-export projected file (wrapped helper handles internal errors)
    _safe_export(in_dir, work_4326, epsg_input)

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
def keep_largest_subnetwork(
    n: Optional[int],
    job_id: Optional[str],
    epsg_input: Optional[int | str],
    selected_roads: Optional[List[str]],
) -> Dict[str, Any]:
    """Keep the largest connected subnetwork within the current tag filter.

    Returns a filtered FeatureCollection representing the updated working set.
    """
    if not n or not job_id:
        raise PreventUpdate

    # Prevent interaction if job is not in PENDING state
    job = CosmonautJob(job_id=job_id)
    if job.get_status() != JOB_STATUS_PENDING:
        logging.warning(f"Keep largest prevented: job {job_id} not in PENDING state")
        raise PreventUpdate

    in_dir, raw_4326, work_4326 = _paths(job_id)
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

    _snapshot(in_dir, work_4326)
    data = _load_fc(work_4326)
    all_roads = data.get("features", [])
    _ensure_feature_ids(all_roads)
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
    _save(work_4326, updated_fc)

    # Re-export projected file
    _safe_export(in_dir, work_4326, epsg_input)

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
def reset_edits(
    n: Optional[int],
    job_id: Optional[str],
    epsg_input: Optional[int | str],
    selected_roads: Optional[List[str]],
) -> Dict[str, Any]:
    """Reset edits by restoring the working file from the raw baseline.

    Returns the baseline filtered by the current tag selection.
    """
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

    # Re-export projected file
    _safe_export(in_dir, work_4326, epsg_input)

    # Return filtered raw view
    data = _load_fc(work_4326)
    all_roads = data.get("features", [])
    _ensure_feature_ids(all_roads)
    visible = _filter_by_tags(all_roads, selected_roads)
    return {"type": "FeatureCollection", "features": visible}


# Select all / none tags
@callback(
    Output(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value", allow_duplicate=True),
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Input(TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    State(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def tags_select_all_none(
    n_all: Optional[int],
    n_none: Optional[int],
    job_id: Optional[str],
    current_geojson: Optional[Dict[str, Any]],
) -> Tuple[List[str], Dict[str, Any]]:
    """Update tag selection to all or none and refresh the visible FeatureCollection."""
    trig = ctx.triggered_id
    if trig not in (
        TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
        TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
    ):
        raise PreventUpdate

    # Determine new selection list
    if trig == TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID:
        new_selection = list(osm_tags_mapping.keys())
    else:
        new_selection = []  # show no roads

    # Reload source data (raw or work) to apply fresh filter; avoids cumulative filtering artifacts
    initial_fc = {"type": "FeatureCollection", "features": []}
    try:
        if job_id:
            in_dir, raw_path, work_path = _paths(job_id)
            source = work_path if os.path.exists(work_path) else raw_path
            if source and os.path.exists(source):
                with open(source, encoding="utf-8") as f:
                    data = json.load(f)
                feats = data.get("features", [])
                _ensure_feature_ids(feats)
                feats = _filter_by_tags(feats, new_selection)
                for feat in feats:
                    p = feat.setdefault("properties", {})
                    name = p.get("name") or p.get("ref")
                    hw = p.get("highway")
                    p["tooltip"] = (
                        f"{name}, {hw}" if name else f"{hw}" if hw else name or ""
                    )
                initial_fc = {"type": "FeatureCollection", "features": feats}
    except Exception as e:
        logging.warning("Tag select all/none preload failed: %s", e)

    return new_selection, initial_fc


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
def toggle_reset_modal(
    n_open: Optional[int],
    n_cancel: Optional[int],
    n_confirm: Optional[int],
    is_open: Optional[bool],
) -> bool:
    """Open/close the reset confirmation modal based on the triggering control."""
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
def clear_selections(
    n_remove: Optional[int],
    n_largest: Optional[int],
    n_reset_confirm: Optional[int],
    hideout: Optional[Dict[str, Any]],
) -> Tuple[List[int], Dict[str, Any]]:
    """Clear current selections after destructive operations for a clean state."""
    if not any([n_remove, n_largest, n_reset_confirm]):
        raise PreventUpdate
    new_hideout = dict(hideout or {})
    new_hideout["selected"] = []
    return [], new_hideout


# Undo: restore last snapshot from history
@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Input(UNDO_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    State(EPSG_STORE_SHARED_ID, "data"),
    State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    prevent_initial_call=True,
)
def undo_last(
    n: Optional[int],
    job_id: Optional[str],
    epsg_input: Optional[int | str],
    selected_roads: Optional[List[str]],
) -> Dict[str, Any]:
    """Restore the most recent snapshot from history and re-filter by tags."""
    if not n or not job_id:
        raise PreventUpdate

    # Prevent interaction if job is not in PENDING state
    job = CosmonautJob(job_id=job_id)
    if job.get_status() != JOB_STATUS_PENDING:
        logging.warning(f"Undo prevented: job {job_id} not in PENDING state")
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
    data = _load_fc(work_4326)
    visible = _filter_by_tags(data.get("features", []), selected_roads)
    return {"type": "FeatureCollection", "features": visible}


# Update database with selected tags
@callback(
    Output(NONE_DIV_SHARED_ID, "children"),
    Input(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def update_tags_dropdown(tags: Optional[List[str]], job_id: Optional[str]):
    """Persist selected tag values to the database.

    Returns no_update; the effect is stored server-side.
    """
    if tags is None:
        raise PreventUpdate

    try:
        DataBaseManager.update_column(job_id, {"selected_road_tags": tags})
        logging.info("Updated selected road tags with following tags: %s", tags)
    except JobNotFound:
        logging.error("Job with ID %s not found.", job_id)

    return no_update
