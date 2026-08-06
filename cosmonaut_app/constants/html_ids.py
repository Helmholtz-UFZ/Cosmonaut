"""HTML Element ID Constants.

This module centralizes all HTML element IDs used throughout the COSMONAUT application.

Naming Convention: <NAME>_<TYPE>_<PAGE>_ID
- NAME: Semantic name (e.g., START_JOB, EMAIL, SEARCH)
- TYPE: Element type (e.g., BUTTON, INPUT, DIV, STORE, DROPDOWN)
- PAGE: Page name or SHARED/COMMON for cross-page elements
- ID: Suffix for all ID constants

Example: START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"

Organization:
1. SHARED/COMMON IDs (stores, navigation, map)
2. Page-specific IDs (alphabetically by page)
   Within each section: grouped by TYPE, then alphabetically by NAME

# nocheck Comment Usage:
The `# nocheck` comment allows constants to bypass the HTML ID enforcement test.
**ONLY USE # nocheck FOR THESE TWO SPECIFIC CASES:**

1. IDs accessed via set_props() in error handling (not standard callbacks)
   Example: ERROR_MODAL_MESSAGE_SHARED_ID = "error-message"  # nocheck

2. IDs used exclusively for testing/automation (not in callbacks)
   Example: NEXT_BUTTON_ROUTING_PARAMS_ID = "next-button-routing-params-id"  # nocheck

**DO NOT USE # nocheck TO BYPASS THE TEST FOR OTHER REASONS!**
- If an ID is unused, delete it instead of adding # nocheck
- If an ID is only a visual container (no callback interaction), remove it
- The test exists to ensure all IDs serve a purpose

BEFORE ADDING # nocheck: Double-check that one of the two valid cases above applies.
If uncertain, ask for review rather than adding # nocheck to suppress the test.
"""

from dash.dash import _ID_LOCATION

# ============================================================================
# SHARED
# ============================================================================

# --- Buttons ---
MAP_LEGEND_TOGGLE_BUTTON_SHARED_ID = "map-legend-toggle-button-shared-id"
RESET_BUTTON_SHARED_ID = "reset-button-shared-id"
RESET_MODAL_CANCEL_BUTTON_SHARED_ID = "reset-modal-cancel-button-shared-id"
RESET_MODAL_CONFIRM_BUTTON_SHARED_ID = "reset-modal-confirm-button-shared-id"

# --- Collapses ---
MAP_LEGEND_COLLAPSE_SHARED_ID = "map-legend-collapse-shared-id"

# --- Intervals ---
MAP_INIT_INTERVAL_SHARED_ID = (
    "map-init-interval-shared-id"  # nocheck used as dcc.Interval only
)

# --- Layers ---
MEMBERSHIP_TILE_LAYER_MAP_ID = "membership-tile-layer-map-id"
OSM_GEOJSON_LAYER_MAP_SHARED_ID = "osm-geojson-layer-map-shared-id"
ROUTE_CASING_LAYER_MAP_ID = "route-casing-layer-map-id"
ROUTE_DIRECTION_DECORATOR_MAP_ID = "route-direction-decorator-map-id"
ROUTE_ENDPOINTS_GROUP_MAP_ID = "route-endpoints-group-map-id"
ROUTE_POLYLINE_LAYER_MAP_ID = "route-polyline-layer-map-id"

# --- Links ---
NEW_JOB_LINK_NAV_SHARED_ID = "new-job-link-nav-shared-id"
# Dash's internal routing location — page_container listens to this ID.
# Outputting to it triggers layout() and navigates without a full reload.
URL_SHARED_ID = _ID_LOCATION

# --- Maps ---
MAIN_MAP_COMPONENT_MAP_SHARED_ID = "main-map-component-map-shared-id"

# --- Modals ---
# used not in normal callbacks, but in error handling callbacks (set_props())
ERROR_MODAL_MESSAGE_SHARED_ID = "error-message"  # nocheck
ERROR_MODAL_SHARED_ID = "error-modal"  # nocheck
ERROR_MODAL_TITLE_SHARED_ID = "error-title"  # nocheck
LOADING_OVERLAY_MODAL_SHARED_ID = "loading-overlay-modal-shared-id"
RESET_MODAL_SHARED_ID = "reset-modal-shared-id"

# --- Codes ---
JOB_ID_KICKER_CODE_SHARED_ID = "job-id-kicker-code-shared-id"

