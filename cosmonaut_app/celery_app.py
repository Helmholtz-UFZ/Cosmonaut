"""Celery application with task registration.

This module creates the Celery worker entry point by importing the shared
Celery app and registering all task functions. The worker command points here:

    celery -A cosmonaut_app.celery_app.celery worker ...

Separated from background_job_manager to break a circular import:
    tasks/*.py → cosmonaut_job → background_job_manager → tasks/*.py
"""

from cosmonaut_app.background_job_manager import (
    NAME_MAINTENANCE_CLEANUP_TASK,
    NAME_ROUTING_TASK,
    NAME_TEST_TASK,
    NAME_UPLOAD_TASK,
    background_job_manager,
)
from cosmonaut_app.tasks.maintenance_tasks import MaintenanceTask, cleanup_task
from cosmonaut_app.tasks.routing_tasks import RoutingTask, process_routing_job
from cosmonaut_app.tasks.test_tasks import TestTask, test_sleep_task
from cosmonaut_app.tasks.upload_tasks import UploadTask, process_upload_task

app = background_job_manager.app

app.task(bind=True, base=RoutingTask, name=NAME_ROUTING_TASK)(process_routing_job)
app.task(bind=True, base=TestTask, name=NAME_TEST_TASK)(test_sleep_task)
app.task(bind=True, base=MaintenanceTask, name=NAME_MAINTENANCE_CLEANUP_TASK)(
    cleanup_task
)
app.task(bind=True, base=UploadTask, name=NAME_UPLOAD_TASK)(process_upload_task)

# Expose for: celery -A cosmonaut_app.celery_app.celery worker ...
celery = app
