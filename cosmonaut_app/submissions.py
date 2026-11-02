"""COSMONAUT's domain submissions: the routing and the upload task.

Module functions over the framework's manager, not a manager subclass or methods
mounted on it (cosmo-ecosystem ADR 0003, docs/conventions/domain_module.md). Both
pull the job id out of ``job.model``, which is where ``CosmonautJob`` keeps it; the
framework manager takes a bare id and never touches a job object.

``track_task_name`` defaults to True in both framework helpers, which is what keeps
a revoked task from showing up as "Unknown" on the worker-management page.
"""

import cosmo_ecosystem.background_job_manager

NAME_ROUTING_TASK = "cosmonaut_app.tasks.routing_tasks.process_routing"
NAME_UPLOAD_TASK = "cosmonaut_app.tasks.upload_tasks.process_upload"


def manager():
    """The framework manager, looked up at call time.

    The app's modules reach it through here. Not bound by a `from … import` at
    import: cosmonaut_app.domain imports this module (through the tasks and
    cosmonaut_job), and binding the manager then would assemble the Celery app while the domain module is still half-imported.
    """
    return cosmo_ecosystem.background_job_manager.background_job_manager


def submit_routing_job(job) -> tuple[str | None, bool]:
    """Submit a routing job to the routing queue.

    Args:
        job: CosmonautJob instance to submit

    Returns:
        tuple: (celery_task_id, failed_boolean)
               celery_task_id is None if submission failed
    """
    return manager().submit_job(NAME_ROUTING_TASK, job.model.job_id, "routing")


def submit_upload_job(job, epsg_input: int) -> tuple[str | None, bool]:
    """Submit an upload post-processing job to the upload queue.

    Args:
        job: CosmonautJob instance to submit
        epsg_input: EPSG code of the uploaded membership data

    Returns:
        tuple: (celery_task_id, failed_boolean)
               celery_task_id is None if submission failed
    """
    # submit_named_job, not submit_job: submit_job passes the job id as the task's
    # *only* positional arg, and this task takes a second one. Same retry policy and
    # the same task-name tracking underneath.
    return manager().submit_named_job(
        NAME_UPLOAD_TASK,
        args=[job.model.job_id, epsg_input],
        queue="upload",
    )
