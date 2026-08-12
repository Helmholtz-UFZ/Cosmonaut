"""Celery application with task registration.

This module creates the Celery worker entry point by importing the shared
Celery app and registering all task functions. The worker command points here:

    celery -A cosmonaut_app.celery_app.celery worker ...

Separated from background_job_manager to break a circular import:
    tasks/*.py → cosmonaut_job → background_job_manager → tasks/*.py
"""

from cosmo_suite.tasks.test_tasks import long_running_test_task

from cosmonaut_app.background_job_manager import (
    NAME_MAINTENANCE_CLEANUP_TASK,
    NAME_ROUTING_TASK,
    NAME_TEST_TASK,
    NAME_UPLOAD_TASK,
    background_job_manager,
)
from cosmonaut_app.tasks.maintenance_tasks import MaintenanceTask, cleanup_task
from cosmonaut_app.tasks.routing_tasks import RoutingTask, process_routing_job
from cosmonaut_app.tasks.upload_tasks import UploadTask, process_upload_task

app = background_job_manager.app

app.task(bind=True, base=RoutingTask, name=NAME_ROUTING_TASK)(process_routing_job)
# The test task comes from the framework. NAME_TEST_TASK is the framework's name,
# and the framework worker-management page submits exactly that name — registering
# a local task under a local name would leave the page's button enqueueing into a
# queue nobody consumes.
app.task(bind=True, name=NAME_TEST_TASK)(long_running_test_task)
app.task(bind=True, base=MaintenanceTask, name=NAME_MAINTENANCE_CLEANUP_TASK)(
    cleanup_task
)
app.task(bind=True, base=UploadTask, name=NAME_UPLOAD_TASK)(process_upload_task)

# Expose for: celery -A cosmonaut_app.celery_app.celery worker ...
celery = app
