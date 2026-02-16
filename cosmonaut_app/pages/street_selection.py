"""Select and refine street networks for route planning.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This interactive page allows you to choose which OpenStreetMap roads should be
included in your navigation route. The page provides multiple selection tools to
help you build an optimal connected road network that covers your measurement
locations.

**Selection Features:**

- **Tag Filtering**: Select road types using dropdown filters organized by
  OSM highway classifications:
  - Motorway (highways and ramps)
  - Trunk road (expressways)
  - Primary road (major routes)
  - Secondary road (regional routes)
  - Tertiary road (local connectors)
  - Unclassified, Residential, Living street, Track

  Use "Select All" / "Select None" buttons for quick bulk operations.

- **Interactive Clicking**: Click individual road segments on the map to toggle
  them in or out of your route network. Selected roads are highlighted in a
  distinct color for visual feedback.

- **Network Tools**:
  - **Keep Largest**: Automatically select only the largest connected road network
    component, removing isolated segments
  - **Remove Disconnected**: Filter out road segments that aren't connected to
    your main network
  - **Reset**: Clear all selections and start over with a clean slate

The map displays selected roads with real-time visual feedback as you make
selections. Your goal is to create a connected network of streets that efficiently
covers your measurement locations while being traversable by your vehicle.

**Tips for Effective Selection:**
- Start by selecting appropriate road types for your vehicle and terrain
- Use "Keep Largest" to remove small disconnected segments automatically
- Verify all measurement points are reachable from your selected network
- Click individual segments to fine-tune network boundaries

When satisfied with your street selection, proceed to configure routing parameters
for the final route calculation.

# Notes (This section is for developer notes and will not appear in the user documentation.)

Street selection state is persisted to the job's work directory as GeoJSON.
Interactive callbacks use Dash Leaflet click events with feature_id tracking.
The StreetSelector class handles graph connectivity analysis and road network processing.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import (
    Input,
    Output,
    State,
    callback,
    ctx,
    dcc,
    html,
    no_update,
    register_page,
)
from dash.exceptions import PreventUpdate
from dash_extensions.javascript import assign

from cosmonaut_app.constants.general import (
    JOB_STATUS_PENDING,
    OSM_TAGS_MAPPING,
)
from cosmonaut_app.constants.html_ids import (
    CANCEL_RESET_BUTTON_STREET_SELECTION_ID,
    CLICKED_ROADS_STORE_SHARED_ID,
    CONFIRM_RESET_BUTTON_STREET_SELECTION_ID,
    JOB_ID_STORE_SHARED_ID,
    LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
    NEXT_BUTTON_STREET_SELECTION_ID,
    NONE_DIV_SHARED_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID,
    RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID,
    RESET_ROADS_BUTTON_STREET_SELECTION_ID,
    TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID,
    TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
    TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.layout import (
    build_url_step,
    create_card_input,
    create_map,
    create_reset_banner,
    create_reset_modal,
    hover_style_handle,
    page_container_split_layout,
    progress_footer,
    style_handle,
)
from cosmonaut_app.street_selector import StreetSelector

register_page(
    __name__,
    path_template="/job/<job_id>/street_selection",
    name="Street Selection",
    title="Street Selection",
    description="Select streets for the routing process.",
    dynamic=True,
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
    logging.info(job.model.membership_upload)

    card_body = []

    # Add reset banner if not PENDING
    if not is_active:
        card_body.append(create_reset_banner(job_id, status))

    # Add form components
    card_body.extend(
        [
            # Shared stores required by cross-page callbacks (map, routing, etc.)
            dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id, storage_type="session"),
            dcc.Store(
                id=CLICKED_ROADS_STORE_SHARED_ID, data=[], storage_type="session"
            ),
            html.P(
                "Select the desired roads in the map on the left. "
                "Click a road to mark it. Use 'Remove selected' to remove the "
                "marked roads. 'Keep largest' retains the largest connected "
                "subset within the currently selected road types.",
                className="text-muted",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Label(
                            "Road type filter",
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
                    {"label": tag, "value": tag} for tag in OSM_TAGS_MAPPING.keys()
                ],
                # Initialize with all tags so we immediately render the network once data exists
                value=list(OSM_TAGS_MAPPING.keys()),
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
                                    disabled=not is_active,
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-diagram-3 me-1"),
                                        "Keep largest",
                                    ],
                                    id=LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID,
                                    color="primary",
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

    sel = StreetSelector(job)
    initial_fc = sel.initial_fc(list(OSM_TAGS_MAPPING.keys()))

    extra_layer = dl.GeoJSON(
        id=OSM_GEOJSON_LAYER_MAP_SHARED_ID,
        data=initial_fc,
        options={"style": style_handle},
        hoverStyle=hover_style_handle,
        eventHandlers=dict(click=click_handler),
        hideout=dict(selected=[], zoom=10),
        zoomToBounds=bool(initial_fc["features"]),
    )

    map = create_map(job=job, extra_layers=[extra_layer])

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_split_layout(map, input_container)


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    [Input(REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [
        State(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout"),
        State(JOB_ID_STORE_SHARED_ID, "data"),
        State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    ],
    prevent_initial_call=True,
)
def remove_selected(
    n: Optional[int],
    hideout: Optional[Dict[str, Any]],
    job_id: Optional[str],
    selected_roads: Optional[List[str]],
) -> Dict[str, Any]:
    """Remove the currently selected roads and update the edited GeoJSON."""
    if not n or not job_id:
        raise PreventUpdate

    sel = StreetSelector(CosmonautJob(job_id=job_id))
    if not sel.is_pending():
        raise PreventUpdate

    clicked = (hideout or {})["selected"]
    if not clicked:
        raise PreventUpdate

    sel.remove_roads(clicked)
    sel.save()
    return sel.visible_fc(selected_roads)


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    [Input(LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [
        State(JOB_ID_STORE_SHARED_ID, "data"),
        State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    ],
    prevent_initial_call=True,
)
def keep_largest_subnetwork(
    n: Optional[int],
    job_id: Optional[str],
    selected_roads: Optional[List[str]],
) -> Dict[str, Any]:
    """Keep the largest connected subnetwork within the current tag filter."""
    if not n or not job_id:
        raise PreventUpdate

    sel = StreetSelector(CosmonautJob(job_id=job_id))
    if not sel.is_pending():
        raise PreventUpdate

    if not sel.keep_largest(selected_roads):
        raise PreventUpdate

    sel.save()
    return sel.visible_fc(selected_roads)


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    [Input(CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [
        State(JOB_ID_STORE_SHARED_ID, "data"),
        State(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    ],
    prevent_initial_call=True,
)
def reset_edits(
    n: Optional[int],
    job_id: Optional[str],
    selected_roads: Optional[List[str]],
) -> Dict[str, Any]:
    """Reset edits by restoring the edited file from the download baseline."""
    if not n or not job_id:
        raise PreventUpdate

    sel = StreetSelector(CosmonautJob(job_id=job_id))
    sel.reset()
    return sel.visible_fc(selected_roads)


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
    if trig == TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID:
        new_selection = list(OSM_TAGS_MAPPING.keys())
    elif trig == TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID:
        new_selection = []
    else:
        raise PreventUpdate

    if not job_id:
        return new_selection, {"type": "FeatureCollection", "features": []}

    sel = StreetSelector(CosmonautJob(job_id=job_id))
    return new_selection, sel.visible_fc(new_selection)


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


@callback(
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
) -> Dict[str, Any]:
    """Clear current selections after destructive operations for a clean state."""
    if not any([n_remove, n_largest, n_reset_confirm]):
        raise PreventUpdate
    new_hideout = dict(hideout or {})
    new_hideout["selected"] = []
    return new_hideout


@callback(
    Output(NONE_DIV_SHARED_ID, "children"),
    Input(TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID, "value"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def update_tags_dropdown(tags: Optional[List[str]], job_id: Optional[str]):
    """Persist selected tag values via the Job model."""
    if tags is None:
        raise PreventUpdate

    logging.info("Updated selected road tags with following tags: %s", tags)
    job = CosmonautJob(job_id=job_id)
    job.model.selected_road_tags = tags
    job.save()

    return no_update
