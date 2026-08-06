"""Celery configuration for COSMONAUT App.

Everything generic (broker/result URL, Redis socket timeouts, serialization,
worker recycling, beat file location) comes from
``cosmo_suite.celery_config.BaseCeleryConfig``. Only the domain routing, the beat
schedule and the two overrides below are set here.
"""

from celery.schedules import crontab
from cosmo_suite.celery_config import BaseCeleryConfig


class CeleryConfig(BaseCeleryConfig):
    """Celery configuration class.

    This configuration uses Redis as both the message broker and result backend.
    Tasks are routed to different queues based on their type.
    """

    # Task routing - different queues for different task types.
    # The framework's maintenance route is kept: the worker registers the
    # framework test task, and cosmonaut's own cleanup task is routed below.
    task_routes = {
        "cosmonaut_app.tasks.routing_tasks.*": {"queue": "routing"},
        "cosmonaut_app.tasks.upload_tasks.*": {"queue": "upload"},
        "cosmonaut_app.tasks.maintenance_tasks.*": {"queue": "default"},
        "cosmo_suite.tasks.test_tasks.*": {"queue": "test"},
    }

    # Deliberately switched off, unlike BaseCeleryConfig (1 h soft / 65 min hard):
    # a routing job's runtime scales with the area — sensor-routing is O(n²) over
    # the measurement points and has no tiling — so a wall-clock ceiling would kill
    # exactly the large surveys the app exists for. Reinstate only together with a
    # measured upper bound.
    task_soft_time_limit = None
    task_time_limit = None

    # Celery Beat schedule - periodic tasks. Cosmonaut's cleanup, not the
    # framework's: the framework task cleans up through cosmo_suite.db_manager,
    # which this app does not use (db_manager.py is not part of slice 1).
    beat_schedule = {
        "daily-cleanup": {
            "task": "cosmonaut_app.tasks.maintenance_tasks.cleanup",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "default"},
        },
    }
