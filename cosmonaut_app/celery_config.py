from celery import Celery
from cosmonaut_app.config import REDIS_PORT


def make_celery(app_name=__name__):
    redis_url = f"redis://localhost:{REDIS_PORT}/0"
    return Celery(
        app_name,
        backend=redis_url,
        broker=redis_url,
    )


celery = make_celery()
