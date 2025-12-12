"""Celery configuration for COSMONAUT App."""

from cosmonaut_app.config import REDIS_HOST, REDIS_DB, REDIS_PASSWORD


class CeleryConfig:
    """Celery configuration class.

    This configuration uses Redis as both the message broker and result backend.
    Tasks are routed to different queues based on their type.
    """

    # Build Redis URL with optional password
    # Handle GitLab CI service link format (tcp://redis:6379)
    _redis_host = REDIS_HOST
    if _redis_host.startswith("tcp://"):
        _redis_host = _redis_host.replace("tcp://", "")
        if ":" in _redis_host:
            _redis_host, _port = _redis_host.split(":")
            REDIS_PORT = _port

    _redis_auth = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    _redis_url = f"redis://{_redis_auth}{_redis_host}:{REDIS_PORT}/{REDIS_DB}"

    # Broker and result backend
    broker_url = _redis_url
    result_backend = _redis_url

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

    # Worker settings for better performance and reliability
    worker_prefetch_multiplier = 1  # Fair distribution of tasks
    task_acks_late = True  # Acknowledge task after completion, not before
    worker_max_tasks_per_child = 50  # Restart worker after 50 tasks (memory cleanup)
    worker_max_memory_per_child = 512000  # 512MB per worker process
