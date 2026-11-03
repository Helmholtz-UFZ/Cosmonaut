"""Test that the end mail is retried until it was actually sent.

``send_mail`` never raises into its callers, so it has to say whether the mail
left; the job's ``notified_end`` flag may only be set for a mail that did.
Runs against real Postgres and object storage; only the SMTP connection is faked.
"""

from unittest import mock

import pytest
from cosmo_ecosystem import job_persistence

from cosmonaut_app import email_service
from cosmonaut_app.constants.general import JOB_STATUS_RUNNING
from cosmonaut_app.cosmonaut_job import CosmonautJob
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.tasks.routing_tasks import process_routing_job


@pytest.fixture
def running_job():
    """Yield a saved RUNNING job with an email; remove it afterwards."""
    job = CosmonautJob()
    job.model.status = JOB_STATUS_RUNNING
    job.model.submitted = True
    job.model.celery_task_id = "task-of-a-test"
    job.model.email = "test@ufz.de"
    job.save()
    yield job
    job_persistence.delete_job(job.job_id)


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
