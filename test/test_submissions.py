"""Submissions name no queue: the routes assembled from the task specs decide."""

from types import SimpleNamespace
from unittest import mock

import pytest

from cosmonaut_app.submissions import (
    NAME_ROUTING_TASK,
    NAME_UPLOAD_TASK,
    manager,
    submit_routing_job,
    submit_upload_job,
)

JOB = SimpleNamespace(model=SimpleNamespace(job_id="test_submissions_job"))


@pytest.mark.parametrize(
    ("submit", "task_name", "queue"),
    [
        (submit_routing_job, NAME_ROUTING_TASK, "routing"),
        (lambda job: submit_upload_job(job, 4326), NAME_UPLOAD_TASK, "upload"),
    ],
)
def test_submission_leaves_the_queue_to_the_domain_routes(submit, task_name, queue):
    app = manager().app
    with mock.patch.object(app, "send_task") as send_task:
        submit(JOB)

    assert send_task.call_args.args[0] == task_name
    assert "queue" not in send_task.call_args.kwargs
    # What the broker then does with it: the route from the task spec.
    assert app.amqp.router.route({}, task_name)["queue"].name == queue
