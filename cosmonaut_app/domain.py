"""COSMONAUT's domain module: what the framework needs to assemble a process.

Named by ``COSMO_DOMAIN=cosmonaut_app.domain`` in every process (web, worker,
CLI). ``cosmo_ecosystem.celery_app`` imports it on first access to the Celery app
and builds that app from the attributes below; see
docs/conventions/domain_module.md in cosmo-ecosystem for the contract.

Importing it also sets ``DbManager.job_table`` (``cosmonaut_app.db_manager`` does
that on import) and loads ``CosmonautJob``, so the worker, which never imports
``app.py``, has them before any task runs. COSMONAUT uses none of the framework
``Job`` seams: its job class is ``CosmonautJob`` on ``BaseJob``. The web process
imports this module at the top of ``app.py``.
"""

from cosmo_ecosystem.celery_config import BaseCeleryConfig
from cosmo_ecosystem.task_spec import TaskSpec

import cosmonaut_app.db_manager  # noqa: F401  sets DbManager.job_table on import
from cosmonaut_app.constants.general import EXCLUDED_LOG_PACKAGES
from cosmonaut_app.submissions import NAME_ROUTING_TASK, NAME_UPLOAD_TASK
from cosmonaut_app.tasks.routing_tasks import process_routing_job
from cosmonaut_app.tasks.upload_tasks import UploadTask, process_upload_task


class CeleryConfig(BaseCeleryConfig):
    """COSMONAUT's Celery settings: the time limits.

    Routes and the beat schedule do not belong here: they come from
    ``task_specs``. The timezone is the framework's UTC default; the cleanup's
    03:00 is therefore 03:00 UTC.
    """

    # No wall-clock ceiling on tasks. Redundant since cosmo-ecosystem v0.4.0, which
    # made None the framework default after this app hit the former 65-minute
    # hard limit — kept explicit on purpose, so a future framework default cannot
    # silently reinstate one. The reason is domain-specific and only visible here:
    # a routing job's runtime scales with the survey area, sensor-routing is O(n²)
    # over the measurement points and is not tileable, so any blanket limit kills
    # exactly the large surveys the app exists for. Set a number only together
    # with a measured upper bound.
    task_soft_time_limit = None
    task_time_limit = None


celery_config = CeleryConfig

task_specs = [
    TaskSpec(
        fn=process_routing_job,
        name=NAME_ROUTING_TASK,
        queue="routing",
        base_task=None,
    ),
    TaskSpec(
        fn=process_upload_task,
        name=NAME_UPLOAD_TASK,
        queue="upload",
        base_task=UploadTask,
    ),
]

# matplotlib/PIL/pyogrio/rasterio all run inside worker processes and log noisily.
excluded_log_packages = EXCLUDED_LOG_PACKAGES

# Log rows older than this are deleted by the framework cleanup.
log_retention_days = 30
