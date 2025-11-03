"""Callbacks for job search, creation, and stage management."""

import os
import logging
from dash import no_update, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from flask import current_app

from cosmonaut_app.config import WEB_WORK_DIR
from cosmonaut_app.constants.html_ids import (
    CURRENT_STAGE_STORE_SHARED_ID,
    JOB_ID_STORE_SHARED_ID,
    JOB_LOADED_FLAG_STORE_SHARED_ID,
    SEARCH_BUTTON_NAV_SHARED_ID,
    SEARCH_INPUT_NAV_SHARED_ID,
    SEARCH_RESULTS_DIV_NAV_SHARED_ID,
    START_JOB_BUTTON_HOME_ID,
    URL_DIV_NAV_SHARED_ID,
)
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.flask_routes import app


@app.callback(
    Output(SEARCH_RESULTS_DIV_NAV_SHARED_ID, "children"),
    Output(JOB_ID_STORE_SHARED_ID, "data", allow_duplicate=True),
    Output(URL_DIV_NAV_SHARED_ID, "pathname", allow_duplicate=True),
    Input(SEARCH_BUTTON_NAV_SHARED_ID, "n_clicks"),
    State(SEARCH_INPUT_NAV_SHARED_ID, "value"),
    prevent_initial_call=True,
)
def search_job_id(n_clicks, job_id):
    if n_clicks is None:
        raise PreventUpdate

    if DataBaseManager.check_existence(job_id):
        job = CosmonautJob(job_id=job_id, download_from_minio=True)
        job.load()

        job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
        current_app.config["JOB_WORKING_DIR"] = job_working_dir

        return (
            dbc.Toast(
                [html.Div(f"Job {job_id} found and loaded successfully.")],
                header="Job loaded",
                icon="success",
                is_open=True,
                duration=3000,
                dismissable=True,
                style={
                    "maxWidth": "26rem",
                    "wordWrap": "break-word",
                    "whiteSpace": "normal",
                },
            ),
            job_id,
            f"/job/{job_id}/user-info",
        )
    else:
        return (
            dbc.Toast(
                [html.Div(f"Job {job_id} not found")],
                header="Not found",
                icon="danger",
                is_open=True,
                duration=3000,
                dismissable=True,
                style={
                    "maxWidth": "26rem",
                    "wordWrap": "break-word",
                    "whiteSpace": "normal",
                },
            ),
            no_update,
            no_update,
        )


@app.callback(
    Output(JOB_ID_STORE_SHARED_ID, "data", allow_duplicate=True),
    Output(URL_DIV_NAV_SHARED_ID, "pathname", allow_duplicate=True),
    Input(START_JOB_BUTTON_HOME_ID, "n_clicks"),
    prevent_initial_call=True,
)
def start_job(n_clicks):
    if not n_clicks:
        logging.debug("No clicks detected, preventing update")
        raise PreventUpdate

    logging.info("Initializing new CosmonautJob")
    job = CosmonautJob()
    job._blank_job()
    job_id = job.job_id

    try:
        job.save()
        logging.info("Successfully saved new job with id=%s", job_id)
    except Exception as e:
        logging.error("Failed to save job %s: %s", job_id, str(e))
        raise

    job_working_dir = os.path.join(WEB_WORK_DIR, job_id)
    current_app.config["JOB_WORKING_DIR"] = job_working_dir

    for p in ["", "transient/debug", "input", "plots", "output"]:
        os.makedirs(os.path.join(job_working_dir, p), exist_ok=True)

    logging.info(
        "Successfully initialized working directory structure for job %s", job_id
    )

    target = f"/job/{job_id}/user-info"
    return job_id, target


# @app.callback(
#     Output("stage-content", "children"),
#     Input("job-id", "data"),
#     Input("current-stage", "data"),
#     State("job-loaded-flag", "data"),
# )
# def update_stage(job_id, current_stage, job_loaded_flag):
#     logging.info("Job ID: %s", job_id)
#     if job_id is None:
#         logging.info("No job initialized. Showing welcome message.")
#         # return html.Div(
#         #     [
#         #         html.H3(
#         #             "Welcome to the COSmic ray based soil MOisture prediction NAvigation Utility Tool."
#         #         ),
#         #         html.H4("Press the Button to start initializing the job."),
#         #         dbc.Button(
#         #             "Start Job",
#         #             id="start-job",
#         #             className="me-auto",
#         #             size="lg",
#         #         ),
#         #     ]
#         # )

