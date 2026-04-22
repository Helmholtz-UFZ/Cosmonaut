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
RESET_BUTTON_SHARED_ID = "reset-button-shared-id"
RESET_MODAL_CANCEL_BUTTON_SHARED_ID = "reset-modal-cancel-button-shared-id"
RESET_MODAL_CONFIRM_BUTTON_SHARED_ID = "reset-modal-confirm-button-shared-id"

# --- Intervals ---
MAP_INIT_INTERVAL_SHARED_ID = (
    "map-init-interval-shared-id"  # nocheck used as dcc.Interval only
)

# --- Layers ---
MEMBERSHIP_TILE_LAYER_MAP_ID = "membership-tile-layer-map-id"
OSM_GEOJSON_LAYER_MAP_SHARED_ID = "osm-geojson-layer-map-shared-id"
ROUTE_POLYLINE_LAYER_MAP_ID = "route-polyline-layer-map-id"

# --- Links ---
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
LOADING_OVERLAY_SHARED_ID = "loading-overlay-shared-id"
RESET_MODAL_SHARED_ID = "reset-modal-shared-id"

# --- Navbars ---
NAVBAR_COLLAPSE_NAV_SHARED_ID = "navbar-collapse-nav-shared-id"
NAVBAR_TOGGLER_NAV_SHARED_ID = "navbar-toggler-nav-shared-id"

# --- Stores ---
CLICKED_ROADS_STORE_SHARED_ID = (
    "clicked-roads-store-shared-id"  # nocheck used as dcc.Store only
)
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
# LOGS
# ============================================================================

# --- Buttons ---
REFRESH_BUTTON_LOGS_ID = "refresh-button-logs-id"

# --- Checklists ---
LIVE_MODE_CHECKLIST_LOGS_ID = "live-mode-checklist-logs-id"
PID_CHECKLIST_LOGS_ID = "pid-checklist-logs-id"

# --- DatePickers ---
LOG_DATE_PICKER_LOGS_ID = "log-date-picker-logs-id"

# --- Divs ---
LOG_OUTPUT_DIV_LOGS_ID = "log-output-div-logs-id"
TIME_ERROR_DIV_LOGS_ID = "time-error-div-logs-id"
TIME_INPUT_GROUP_LOGS_ID = "time-input-group-logs-id"

# --- Dropdowns ---
LOG_LEVELS_DROPDOWN_LOGS_ID = "log-levels-dropdown-logs-id"
MODULE_EXCLUDE_DROPDOWN_LOGS_ID = "module-exclude-dropdown-logs-id"

# --- Inputs ---
END_HOUR_INPUT_LOGS_ID = "end-hour-input-logs-id"
END_MINUTE_INPUT_LOGS_ID = "end-minute-input-logs-id"
LOG_PID_INPUT_LOGS_ID = "log-pid-input-logs-id"
START_HOUR_INPUT_LOGS_ID = "start-hour-input-logs-id"
START_MINUTE_INPUT_LOGS_ID = "start-minute-input-logs-id"

# --- Intervals ---
AUTO_POLL_INTERVAL_LOGS_ID = "auto-poll-interval-logs-id"


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

# --- Inputs ---
EMAIL_INPUT_USER_INFO_ID = "email-input-user-info-id"


# ============================================================================
# WORKER_MANAGEMENT
# ============================================================================

# --- Buttons ---
CANCEL_MODAL_CANCEL_BUTTON_WORKER_MANAGEMENT_ID = (
    "cancel-modal-cancel-button-worker-management-id"
)
CANCEL_MODAL_CONFIRM_BUTTON_WORKER_MANAGEMENT_ID = (
    "cancel-modal-confirm-button-worker-management-id"
)
KILL_MODAL_CANCEL_BUTTON_WORKER_MANAGEMENT_ID = (
    "kill-modal-cancel-button-worker-management-id"
)
KILL_MODAL_CONFIRM_BUTTON_WORKER_MANAGEMENT_ID = (
    "kill-modal-confirm-button-worker-management-id"
)
TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID = "test-task-button-worker-management-id"
WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID = "worker-cancel-btn-worker-management-id"
WORKER_KILL_BTN_WORKER_MANAGEMENT_ID = "worker-kill-btn-worker-management-id"
WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID = "worker-refresh-btn-worker-management-id"

# --- Divs ---
CANCEL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID = (
    "cancel-modal-task-info-div-worker-management-id"
)
KILL_MODAL_TASK_INFO_DIV_WORKER_MANAGEMENT_ID = (
    "kill-modal-task-info-div-worker-management-id"
)
WORKER_LAST_REFRESH_DIV_WORKER_MANAGEMENT_ID = (
    "worker-last-refresh-div-worker-management-id"
)
WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID = (
    "worker-management-dummy-component-worker-management-id"
)
WORKER_STATS_CARD_DIV_WORKER_MANAGEMENT_ID = (
    "worker-stats-card-div-worker-management-id"
)

# --- Modals ---
CANCEL_MODAL_WORKER_MANAGEMENT_ID = "cancel-modal-worker-management-id"
KILL_MODAL_WORKER_MANAGEMENT_ID = "kill-modal-worker-management-id"

# --- Tables ---
ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID = "active-tasks-table-worker-management-id"
RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID = "reserved-tasks-table-worker-management-id"
REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID = "revoked-tasks-table-worker-management-id"
SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID = (
    "scheduled-tasks-table-worker-management-id"
)
