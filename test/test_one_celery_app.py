"""Guardrail: a web process holds exactly one Celery app, the framework's.

Runs in a fresh interpreter: Celery keeps every app ever built in a process-wide
registry, and this session builds its own. The app is imported with all its pages,
the framework ones included, as the web server does, so a page or job module that
builds a second instance shows up here.
"""

import json
import os
import subprocess
import sys

from celery.schedules import crontab
from cosmo_ecosystem.celery_app import NAME_CLEANUP_TASK, get_app

NAME_ROUTING_TASK = "cosmonaut_app.tasks.routing_tasks.process_routing"
NAME_UPLOAD_TASK = "cosmonaut_app.tasks.upload_tasks.process_upload"

REPORT = """
import json

from celery import _state

import cosmonaut_app.app  # imports every page, the framework ones included
from cosmo_ecosystem.background_job_manager import background_job_manager

apps = list(_state._get_active_apps())
print(json.dumps({
    "count": len(apps),
    "is_managers": apps[0] is background_job_manager.app,
    "routes": background_job_manager.app.conf.task_routes,
}))
"""


def test_web_process_holds_one_celery_app_with_the_domain_routes():
    result = subprocess.run(
        [sys.executable, "-c", REPORT],
        env=dict(os.environ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])

    assert report["count"] == 1
    assert report["is_managers"]
    # The web process routes the domain tasks too, not only the worker.
    assert report["routes"][NAME_ROUTING_TASK] == {"queue": "routing"}
    assert report["routes"][NAME_UPLOAD_TASK] == {"queue": "upload"}


def test_beat_runs_only_the_framework_cleanup_at_three_on_maintenance():
    """The app's own daily cleanup is gone; the framework's takes its slot."""
    schedule = get_app().conf.beat_schedule

    assert list(schedule) == [NAME_CLEANUP_TASK]
    entry = schedule[NAME_CLEANUP_TASK]
    assert entry["options"]["queue"] == "maintenance"
    assert entry["schedule"] == crontab(minute=0, hour=3)