# --- Navbars ---
NAVBAR_COLLAPSE_NAV_SHARED_ID = "navbar-collapse-nav-shared-id"
NAVBAR_TOGGLER_NAV_SHARED_ID = "navbar-toggler-nav-shared-id"

# --- Stores ---
CURRENT_JOB_ID_MAP_STORE_ID = "current-job-id-map-store-id"
JOB_ID_STORE_SHARED_ID = "job-id-store-shared-id"
STREETS_REFRESH_TRIGGER_STORE_SHARED_ID = "streets-refresh-trigger-store-shared-id"


# ============================================================================
# DATA_UPLOAD
# ============================================================================

# --- Buttons ---
DELETE_MEMBERSHIP_BUTTON_DATA_UPLOAD_ID = "delete-membership-button-data-upload-id"
DELETE_PREDICTOR_BUTTON_DATA_UPLOAD_ID = "delete-predictor-button-data-upload-id"
NEXT_BUTTON_DATA_UPLOAD_ID = "next-button-data-upload-id"

# --- Collapses ---
MEMBERSHIP_UPLOAD_COLLAPSE_DATA_UPLOAD_ID = "membership-upload-collapse-data-upload-id"
PREDICTOR_UPLOAD_COLLAPSE_DATA_UPLOAD_ID = "predictor-upload-collapse-data-upload-id"

# --- Divs ---
DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID = (
    "data-upload-epsg-helper-text-data-upload-id"
)
DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID = "data-upload-file-info-div-data-upload-id"
MEMBERSHIP_ERROR_DIV_DATA_UPLOAD_ID = "membership-error-div-data-upload-id"
PREDICTOR_ERROR_DIV_DATA_UPLOAD_ID = "predictor-error-div-data-upload-id"
PREDICTOR_FILE_INFO_DIV_DATA_UPLOAD_ID = "predictor-file-info-div-data-upload-id"
STREET_PROCESSING_STATUS_DIV_DATA_UPLOAD_ID = (
    "street-processing-status-div-data-upload-id"
)

# --- Icons ---
MEMBERSHIP_HELP_ICON_ID = (
    "membership-help-icon-data-upload-id"  # nocheck dbc.Tooltip target only
)
PREDICTOR_HELP_ICON_ID = (
    "predictor-help-icon-data-upload-id"  # nocheck dbc.Tooltip target only
)

# --- Inputs ---
DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID = "data-upload-epsg-input-data-upload-id"
DATA_UPLOAD_OPACITY_SLIDER_DATA_UPLOAD_ID = "data-upload-opacity-slider-data-upload-id"

# --- Intervals ---
STREET_PROCESSING_POLL_DATA_UPLOAD_ID = "street-processing-poll-data-upload-id"

# --- Stores ---
DATA_UPLOAD_INIT_STORE_DATA_UPLOAD_ID = "data-upload-init-store-data-upload-id"

# --- Uploads ---
DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID = (
    "data-upload-upload-component-data-upload-id"
)
PREDICTOR_UPLOAD_COMPONENT_DATA_UPLOAD_ID = "predictor-upload-component-data-upload-id"


# ============================================================================
# HOME
# ============================================================================

# --- Buttons ---
START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"


# ============================================================================
# JOB_MANAGER
# ============================================================================

# --- Buttons ---
CLEAN_UP_BUTTON_JOB_MANAGER_ID = "clean-up-button-job-manager-id"
DELETE_BUTTON_JOB_MANAGER_ID = "delete-button-job-manager-id"
REFRESH_BUTTON_JOB_MANAGER_ID = "refresh-button-job-manager-id"

# --- Tables ---
JOBS_TABLE_JOB_MANAGER_ID = "jobs-table-job-manager-id"

# ============================================================================
# ROUTE_COMPUTATION
# ============================================================================

# --- Buttons ---
CANCEL_BUTTON_ROUTE_COMPUTATION_ID = "cancel-button-route-computation-id"
NEXT_BUTTON_ROUTE_COMPUTATION_ID = "next-button-route-computation-id"
RESTART_BUTTON_ROUTE_COMPUTATION_ID = "restart-button-route-computation-id"
START_BUTTON_ROUTE_COMPUTATION_ID = "start-button-route-computation-id"

# --- Intervals ---
STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID = "status-poll-interval-route-computation-id"

