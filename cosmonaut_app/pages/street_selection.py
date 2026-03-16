"""Select and refine street networks for route planning.

# User documentation (This section is for user documentation and will appear in the user documentation.)

This interactive page allows you to choose which OpenStreetMap roads should be
included in your navigation route. Every change you make is **immediately
persisted** — if you leave the page and come back, your selections are
preserved exactly as you left them.

**Selection Features:**

- **Tag Filtering**: Toggle road types on or off using the switches. Roads of
  a disabled type are removed from the working network and will not appear on
  any other page or in the final route. Re-enabling a type brings those roads
  back from the original OSM download. Available classifications:

  - Motorway (highways and ramps)
  - Trunk road (expressways)
  - Primary road (major routes)
  - Secondary road (regional routes)
  - Tertiary road (local connectors)
  - Unclassified, Residential, Living street, Track

  Use "Select All" / "Select None" buttons for quick bulk operations.

- **Interactive Clicking**: Click individual road segments on the map to mark
  them for removal. Marked roads are highlighted in a distinct color for
  visual feedback. Press "Remove selected" to permanently delete them.

- **Network Tools**:
  - **Keep Largest**: Retain only the largest connected road network
    component, removing isolated segments. This acts as a toggle — any
    subsequent edit (tag change, road removal) automatically resets it so
    that previously disconnected roads reappear for further editing.
  - **Reset**: Clear all selections, deletions, and filters, restoring the
    full original OSM download.

The map displays the current working network with real-time visual feedback.
Your goal is to create a connected network of streets that efficiently covers
your measurement locations while being traversable by your vehicle.

**Tips for Effective Selection:**

- Start by disabling road types that are unsuitable for your vehicle
- Remove individual problematic segments by clicking and removing
- Use "Keep Largest" as a final check to ensure network connectivity
- Verify all measurement points are reachable from your selected network

When satisfied with your street selection, proceed to configure routing
parameters for the final route calculation.

# Notes (This section is for developer notes and will not appear in the user documentation.)

Street selection state is persisted to ``street_edits.json`` in the job's
work directory. The file records removed road IDs, selected tag filters, and
a boolean flag for keep-largest. Every edit re-derives
``osm_data_edited.geojson`` and ``osm_data_transformed.geojson`` from the
immutable ``osm_data_download.geojson`` via :meth:`StreetSelector.apply_edits`.

Interactive callbacks use Dash Leaflet click events with feature_id tracking.
The StreetSelector class handles graph connectivity analysis and road network
processing.
"""

import logging
from typing import Any, Dict, List, Optional

