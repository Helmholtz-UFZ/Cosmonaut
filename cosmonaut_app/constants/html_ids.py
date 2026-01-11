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
"""

# ============================================================================
# SHARED/COMMON IDS
# ============================================================================

# --- Stores ---
CLICKED_ROADS_STORE_SHARED_ID = "clicked-roads-store-shared-id"
EPSG_STORE_SHARED_ID = "epsg-store-shared-id"
JOB_ID_STORE_SHARED_ID = "job-id-store-shared-id"

# --- Navigation ---
NAVBAR_COLLAPSE_NAV_SHARED_ID = "navbar-collapse-nav-shared-id"
NAVBAR_TOGGLER_NAV_SHARED_ID = "navbar-toggler-nav-shared-id"
SEARCH_BUTTON_NAV_SHARED_ID = "search-button-nav-shared-id"
SEARCH_INPUT_NAV_SHARED_ID = "search-input-nav-shared-id"
SEARCH_RESULTS_DIV_NAV_SHARED_ID = "search-results-div-nav-shared-id"
URL_SHARED_ID = "url-shared-id"

# --- Utility ---
NONE_DIV_SHARED_ID = "none-div-shared-id"
# --- Map Elements ---
MAIN_MAP_COMPONENT_MAP_SHARED_ID = "main-map-component-map-shared-id"
OSM_GEOJSON_LAYER_MAP_SHARED_ID = "osm-geojson-layer-map-shared-id"

# --- Modals ---
# used not in normal callbacks, but in error handling callbacks (set_props())
ERROR_MODAL_TITLE_SHARED_ID = "error-title"  # nocheck
ERROR_MODAL_MESSAGE_SHARED_ID = "error-message"  # nocheck
ERROR_MODAL_SHARED_ID = "error-modal"  # nocheck
LOADING_OVERLAY_SHARED_ID = "loading-overlay-shared-id"

# --- Reset Components (Shared) ---
RESET_BANNER_ALERT_SHARED_ID = "reset-banner-alert-shared-id"
RESET_BUTTON_SHARED_ID = "reset-button-shared-id"
RESET_MODAL_SHARED_ID = "reset-modal-shared-id"
RESET_MODAL_CANCEL_BUTTON_SHARED_ID = "reset-modal-cancel-button-shared-id"
RESET_MODAL_CONFIRM_BUTTON_SHARED_ID = "reset-modal-confirm-button-shared-id"

# ============================================================================
# PAGE: DATA_UPLOAD
# ============================================================================

# --- Buttons ---
NEXT_BUTTON_DATA_UPLOAD_ID = "next-button-data-upload-id"

# --- Divs ---
DATA_UPLOAD_DROPZONE_DIV_DATA_UPLOAD_ID = (
    "data-upload-dropzone-div-data-upload-id"  # nocheck visual container
)
DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID = "data-upload-file-info-div-data-upload-id"

# --- Inputs ---
DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID = "data-upload-epsg-input-data-upload-id"

# --- Other ---
DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID = (
    "data-upload-epsg-helper-text-data-upload-id"
)
DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID = (
    "data-upload-upload-component-data-upload-id"
)


# ============================================================================
# PAGE: HOME
# ============================================================================

# --- Buttons ---
START_JOB_BUTTON_HOME_ID = "start-job-button-home-id"


# ============================================================================
# PAGE: MAP
# ============================================================================

# (Map elements are in SHARED section above as they're used across pages)


# ============================================================================
# PAGE: LOGS
# ============================================================================

# --- Divs ---
LOG_OUTPUT_DIV_LOGS_ID = "log-output-div-logs-id"
TIME_ERROR_DIV_LOGS_ID = "time-error-div-logs-id"

# --- Dropdowns ---
LOG_LEVELS_DROPDOWN_LOGS_ID = "log-levels-dropdown-logs-id"

# --- Inputs ---
END_HOUR_INPUT_LOGS_ID = "end-hour-input-logs-id"
END_MINUTE_INPUT_LOGS_ID = "end-minute-input-logs-id"
LOG_PID_INPUT_LOGS_ID = "log-pid-input-logs-id"
START_HOUR_INPUT_LOGS_ID = "start-hour-input-logs-id"
START_MINUTE_INPUT_LOGS_ID = "start-minute-input-logs-id"

# --- Other ---
LOG_DATE_PICKER_LOGS_ID = "log-date-picker-logs-id"
PID_CHECKLIST_LOGS_ID = "pid-checklist-logs-id"
TIME_INPUT_GROUP_LOGS_ID = "time-input-group-logs-id"


# ============================================================================
# PAGE: ROUTING_PARAMS
# ============================================================================

# Needed for testing purposes
NEXT_BUTTON_ROUTING_PARAMS_ID = "next-button-routing-params-id"  # nocheck

# ============================================================================
# PAGE: ROUTE_COMPUTATION
# ============================================================================

# --- Buttons ---
START_BUTTON_ROUTE_COMPUTATION_ID = "start-button-route-computation-id"
CANCEL_BUTTON_ROUTE_COMPUTATION_ID = "cancel-button-route-computation-id"
RESTART_BUTTON_ROUTE_COMPUTATION_ID = "restart-button-route-computation-id"

# --- Displays ---
STATUS_BADGE_ROUTE_COMPUTATION_ID = "status-badge-route-computation-id"
CELERY_INFO_CARD_ROUTE_COMPUTATION_ID = "celery-info-card-route-computation-id"
WORKER_STATUS_TEXT_ROUTE_COMPUTATION_ID = "worker-status-text-route-computation-id"
TASK_STATUS_TEXT_ROUTE_COMPUTATION_ID = "task-status-text-route-computation-id"
WORKER_NAME_TEXT_ROUTE_COMPUTATION_ID = "worker-name-text-route-computation-id"
LOG_VIEWER_ROUTE_COMPUTATION_ID = "log-viewer-route-computation-id"

# --- Intervals ---
STATUS_POLL_INTERVAL_ROUTE_COMPUTATION_ID = "status-poll-interval-route-computation-id"

# ============================================================================
# PAGE: ROUTE_DOWNLOAD
# ============================================================================

# --- Buttons ---
START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID = "start-route-button-route-download-id"

# --- Divs/Images ---
QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID = "qr-code-image-route-download-id"


# ============================================================================
# PAGE: STREET_SELECTION
# ============================================================================

# --- Buttons ---
# Needed for testing purposes
NEXT_BUTTON_STREET_SELECTION_ID = "next-button-street-selection-id"  # nocheck
CANCEL_RESET_BUTTON_STREET_SELECTION_ID = "cancel-reset-button-street-selection-id"
CONFIRM_RESET_BUTTON_STREET_SELECTION_ID = "confirm-reset-button-street-selection-id"
LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID = "largest-button-button-street-selection-id"
REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID = "remove-button-button-street-selection-id"
RESET_ROADS_BUTTON_STREET_SELECTION_ID = "reset-roads-button-street-selection-id"
TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID = (
    "tags-select-all-button-street-selection-id"
)
TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID = (
    "tags-select-none-button-street-selection-id"
)
UNDO_BUTTON_BUTTON_STREET_SELECTION_ID = "undo-button-button-street-selection-id"

# --- Dropdowns ---
TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID = (
    "tags-dropdown-dropdown-street-selection-id"
)

# --- Modals ---
RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID = (
    "reset-confirm-modal-modal-street-selection-id"
)


# ============================================================================
# PAGE: USER_INFO
# ============================================================================

# --- Buttons ---
USER_INFO_NEXT_BUTTON_USER_INFO_ID = "user-info-next-button-user-info-id"

# --- Inputs ---
USER_INFO_EMAIL_INPUT_USER_INFO_ID = "user-info-email-input-user-info-id"


# ============================================================================
# PAGE: WORKER_MANAGEMENT
# ============================================================================

# --- Buttons ---
WORKER_CANCEL_BTN_WORKER_MANAGEMENT_ID = "worker-cancel-btn-worker-management-id"
WORKER_KILL_BTN_WORKER_MANAGEMENT_ID = "worker-kill-btn-worker-management-id"
WORKER_REFRESH_BTN_WORKER_MANAGEMENT_ID = "worker-refresh-btn-worker-management-id"
TEST_TASK_BUTTON_WORKER_MANAGEMENT_ID = "test-task-button-worker-management-id"

# --- Inputs ---
SELECTED_TASK_ID_INPUT_WORKER_MANAGEMENT_ID = (
    "selected-task-id-input-worker-management-id"
)

# --- Divs ---
WORKER_LAST_REFRESH_DIV_WORKER_MANAGEMENT_ID = (
    "worker-last-refresh-div-worker-management-id"
)
WORKER_STATS_CARD_DIV_WORKER_MANAGEMENT_ID = (
    "worker-stats-card-div-worker-management-id"
)

# --- Other ---
WORKER_MANAGEMENT_DUMMY_COMPONENT_WORKER_MANAGEMENT_ID = (
    "worker-management-dummy-component-worker-management-id"
)

# --- Tables ---
ACTIVE_TASKS_TABLE_WORKER_MANAGEMENT_ID = "active-tasks-table-worker-management-id"
RESERVED_TASKS_TABLE_WORKER_MANAGEMENT_ID = "reserved-tasks-table-worker-management-id"
REVOKED_TASKS_TABLE_WORKER_MANAGEMENT_ID = "revoked-tasks-table-worker-management-id"
SCHEDULED_TASKS_TABLE_WORKER_MANAGEMENT_ID = (
    "scheduled-tasks-table-worker-management-id"
)