# --- Spans ---
STATUS_BADGE_ROUTE_COMPUTATION_ID = "status-badge-route-computation-id"
TASK_STATUS_SPAN_ROUTE_COMPUTATION_ID = "task-status-span-route-computation-id"
WORKER_NAME_SPAN_ROUTE_COMPUTATION_ID = "worker-name-span-route-computation-id"
WORKER_STATUS_SPAN_ROUTE_COMPUTATION_ID = "worker-status-span-route-computation-id"

# --- Stores ---
UPDATE_TRIGGER_STORE_ROUTE_COMPUTATION_ID = "update-trigger-store-route-computation-id"

# --- Viewers ---
LOG_VIEWER_PRE_ROUTE_COMPUTATION_ID = "log-viewer-pre-route-computation-id"


# ============================================================================
# ROUTE_DOWNLOAD
# ============================================================================

# --- Divs ---
DOWNLOAD_URL_CODE_ROUTE_DOWNLOAD_ID = (
    "download-url-code-route-download-id"  # nocheck testing only
)

# --- Switches ---
REVERSE_ROUTE_SWITCH_ROUTE_DOWNLOAD_ID = "reverse-route-switch-route-download-id"


# ============================================================================
# ROUTING_PARAMS
# ============================================================================

# --- Buttons ---
ADVANCED_TOGGLE_ROUTING_PARAMS_ID = "advanced-toggle-routing-params-id"
# Needed for testing purposes
NEXT_BUTTON_ROUTING_PARAMS_ID = "next-button-routing-params-id"  # nocheck

# --- Collapses ---
ADVANCED_COLLAPSE_ROUTING_PARAMS_ID = "advanced-collapse-routing-params-id"


# ============================================================================
# STREET_SELECTION
# ============================================================================

# --- Alerts ---
STREET_PROCESSING_ALERT_STREET_SELECTION_ID = (
    "street-processing-alert-street-selection-id"
)

# --- Badges ---
SELECTED_BADGE_STREET_SELECTION_ID = "selected-badge-street-selection-id"

# --- Buttons ---
CANCEL_RESET_BUTTON_STREET_SELECTION_ID = "cancel-reset-button-street-selection-id"
CLEAR_REMOVED_BUTTON_STREET_SELECTION_ID = "clear-removed-button-street-selection-id"
CONFIRM_RESET_BUTTON_STREET_SELECTION_ID = "confirm-reset-button-street-selection-id"
KEEP_LARGEST_HINT_STREET_SELECTION_ID = "keep-largest-hint-street-selection-id"
LARGEST_BUTTON_STREET_SELECTION_ID = "largest-button-street-selection-id"
# Needed for testing purposes
NEXT_BUTTON_STREET_SELECTION_ID = "next-button-street-selection-id"  # nocheck
REMOVE_BUTTON_STREET_SELECTION_ID = "remove-button-street-selection-id"
RESET_ROADS_BUTTON_STREET_SELECTION_ID = "reset-roads-button-street-selection-id"
TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID = (
    "tags-select-all-button-street-selection-id"
)
TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID = (
    "tags-select-none-button-street-selection-id"
)

# --- Checklists ---
TRACK_GRADES_CHECKLIST_STREET_SELECTION_ID = (
    "track-grades-checklist-street-selection-id"
)

# --- Collapses ---
TRACK_GRADES_COLLAPSE_STREET_SELECTION_ID = "track-grades-collapse-street-selection-id"

# --- Divs ---
REMOVED_ROADS_LIST_DIV_STREET_SELECTION_ID = (
    "removed-roads-list-div-street-selection-id"
)

# --- Dropdowns ---
TAGS_DROPDOWN_STREET_SELECTION_ID = "tags-dropdown-street-selection-id"

# --- Intervals ---
STREET_PROCESSING_POLL_STREET_SELECTION_ID = (
    "street-processing-poll-street-selection-id"
)

# --- Modals ---
RESET_CONFIRM_MODAL_STREET_SELECTION_ID = "reset-confirm-modal-street-selection-id"


# ============================================================================
# USER_INFO
# ============================================================================

# --- Buttons ---
NEXT_BUTTON_USER_INFO_ID = "next-button-user-info-id"

# --- Collapses ---
EMAIL_VISIBILITY_NOTICE_COLLAPSE_USER_INFO_ID = (
    "email-visibility-notice-collapse-user-info-id"
)

# --- Divs ---
EMAIL_HELPER_TEXT_USER_INFO_ID = "email-helper-text-user-info-id"

# --- Inputs ---
EMAIL_INPUT_USER_INFO_ID = "email-input-user-info-id"
