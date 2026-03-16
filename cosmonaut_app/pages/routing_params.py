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


card_body_with_placeholder = []
fields = list(FullPipelineConfig.model_fields.keys())
for i in range(0, len(fields), 2):
    col = [dbc.Col(InputField(fields[i]))]
    if i + 1 < len(fields):
        col.append(dbc.Col(InputField(fields[i + 1])))
    card_body_with_placeholder.append(dbc.Row(col, className="g-2 mt-1"))

form_factory = FormFactory(FullPipelineConfig, card_body_with_placeholder)
card_body = form_factory.process_layout(form_factory.layout)


def layout(job_id):
    log.info(f"Routing params layout called with job_id={job_id}")
    job = CosmonautJob(job_id=job_id)
    status = job.get_status()
    is_active = status == JOB_STATUS_PENDING

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
    )
    return page_container_fullscreen_layout(input_container)


# ============================================================================
# Callbacks
# ============================================================================


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
    job = CosmonautJob(job_id=job_id)

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
        job.save()
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
