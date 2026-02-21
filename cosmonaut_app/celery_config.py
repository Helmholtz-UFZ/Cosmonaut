"""Celery configuration for COSMONAUT App."""

from celery.schedules import crontab

from cosmonaut_app.config import REDIS_HOST, REDIS_DB, REDIS_PASSWORD, REDIS_PORT


def _get_redis_port():
    """Get Redis port, handling GitLab CI service link format."""
    port = REDIS_PORT
    # GitLab CI may set REDIS_PORT as 'tcp://redis:6379' format
    if port and port.startswith("tcp://"):
        # Extract port from URL format
        port = port.split(":")[-1]
    return port


class CeleryConfig:
    """Celery configuration class.

    This configuration uses Redis as both the message broker and result backend.
    Tasks are routed to different queues based on their type.
    """

    # Build Redis URL with optional password
    _redis_auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    _redis_port = _get_redis_port()
    _redis_url = f"redis://{_redis_auth}{REDIS_HOST}:{_redis_port}/{REDIS_DB}"

    # Broker and result backend
    broker_url = _redis_url
    result_backend = _redis_url
    broker_connection_retry_on_startup = True

    # Serialization
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]

    # Timezone
    timezone = "UTC"
    enable_utc = True

    # Task routing - different queues for different task types
    task_routes = {
        "cosmonaut_app.tasks.routing_tasks.*": {"queue": "routing"},
    }

    # Logging - prevent Celery from hijacking the root logger and removing
    # our PostgreSQL handler (which is configured in app.py / logger.py)
    worker_hijack_root_logger = False

    # Worker settings for better performance and reliability
    worker_prefetch_multiplier = 1  # Fair distribution of tasks
    task_acks_late = True  # Acknowledge task after completion, not before
    # Restart worker after 50 tasks (memory cleanup)
    worker_max_tasks_per_child = 50
    worker_max_memory_per_child = 512000  # 512MB per worker process

    # Celery Beat schedule - periodic tasks
    beat_schedule = {
        "daily-cleanup": {
            "task": "cosmonaut_app.tasks.maintenance_tasks.cleanup",
            "schedule": crontab(hour=3, minute=0),
        },
    }