import dash_bootstrap_components as dbc
from dash import (
    ALL,
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

from cosmonaut_app.constants.general import (
    JOB_STATUS_PENDING,
    OSM_TAGS_MAPPING,
)
from cosmonaut_app.constants.html_ids import (
    CANCEL_RESET_BUTTON_STREET_SELECTION_ID,
    CLEAR_REMOVED_BUTTON_STREET_SELECTION_ID,
    CLICKED_ROADS_STORE_SHARED_ID,
    CONFIRM_RESET_BUTTON_STREET_SELECTION_ID,
    JOB_ID_STORE_SHARED_ID,
    KEEP_LARGEST_HINT_STREET_SELECTION_ID,
    LARGEST_BUTTON_STREET_SELECTION_ID,
    NEXT_BUTTON_STREET_SELECTION_ID,
    OSM_GEOJSON_LAYER_MAP_SHARED_ID,
    REMOVE_BUTTON_STREET_SELECTION_ID,
    REMOVED_ROADS_LIST_DIV_STREET_SELECTION_ID,
    RESET_CONFIRM_MODAL_STREET_SELECTION_ID,
    RESET_ROADS_BUTTON_STREET_SELECTION_ID,
    STREET_PROCESSING_ALERT_STREET_SELECTION_ID,
    STREET_PROCESSING_POLL_STREET_SELECTION_ID,
    TAGS_DROPDOWN_STREET_SELECTION_ID,
    TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
    TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID,
    URL_SHARED_ID,
)
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.layout import (
    build_url_step,
    create_card_input,
    create_reset_banner,
    create_reset_modal,
    page_container_fullscreen_layout,
    progress_footer,
)
from cosmonaut_app.street_selector import StreetSelector

log = logging.getLogger(__name__)

# Height for ~5 list items before scrolling
_REMOVED_LIST_MAX_HEIGHT = "12rem"


def _build_keep_largest_hint(keep_largest: bool) -> list:
    """Build the connectivity hint content based on keep_largest state."""
    if keep_largest:
        return [
            html.I(className="bi bi-check-circle-fill me-1"),
            "Largest road network kept",
        ]
    return [
        html.I(className="bi bi-exclamation-triangle-fill me-1"),
        "Road network might be disconnected",
    ]


def _build_removed_roads_list(removed_info: list[dict], is_active: bool) -> list:
    """Build ListGroup items for the removed roads panel."""
    if not removed_info:
        return [
            dbc.ListGroupItem(
                "No roads removed", className="text-muted fst-italic", disabled=True
            )
        ]
    items = []
    for road in removed_info:
        items.append(
            dbc.ListGroupItem(
                [
                    html.Span(road["label"], className="flex-grow-1"),
                    dbc.Button(
                        html.I(className="bi bi-x-lg"),
                        # Dynamic IDs for per-road restore buttons
                        id={"type": "restore-road-btn", "index": road["id"]},  # nocheck
                        size="sm",
                        color="link",
                        className="p-0 ms-2 text-danger",
                        disabled=not is_active,
                    ),
                ],
                className="d-flex align-items-center py-1 px-2",
            )
        )
    return items


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
        A composed layout with controls for street editing.
    """
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()
    is_active = status == JOB_STATUS_PENDING

    log.info(f"Street selection layout for job {job_id}")
    log.debug(f"Job {job_id} membership_upload: {job.model.membership_upload}")

    # Gate on street processing status
    sp_status = job.get_street_processing_status()
    if sp_status == "RUNNING":
        return _street_processing_wait_layout(job_id)
    elif sp_status == "FAILED":
        return _street_processing_failed_layout(job_id)

    sel = StreetSelector(job)

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
                "subset of the current road network.",
                className="text-muted",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Label(
                            "Road type filter",
                            html_for=TAGS_DROPDOWN_STREET_SELECTION_ID,
                            className="mt-2",
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        dbc.ButtonGroup(
                            [
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-check-all me-1"),
                                        "Select all",
                                    ],
                                    id=TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID,
                                    size="sm",
                                    color="link",
                                    disabled=not is_active,
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-x-circle me-1"),
                                        "Select none",
                                    ],
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
                id=TAGS_DROPDOWN_STREET_SELECTION_ID,
                options=[
                    {"label": tag, "value": tag} for tag in OSM_TAGS_MAPPING.keys()
                ],
                value=sel.selected_road_tags,
                switch=True,
                inline=True,
                input_class_name="form-check-input"
                if is_active
                else "form-check-input disabled",
                className="" if is_active else "pe-none opacity-50",
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
                                    id=REMOVE_BUTTON_STREET_SELECTION_ID,
                                    color="danger",
                                    disabled=not is_active,
                                ),
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-diagram-3 me-1"),
                                        "Keep largest",
                                    ],
                                    id=LARGEST_BUTTON_STREET_SELECTION_ID,
                                    color="primary",
                                    disabled=not is_active or sel.keep_largest_applied,
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
            # Removed roads panel
            dbc.Label("Removed roads", className="mt-3 mb-1"),
            html.Div(
                dbc.ListGroup(
                    _build_removed_roads_list(sel.get_removed_roads_info(), is_active),
                    flush=True,
                ),
                id=REMOVED_ROADS_LIST_DIV_STREET_SELECTION_ID,
                className="overflow-auto border rounded",
                # style needed: dynamic max-height from variable, no Bootstrap equivalent
                style={"max-height": _REMOVED_LIST_MAX_HEIGHT},
            ),
            dbc.Button(
                [
                    html.I(className="bi bi-trash me-1"),
                    "Clear all",
                ],
                id=CLEAR_REMOVED_BUTTON_STREET_SELECTION_ID,
                size="sm",
                color="link",
                className="mt-1 p-0",
                disabled=not is_active or not sel.removed_roads,
            ),
            # Connectivity hint
            html.Div(
                html.Small(
                    _build_keep_largest_hint(sel.keep_largest_applied),
                    className="text-success"
                    if sel.keep_largest_applied
                    else "text-warning",
                ),
                id=KEEP_LARGEST_HINT_STREET_SELECTION_ID,
                className="mt-3",
            ),
            dbc.Tooltip(
                "When active, only the largest connected road component is kept. "
                "Any edit (tag change, road removal) resets this filter so you "
                "can re-evaluate connectivity.",
                target=KEEP_LARGEST_HINT_STREET_SELECTION_ID,
                placement="bottom",
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
                id=RESET_CONFIRM_MODAL_STREET_SELECTION_ID,
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

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_fullscreen_layout(input_container)


def _street_processing_wait_layout(job_id):
    """Render a waiting layout while street processing is in progress."""
    card_body = [
        dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id, storage_type="session"),
        dcc.Store(id=CLICKED_ROADS_STORE_SHARED_ID, data=[], storage_type="session"),
        dbc.Alert(
            "Road network is being built, please wait...",
            id=STREET_PROCESSING_ALERT_STREET_SELECTION_ID,
            color="info",
        ),
        dcc.Interval(
            id=STREET_PROCESSING_POLL_STREET_SELECTION_ID,
            interval=3000,
            disabled=False,
        ),
    ]

    data_upload_path = build_url_step("data_upload", job_id)
    routing_params_path = build_url_step("routing_params", job_id)

    footer = progress_footer(
        prev_url=data_upload_path,
        next_url=routing_params_path,
        next_id=NEXT_BUTTON_STREET_SELECTION_ID,
        next_disabled=True,
    )

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_fullscreen_layout(input_container)


def _street_processing_failed_layout(job_id):
    """Render a failure layout when street processing has failed."""
    card_body = [
        dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id, storage_type="session"),
        dcc.Store(id=CLICKED_ROADS_STORE_SHARED_ID, data=[], storage_type="session"),
        dbc.Alert(
            "Road network construction failed. Please go back to Data Upload "
            "and re-upload your membership file. If the problem persists, "
            "contact the maintainer.",
            id=STREET_PROCESSING_ALERT_STREET_SELECTION_ID,
            color="danger",
        ),
    ]

    data_upload_path = build_url_step("data_upload", job_id)
    routing_params_path = build_url_step("routing_params", job_id)

    footer = progress_footer(
        prev_url=data_upload_path,
        next_url=routing_params_path,
        next_id=NEXT_BUTTON_STREET_SELECTION_ID,
        next_disabled=True,
    )

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_fullscreen_layout(input_container)


@callback(
    Output(STREET_PROCESSING_ALERT_STREET_SELECTION_ID, "children"),
    Output(STREET_PROCESSING_ALERT_STREET_SELECTION_ID, "color"),
    Output(STREET_PROCESSING_POLL_STREET_SELECTION_ID, "disabled"),
    Output(URL_SHARED_ID, "pathname", allow_duplicate=True),
    Input(STREET_PROCESSING_POLL_STREET_SELECTION_ID, "n_intervals"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def poll_street_processing_status(n_intervals, job_id):
    """Poll street processing and reload page when complete."""
    if not job_id:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    sp_status = job.get_street_processing_status()

    if sp_status == "COMPLETED":
        return (
            no_update,
            no_update,
            True,
            f"/job/{job_id}/street_selection",
        )
    elif sp_status == "FAILED":
        return (
            "Road network construction failed. Please go back to Data Upload "
            "and re-upload your membership file. If the problem persists, "
            "contact the maintainer.",
            "danger",
            True,
            no_update,
        )
    # Still running
    return (
        "Road network is being built, please wait...",
        "info",
        False,
        no_update,
    )


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Output(
        REMOVED_ROADS_LIST_DIV_STREET_SELECTION_ID, "children", allow_duplicate=True
    ),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "className", allow_duplicate=True),
    [Input(REMOVE_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [
        State(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "hideout"),
        State(JOB_ID_STORE_SHARED_ID, "data"),
    ],
    prevent_initial_call=True,
)
def remove_selected(
    n: Optional[int],
    hideout: Optional[Dict[str, Any]],
    job_id: Optional[str],
):
    """Remove the currently selected roads and update the edited GeoJSON."""
    if not n or not job_id:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    if job.get_status() != JOB_STATUS_PENDING:
        raise PreventUpdate

    clicked = (hideout or {})["selected"]
    if not clicked:
        raise PreventUpdate

    sel = StreetSelector(job)
    sel.remove_roads(clicked)
    list_group = dbc.ListGroup(
        _build_removed_roads_list(sel.get_removed_roads_info(), True), flush=True
    )
    hint = html.Small(
        _build_keep_largest_hint(sel.keep_largest_applied),
        className="text-success" if sel.keep_largest_applied else "text-warning",
    )
    return sel.visible_fc(), list_group, hint, "mt-3"


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "className", allow_duplicate=True),
    [Input(LARGEST_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [State(JOB_ID_STORE_SHARED_ID, "data")],
    prevent_initial_call=True,
)
def keep_largest_subnetwork(
    n: Optional[int],
    job_id: Optional[str],
):
    """Keep the largest connected subnetwork of the current road network."""
    if not n or not job_id:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    if job.get_status() != JOB_STATUS_PENDING:
        raise PreventUpdate

    sel = StreetSelector(job)
    if not sel.keep_largest():
        raise PreventUpdate

    hint = html.Small(
        _build_keep_largest_hint(True),
        className="text-success",
    )
    return sel.visible_fc(), hint, "mt-3"


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Output(TAGS_DROPDOWN_STREET_SELECTION_ID, "value", allow_duplicate=True),
    Output(
        REMOVED_ROADS_LIST_DIV_STREET_SELECTION_ID, "children", allow_duplicate=True
    ),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "className", allow_duplicate=True),
    [Input(CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks")],
    [State(JOB_ID_STORE_SHARED_ID, "data")],
    prevent_initial_call=True,
)
def reset_edits(
    n: Optional[int],
    job_id: Optional[str],
):
    """Reset edits by restoring all state to defaults."""
    if not n or not job_id:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    sel = StreetSelector(job)
    sel.reset()
    is_active = job.get_status() == JOB_STATUS_PENDING
    list_group = dbc.ListGroup(_build_removed_roads_list([], is_active), flush=True)
    hint = html.Small(
        _build_keep_largest_hint(False),
        className="text-warning",
    )
    return sel.visible_fc(), sel.selected_road_tags, list_group, hint, "mt-3"


@callback(
    Output(TAGS_DROPDOWN_STREET_SELECTION_ID, "value", allow_duplicate=True),
    Input(TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    prevent_initial_call=True,
)
def tags_select_all_none(
    n_all: Optional[int],
    n_none: Optional[int],
) -> List[str]:
    """Set checklist to all or none. The value change triggers update_tags_dropdown."""
    trig = ctx.triggered_id
    if trig == TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID:
        return list(OSM_TAGS_MAPPING.keys())
    if trig == TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID:
        return []
    raise PreventUpdate


@callback(
    Output(RESET_CONFIRM_MODAL_STREET_SELECTION_ID, "is_open", allow_duplicate=True),
    Input(RESET_ROADS_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(CANCEL_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(CONFIRM_RESET_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(RESET_CONFIRM_MODAL_STREET_SELECTION_ID, "is_open"),
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
    Input(REMOVE_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    Input(LARGEST_BUTTON_STREET_SELECTION_ID, "n_clicks"),
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
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "className", allow_duplicate=True),
    Input(TAGS_DROPDOWN_STREET_SELECTION_ID, "value"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def update_tags_dropdown(tags: Optional[List[str]], job_id: Optional[str]):
    """Persist selected tag values and refresh the map to match the filter."""
    if tags is None:
        raise PreventUpdate

    log.info(f"Job {job_id} road tags updated: {tags}")
    sel = StreetSelector(CosmonautJob(job_id=job_id))
    sel.update_tags(tags)
    hint = html.Small(
        _build_keep_largest_hint(sel.keep_largest_applied),
        className="text-success" if sel.keep_largest_applied else "text-warning",
    )
    return sel.visible_fc(), hint, "mt-3"


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Output(
        REMOVED_ROADS_LIST_DIV_STREET_SELECTION_ID, "children", allow_duplicate=True
    ),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "className", allow_duplicate=True),
    Input({"type": "restore-road-btn", "index": ALL}, "n_clicks"),  # nocheck
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def restore_single_road(n_clicks_list, job_id):
    """Restore a single road removed from the network."""
    if not any(n_clicks_list) or not job_id:
        raise PreventUpdate

    road_id = ctx.triggered_id["index"]
    job = CosmonautJob(job_id=job_id)
    sel = StreetSelector(job)
    sel.restore_road(road_id)

    removed_info = sel.get_removed_roads_info()
    is_active = job.get_status() == JOB_STATUS_PENDING
    list_group = dbc.ListGroup(
        _build_removed_roads_list(removed_info, is_active), flush=True
    )
    hint = html.Small(
        _build_keep_largest_hint(sel.keep_largest_applied),
        className="text-success" if sel.keep_largest_applied else "text-warning",
    )
    return sel.visible_fc(), list_group, hint, "mt-3"


@callback(
    Output(OSM_GEOJSON_LAYER_MAP_SHARED_ID, "data", allow_duplicate=True),
    Output(
        REMOVED_ROADS_LIST_DIV_STREET_SELECTION_ID, "children", allow_duplicate=True
    ),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "children", allow_duplicate=True),
    Output(KEEP_LARGEST_HINT_STREET_SELECTION_ID, "className", allow_duplicate=True),
    Input(CLEAR_REMOVED_BUTTON_STREET_SELECTION_ID, "n_clicks"),
    State(JOB_ID_STORE_SHARED_ID, "data"),
    prevent_initial_call=True,
)
def clear_all_removed_roads(n_clicks, job_id):
    """Clear the entire removed roads list and restore all roads."""
    if not n_clicks or not job_id:
        raise PreventUpdate

    job = CosmonautJob(job_id=job_id)
    sel = StreetSelector(job)
    sel.clear_removed_roads()

    is_active = job.get_status() == JOB_STATUS_PENDING
    list_group = dbc.ListGroup(_build_removed_roads_list([], is_active), flush=True)
    hint = html.Small(
        _build_keep_largest_hint(sel.keep_largest_applied),
        className="text-success" if sel.keep_largest_applied else "text-warning",
    )
    return sel.visible_fc(), list_group, hint, "mt-3"
