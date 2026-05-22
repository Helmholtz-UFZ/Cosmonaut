"""Configure routing algorithm parameters before calculation.

# User documentation (This section is for user documentation and will appear in the user documentation.)

Fine-tune the routing calculation by adjusting advanced parameters that control
how your navigation route is optimized. This page presents a dynamically generated
form with configuration options from the sensor-routing pipeline.

**Available Parameters:**

The form includes various routing optimization settings such as:
- Route optimization weights and penalties
- Distance calculation methods and thresholds
- Network traversal and pathfinding settings
- Algorithmic tuning options for the routing algorithm

The form is automatically generated from the FullPipelineConfig Pydantic model,
ensuring all parameters are properly validated and have sensible defaults. Each
field includes its data type, default value, and valid ranges where applicable.

**Using This Page:**

Most users can proceed with the default values, which are optimized for typical
CRNS field sampling scenarios. The defaults provide a good balance between route
efficiency, coverage of measurement points, and practical navigability.

Advanced users can customize parameters for specific use cases:
- Different vehicle types (car, bicycle, on-foot)
- Varying terrain requirements
- Specific measurement density patterns
- Custom optimization objectives

Simply review the default settings and modify any parameters you wish to customize.
When satisfied, click "Next" to proceed to the final page where you'll start the
route calculation and download your GPX navigation file.

# Notes (This section is for developer notes and will not appear in the user documentation.)

The form is auto-generated using FormFactory with InputField components.
All configuration is validated against the FullPipelineConfig pydantic model to
ensure type safety and value constraints. Parameters are persisted to the job
model and used during background route calculation.
"""

import logging
from dash import (
    register_page,
    dcc,
    callback,
    Output,
    State,
    Input,
    callback_context,
    no_update,
)
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.constants.general import JOB_STATUS_PENDING
from cosmonaut_app.constants.html_ids import (
    ADVANCED_COLLAPSE_ROUTING_PARAMS_ID,
    ADVANCED_TOGGLE_ROUTING_PARAMS_ID,
    JOB_ID_STORE_SHARED_ID,
    NEXT_BUTTON_ROUTING_PARAMS_ID,
    URL_SHARED_ID,
)

from cosmonaut_app.layout import (
    page_container_fullscreen_layout,
    create_card_input,
    progress_footer,
    build_url_step,
    create_reset_banner,
    create_reset_modal,
)
from dash_form_factory import FormFactory, InputField
from cosmonaut_app.pydantic_models import FullPipelineConfig

log = logging.getLogger(__name__)

register_page(
    __name__,
    path_template="/job/<job_id>/routing-params",
    name="Routing Parameters",
    title="Routing Parameters",
    description="Tune parameters before route calculation.",
    dynamic=True,
)

ESSENTIAL_FIELDS = [
    "segment_number",
    "time_limit",
    "max_distance",
    "optimization_objective",
    "num_points",
]

ADVANCED_FIELDS = [
    "lower_benefit_limit",
    "max_aco_iteration",
    "ant_no",
    "is_reversed",
    "working_directory",
    "benefit_type",
    "route_type",
    "goal_ratio",
    "use_fixed_seeds",
    "debug_seed",
    "allow_fewer_points",
]

assert set(ESSENTIAL_FIELDS + ADVANCED_FIELDS) == set(
    FullPipelineConfig.model_fields.keys()
), (
    f"Field partition mismatch. Missing: "
    f"{set(FullPipelineConfig.model_fields.keys()) - set(ESSENTIAL_FIELDS + ADVANCED_FIELDS)}. "
    f"Extra: {set(ESSENTIAL_FIELDS + ADVANCED_FIELDS) - set(FullPipelineConfig.model_fields.keys())}"
)


def _build_rows(fields):
    rows = []
    for i in range(0, len(fields), 2):
        col = [dbc.Col(InputField(fields[i]))]
        if i + 1 < len(fields):
            col.append(dbc.Col(InputField(fields[i + 1])))
        rows.append(dbc.Row(col, className="g-2 mt-1"))
    return rows


_essential_rows = _build_rows(ESSENTIAL_FIELDS)

# Insert objective helper caption right after the row containing optimization_objective.
# optimization_objective is at index 3 in ESSENTIAL_FIELDS (0-based), so row index 1
# (row 0: segment_number + time_limit, row 1: max_distance + optimization_objective).
_objective_caption = dbc.Row(
    dbc.Col(
        dbc.FormText(
            "Objective: 'd' = max distance, 't' = time limit.",
        ),
    ),
    className="mt-1",
)

_advanced_rows = _build_rows(ADVANCED_FIELDS)

