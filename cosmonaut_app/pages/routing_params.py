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
import dash_bootstrap_components as dbc

from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.constants.html_ids import (
    JOB_ID_STORE_SHARED_ID,
    NEXT_BUTTON_ROUTING_PARAMS_ID,
    URL_SHARED_ID,
)

from cosmonaut_app.layout import (
    create_map,
    page_container_split_layout,
    create_card_input,
    progress_footer,
    build_url_step,
)
from cosmonaut_app.form_factory import FormFactory, InputField
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
    logging.info(f"Routing params layout called with job_id={job_id}")
    job = CosmonautJob(job_id=job_id)
    form_factory = FormFactory(job.model, card_body_with_placeholder)
    card_body = form_factory.process_layout(form_factory.layout)
    card_body.append(dcc.Store(id=JOB_ID_STORE_SHARED_ID, data=job_id))

    user_info_path = build_url_step("street_selection", job_id)

    footer = progress_footer(
        prev_url=user_info_path,
        next_id=NEXT_BUTTON_ROUTING_PARAMS_ID,
        next_disabled=True,
    )

    map = create_map(job=job)

    input_container = create_card_input(
        card_body,
        card_footer=footer,
        name_step=__name__.replace("pages.", ""),
        job_id=job_id,
    )
    return page_container_split_layout(map, input_container)


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
    valid, output_dict = form_factory.validate_callback(inputs)
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    logging.info(f"Routing params callback triggered by {triggered_id}, valid={valid}")
    if valid and triggered_id == NEXT_BUTTON_ROUTING_PARAMS_ID:
        for key, value in inputs.items():
            if hasattr(job.model, key):
                setattr(job.model, key, value)
        job.submit()
        return {
            **output_dict,
            "url": build_url_step("route_download", job_id),
            "next_button": False,
        }

    output_dict["url"] = no_update
    if valid:
        output_dict["next_button"] = False
    else:
        output_dict["next_button"] = True

    return output_dict
