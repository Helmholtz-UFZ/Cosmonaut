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
CURRENT_STAGE_STORE_SHARED_ID = "current-stage-store-shared-id"
EMAIL_STORE_SHARED_ID = "email-store-shared-id"
EPSG_STORE_SHARED_ID = "epsg-store-shared-id"
FILE_PATH_STORE_SHARED_ID = "file-path-store-shared-id"
JOB_ID_STORE_SHARED_ID = "job-id-store-shared-id"
JOB_LOADED_FLAG_STORE_SHARED_ID = "job-loaded-flag-store-shared-id"
OSM_FILE_PATH_STORE_SHARED_ID = "osm-file-path-store-shared-id"
ROUTING_COMPLETE_STORE_SHARED_ID = "routing-complete-store-shared-id"
TAGS_LAST_SELECTION_STORE_SHARED_ID = "tags-last-selection-store-shared-id"
UPLOAD_DATA_STORE_SHARED_ID = "upload-data-store-shared-id"

# --- Navigation ---
HIDDEN_DIV_NAV_SHARED_ID = "hidden-div-nav-shared-id"
NAVBAR_COLLAPSE_NAV_SHARED_ID = "navbar-collapse-nav-shared-id"
NAVBAR_TOGGLER_NAV_SHARED_ID = "navbar-toggler-nav-shared-id"
REDIRECT_INTERVAL_NAV_SHARED_ID = "redirect-interval-nav-shared-id"
SEARCH_BUTTON_NAV_SHARED_ID = "search-button-nav-shared-id"
SEARCH_INPUT_NAV_SHARED_ID = "search-input-nav-shared-id"
SEARCH_RESULTS_DIV_NAV_SHARED_ID = "search-results-div-nav-shared-id"
URL_DIV_NAV_SHARED_ID = "url-div-nav-shared-id"

# --- Utility ---
DUMMY_OUTPUT_DIV_SHARED_ID = "dummy-output-div-shared-id"
NONE_DIV_SHARED_ID = "none-div-shared-id"

# --- Map Elements ---
LC_LAYER_MAP_SHARED_ID = "lc-layer-map-shared-id"
MAIN_MAP_DIV_MAP_SHARED_ID = "main-map-div-map-shared-id"
MAP_CONTAINER_DIV_MAP_SHARED_ID = "map-container-div-map-shared-id"
OSM_GEOJSON_LAYER_MAP_SHARED_ID = "osm-geojson-layer-map-shared-id"
ROUTE_GEOJSON_LAYER_MAP_SHARED_ID = "route-geojson-layer-map-shared-id"
ROUTE_LAYER_LAYER_MAP_SHARED_ID = "route-layer-layer-map-shared-id"
WMS_LAYER_LAYER_MAP_SHARED_ID = "wms-layer-layer-map-shared-id"


# ============================================================================
# PAGE: DATA_UPLOAD
# ============================================================================

# --- Buttons ---
DATA_UPLOAD_NEXT_BUTTON_DATA_UPLOAD_ID = "data-upload-next-button-data-upload-id"
DATA_UPLOAD_PREV_BUTTON_DATA_UPLOAD_ID = "data-upload-prev-button-data-upload-id"

# --- Divs ---
DATA_UPLOAD_CONTENT_DIV_DATA_UPLOAD_ID = "data-upload-content-div-data-upload-id"
DATA_UPLOAD_DROPZONE_DIV_DATA_UPLOAD_ID = "data-upload-dropzone-div-data-upload-id"
DATA_UPLOAD_FILE_INFO_DIV_DATA_UPLOAD_ID = "data-upload-file-info-div-data-upload-id"
OUTPUT_DATA_UPLOAD_DIV_DATA_UPLOAD_ID = "output-data-upload-div-data-upload-id"
OUTPUT_MINIO_STATUS_DIV_DATA_UPLOAD_ID = "output-minio-status-div-data-upload-id"
OUTPUT_OSM_QUERY_DIV_DATA_UPLOAD_ID = "output-osm-query-div-data-upload-id"
PLOT_GENERATION_STATUS_DIV_DATA_UPLOAD_ID = "plot-generation-status-div-data-upload-id"

# --- Inputs ---
DATA_UPLOAD_EPSG_INPUT_DATA_UPLOAD_ID = "data-upload-epsg-input-data-upload-id"

# --- Other ---
DATA_UPLOAD_EPSG_HELPER_TEXT_DATA_UPLOAD_ID = "data-upload-epsg-helper-text-data-upload-id"
DATA_UPLOAD_UPLOAD_COMPONENT_DATA_UPLOAD_ID = "data-upload-upload-component-data-upload-id"
TOAST_STACK_CONTAINER_DATA_UPLOAD_ID = "toast-stack-container-data-upload-id"


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
# PAGE: ROUTING_PARAMS
# ============================================================================