#     logging.info("Processing job %s", job_id)
#     logging.debug(
#         "Input state - stage: %s, loaded_flag: %s", current_stage, job_loaded_flag
#     )

#     try:
#         job = CosmonautJob(job_id=job_id)
#         loaded_stage = job.stage
#         logging.debug("Loaded stage from job: %s", loaded_stage)
#     except Exception as e:
#         logging.error("Failed to load job %s: %s", job_id, str(e))
#         raise

#     if current_stage is None or current_stage != loaded_stage:
#         current_stage = loaded_stage
#         job_loaded = True
#         logging.info("Job %s loaded with stage %s", job_id, current_stage)
#     else:
#         job_loaded = False
#         logging.debug("Job %s already loaded", job_id)

#     if job_loaded_flag is None:
#         job_loaded_flag = job_loaded
#     elif job_loaded_flag and not job_loaded:
#         job_loaded_flag = False

#     logging.debug("Updated job_loaded_flag: %s", job_loaded_flag)

#     try:
#         if current_stage == 0:
#             if not job_loaded_flag:
#                 logging.info("Job %s progressing to Stage 1", job_id)
#                 DataBaseManager.update_column(job_id, {"stage": 1})
#                 return stage1(job_id)
#         elif current_stage == 1:
#             if not job_loaded_flag:
#                 logging.info("Job %s progressing to Stage 2", job_id)
#                 DataBaseManager.update_column(job_id, {"stage": 2})

#                 input_dir = f"cosmonaut_app/work_dir/{job_id}/input"

#                 if os.listdir(input_dir):
#                     logging.info("Starting MinIO file upload for job %s", job_id)
#                     minio_manager = MiniIOManager("cosmic-routing")
#                     for file in os.listdir(input_dir):
#                         file_path = f"{input_dir}/{file}"
#                         try:
#                             minio_manager.upload_file(file_path, file)
#                             logging.debug("Successfully uploaded %s to MinIO", file)
#                         except Exception as e:
#                             logging.error(
#                                 "Failed to upload %s to MinIO: %s", file, str(e)
#                             )
#                             raise

#                 DataBaseManager.update_column(job_id, {"data_uploaded": True})
#                 logging.info("Completed MinIO uploads for job %s", job_id)
#                 return stage2(job_id)
#         elif current_stage == 2:
#             if not job_loaded_flag:
#                 logging.info("Job %s progressing to Stage 3", job_id)
#                 DataBaseManager.update_column(job_id, {"stage": 3})
#                 return stage3(job_id)
#     except Exception as e:
#         logging.error(
#             "Error processing stage %s for job %s: %s", current_stage, job_id, str(e)
#         )
#         raise

#     logging.debug("No stage transition needed for job %s", job_id)
#     return None


@app.callback(
    Output(JOB_LOADED_FLAG_STORE_SHARED_ID, "data"),
    Input("next-stage-button", "n_clicks"),
    State(JOB_LOADED_FLAG_STORE_SHARED_ID, "data"),
)
def reset_job_loaded_flag(n_clicks, job_loaded_flag):
    if n_clicks is not None and job_loaded_flag:
        return False
    return job_loaded_flag


@app.callback(
    Output(CURRENT_STAGE_STORE_SHARED_ID, "data"),
    Input("next-button", "n_clicks"),
    Input("prev-button", "n_clicks"),
    State(CURRENT_STAGE_STORE_SHARED_ID, "data"),
)
def update_current_stage(next_clicks, prev_clicks, current_stage):
    if next_clicks is None and prev_clicks is None:
        return 0

    if next_clicks is not None:
        return current_stage + 1

    if prev_clicks is not None:
        return current_stage - 1


@app.callback(
    Output("force-refresh", "children"),
    Input(URL_DIV_NAV_SHARED_ID, "pathname"),
)
def force_user_info_refresh(pathname):
    # Return the pathname or a timestamp to force update
    return f"refreshed: {pathname}"
