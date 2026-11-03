"""Test that the end mail is retried until it was actually sent.

``send_mail`` never raises into its callers, so it has to say whether the mail
left; the job's ``notified_end`` flag may only be set for a mail that did.
Runs against real Postgres and object storage; only the SMTP connection is faked.
"""

from unittest import mock

import pytest

from cosmonaut_app import email_service
from cosmonaut_app.constants.general import JOB_STATUS_RUNNING
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.tasks.routing_tasks import process_routing_job
from test.help_functions_tests import remove_job, set_run_columns


@pytest.fixture
def running_job():
    """Yield a saved RUNNING job with an email; remove it afterwards."""
    job = CosmonautJob()
    job.model.celery_task_id = "task-of-a-test"
    job.model.email = "test@ufz.de"
    job.save()
    set_run_columns(job.job_id, status=JOB_STATUS_RUNNING, submitted=True)
    yield job
    remove_job(job.job_id)


def _smtp_server(smtp):
    """Make ``smtplib.SMTP`` a real-mail configuration with the given double."""
    return (
        mock.patch.object(email_service, "EMAIL_SERVER", "smtp.example.org"),
        mock.patch("cosmonaut_app.email_service.smtplib.SMTP", smtp),
    )


def test_send_mail_reports_a_mail_the_smtp_server_refused():
    server, smtp = _smtp_server(mock.Mock(side_effect=OSError("connection refused")))
    with server, smtp:
        assert email_service.send_mail(["a@ufz.de"], "subject", "body") is False


def test_send_mail_reports_a_mail_that_was_sent():
    server, smtp = _smtp_server(mock.MagicMock())
    with server, smtp:
        assert email_service.send_mail(["a@ufz.de"], "subject", "body") is True


def test_send_mail_reports_a_mail_it_could_not_even_build():
    """Header construction is part of the never-raises promise."""
    server, smtp = _smtp_server(mock.MagicMock())
    with server, smtp:
        assert email_service.send_mail([None], "subject", "body") is False


def test_a_failed_end_mail_leaves_notified_end_unset_so_it_is_retried(running_job):
    """The job has no uploads, so the routing pipeline fails; the mail is
    refused, and the next run's end mail must still be due."""
    job_id = running_job.job_id
    server, smtp = _smtp_server(mock.Mock(side_effect=OSError("connection refused")))

    with server, smtp:
        process_routing_job(None, job_id)

    assert DataBaseManager.get_job_columns(job_id)["notified_end"] is False


def test_a_resubmit_before_the_end_mail_is_flagged_keeps_the_next_runs_mail_due(
    running_job,
):
    """The mail of run 1 is out; the user resubmits before notified_end is
    written. The flag must not be set over the new run."""
    job_id = running_job.job_id

    def mail_goes_out_and_the_user_restarts(_to, subject, _body):
        if "submitted" in subject:
            return True
        with mock.patch(
            "cosmonaut_app.cosmonaut_job.submit_routing_job",
            return_value=("task-of-the-restart", False),
        ):
            restarted = CosmonautJob(job_id=job_id)
            restarted.reset()
            restarted.submit()
        return True

    with mock.patch(
        "cosmonaut_app.tasks.routing_tasks.send_mail",
        side_effect=mail_goes_out_and_the_user_restarts,
    ):
        process_routing_job(None, job_id)

    row = DataBaseManager.get_job_columns(job_id)
    assert row["status"] == JOB_STATUS_RUNNING
    assert row["notified_end"] is False