_toggle_button = dbc.Button(
    "Show advanced options ▾",
    id=ADVANCED_TOGGLE_ROUTING_PARAMS_ID,
    color="link",
    className="mt-2 p-0 text-muted small text-decoration-none",
    n_clicks=0,
)

_advanced_collapse = dbc.Collapse(
    _advanced_rows,
    id=ADVANCED_COLLAPSE_ROUTING_PARAMS_ID,
    is_open=False,
)

card_body_with_placeholder = [
    *_essential_rows[:2],   # segment_number+time_limit, max_distance+optimization_objective
    _objective_caption,
    *_essential_rows[2:],   # num_points row
    _toggle_button,
    _advanced_collapse,
]

form_factory = FormFactory(FullPipelineConfig, card_body_with_placeholder)
card_body = form_factory.process_layout(form_factory.layout)


def layout(job_id):
    log.info(f"Routing params layout called with job_id={job_id}")
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()
    is_active = status == JOB_STATUS_PENDING
    job.model.stage = max(job.model.stage, 3)
    job.save(sync_files=False)

    # Create form with FormFactory (active parameter controls disabled state and styling)
    # IDs are always preserved for callbacks regardless of active state
    form_factory = FormFactory(job.model, card_body_with_placeholder, active=is_active)
    card_body = form_factory.process_layout(form_factory.layout)

    # Add reset banner if not PENDING (insert at beginning)
    if not is_active:
        card_body.insert(0, create_reset_banner(job_id, status))

    # Add reset modal
    card_body.append(create_reset_modal())

    # Add store
    card_body.append(dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id))

    user_info_path = build_url_step("street_selection", job_id)

    footer = progress_footer(
        prev_url=user_info_path,
        next_id=NEXT_BUTTON_ROUTING_PARAMS_ID,
        next_disabled=is_active,  # When PENDING, disable until form validated by callback
    )

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
        completed_steps=job.get_completed_steps(),
    )
    return page_container_fullscreen_layout(input_container)


# ============================================================================
# Callbacks
# ============================================================================


@callback(
    Output(ADVANCED_COLLAPSE_ROUTING_PARAMS_ID, "is_open"),
    Output(ADVANCED_TOGGLE_ROUTING_PARAMS_ID, "children"),
    Output(ADVANCED_TOGGLE_ROUTING_PARAMS_ID, "className"),
    Input(ADVANCED_TOGGLE_ROUTING_PARAMS_ID, "n_clicks"),
    State(ADVANCED_COLLAPSE_ROUTING_PARAMS_ID, "is_open"),
    prevent_initial_call=True,
)
def toggle_advanced_options(n_clicks, is_open):
    new_open = not is_open
    label = "Hide advanced options ▴" if new_open else "Show advanced options ▾"
    className = "mt-2 p-0 text-muted small text-decoration-none"
    return new_open, label, className


@callback(
    output={
        **form_factory.produce_callback_outputs(),
        "url": Output(URL_SHARED_ID, "pathname"),
        "next_button": Output(NEXT_BUTTON_ROUTING_PARAMS_ID, "disabled"),
    },
    inputs={
        **form_factory.produce_callback_inputs(),
        "input_next": Input(NEXT_BUTTON_ROUTING_PARAMS_ID, "n_clicks"),
    },
    state={
        "job_id": State(JOB_ID_STORE_SHARED_ID, "data"),
    },
    prevent_initial_call="initial_duplicate",
)
def update_routing_params(**inputs):
    job_id = inputs.pop("job_id")
    job = CosmonautJob(job_id=job_id, sync_files=False)

    triggered_ids = {
        t["prop_id"].split(".")[0]
        for t in callback_context.triggered
        if t["value"] is not None
    }

    # If job is not PENDING, only allow navigation (no param updates)
    if job.get_status() != JOB_STATUS_PENDING:
        if NEXT_BUTTON_ROUTING_PARAMS_ID in triggered_ids:
            return {
                **{k: no_update for k in form_factory.produce_callback_outputs()},
                "url": build_url_step("route_computation", job_id),
                "next_button": no_update,
            }
        raise PreventUpdate

    valid, output_dict = form_factory.validate_callback(inputs)
    log.info(f"Routing params callback triggered by {triggered_ids}, valid={valid}")
    if valid and NEXT_BUTTON_ROUTING_PARAMS_ID in triggered_ids:
        for key, value in inputs.items():
            if hasattr(job.model, key):
                setattr(job.model, key, value)
        job.model.stage = max(job.model.stage, 3)
        # Skip file sync — submit() syncs before the worker starts
        job.save(sync_files=False)
        return {
            **output_dict,
            "url": build_url_step("route_computation", job_id),
            "next_button": False,
        }

    output_dict["url"] = no_update
    if valid:
        output_dict["next_button"] = False
    else:
        output_dict["next_button"] = True

    return output_dict