# --- Alerts ---
PARAMS_ALERT_ALERT_ROUTING_PARAMS_ID = "params-alert-alert-routing-params-id"

# --- Buttons ---
PARAMS_LOAD_BUTTON_ROUTING_PARAMS_ID = "params-load-button-routing-params-id"
RUN_ROUTING_BUTTON_ROUTING_PARAMS_ID = "run-routing-button-routing-params-id"

# --- Inputs (Config Parameters) ---
CFG_AN_INPUT_ROUTING_PARAMS_ID = "cfg-an-input-routing-params-id"
CFG_IR_INPUT_ROUTING_PARAMS_ID = "cfg-ir-input-routing-params-id"
CFG_LBF_INPUT_ROUTING_PARAMS_ID = "cfg-lbf-input-routing-params-id"
CFG_MAI_INPUT_ROUTING_PARAMS_ID = "cfg-mai-input-routing-params-id"
CFG_MD_INPUT_ROUTING_PARAMS_ID = "cfg-md-input-routing-params-id"
CFG_OO_INPUT_ROUTING_PARAMS_ID = "cfg-oo-input-routing-params-id"
CFG_SN_INPUT_ROUTING_PARAMS_ID = "cfg-sn-input-routing-params-id"
CFG_TL_INPUT_ROUTING_PARAMS_ID = "cfg-tl-input-routing-params-id"
CFG_WD_INPUT_ROUTING_PARAMS_ID = "cfg-wd-input-routing-params-id"


# ============================================================================
# PAGE: ROUTE_DOWNLOAD
# ============================================================================

# --- Buttons ---
START_ROUTE_BUTTON_ROUTE_DOWNLOAD_ID = "start-route-button-route-download-id"

# --- Divs/Images ---
QR_CODE_IMAGE_ROUTE_DOWNLOAD_ID = "qr-code-image-route-download-id"
ROUTE_QRCODE_DIV_ROUTE_DOWNLOAD_ID = "route-qrcode-div-route-download-id"

# --- Links ---
ROUTE_GPX_LINK_LINK_ROUTE_DOWNLOAD_ID = "route-gpx-link-link-route-download-id"


# ============================================================================
# PAGE: STREET_SELECTION
# ============================================================================

# --- Alerts ---
ACTION_ALERT_ALERT_STREET_SELECTION_ID = "action-alert-alert-street-selection-id"

# --- Buttons ---
CONFIRM_RESET_BUTTON_STREET_SELECTION_ID = "confirm-reset-button-street-selection-id"
CANCEL_RESET_BUTTON_STREET_SELECTION_ID = "cancel-reset-button-street-selection-id"
LARGEST_BUTTON_BUTTON_STREET_SELECTION_ID = "largest-button-button-street-selection-id"
REMOVE_BUTTON_BUTTON_STREET_SELECTION_ID = "remove-button-button-street-selection-id"
RESET_ROADS_BUTTON_STREET_SELECTION_ID = "reset-roads-button-street-selection-id"
STREET_SELECTION_NEXT_BUTTON_STREET_SELECTION_ID = "street-selection-next-button-street-selection-id"
STREET_SELECTION_PREV_BUTTON_STREET_SELECTION_ID = "street-selection-prev-button-street-selection-id"
TAGS_SELECT_ALL_BUTTON_STREET_SELECTION_ID = "tags-select-all-button-street-selection-id"
TAGS_SELECT_NONE_BUTTON_STREET_SELECTION_ID = "tags-select-none-button-street-selection-id"
UNDO_BUTTON_BUTTON_STREET_SELECTION_ID = "undo-button-button-street-selection-id"

# --- Divs ---
SELECTION_COUNT_DIV_STREET_SELECTION_ID = "selection-count-div-street-selection-id"

# --- Dropdowns ---
TAGS_DROPDOWN_DROPDOWN_STREET_SELECTION_ID = "tags-dropdown-dropdown-street-selection-id"

# --- Modals ---
RESET_CONFIRM_MODAL_MODAL_STREET_SELECTION_ID = "reset-confirm-modal-modal-street-selection-id"


# ============================================================================
# PAGE: USER_INFO
# ============================================================================

# --- Buttons ---
USER_INFO_NEXT_BUTTON_USER_INFO_ID = "user-info-next-button-user-info-id"
USER_INFO_PREV_BUTTON_USER_INFO_ID = "user-info-prev-button-user-info-id"

# --- Divs ---
USER_INFO_CONTENT_DIV_USER_INFO_ID = "user-info-content-div-user-info-id"

# --- Inputs ---
USER_INFO_EMAIL_INPUT_USER_INFO_ID = "user-info-email-input-user-info-id"
