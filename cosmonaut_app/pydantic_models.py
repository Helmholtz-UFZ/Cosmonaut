"""Pydantic models for user input and persisted job state.

``validate_job_id`` comes from ``cosmo_suite.pydantic_models``. ``UserModel``
deliberately does **not** subclass the framework's ``BaseJobConfig``: that contract
carries an ``upload_file_name`` field for the framework ``Job``'s single-upload
model, and cosmonaut has two uploads, each with its own JSON column
(``membership_upload`` / ``predictor_upload``). Measured consequence of inheriting
it: ``model_dump()`` gains an ``upload_file_name`` key that ``JobTable`` has no
column for, so ``CosmonautJob.save()`` breaks — the fix would be a permanently NULL
production column for a field the domain has no use for. Revisit when the framework
``Job`` is actually adopted (that is what ``BaseJobConfig`` is a contract for);
``cosmonaut_job.py`` is not part of slice 1.
"""

import logging
from datetime import date
from typing import Annotated, Any

from cosmo_suite.pydantic_models import validate_job_id
from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, ConfigDict, Field
from pyproj import CRS
from pyproj.exceptions import CRSError
from sensor_routing.full_pipeline_cli import FullPipelineConfig

log = logging.getLogger(__name__)


def check_epsg(epsg: str | int) -> tuple[int | None, bool]:
    try:
        if isinstance(epsg, str) and epsg.upper().startswith("EPSG:"):
            epsg = epsg[5:]
        epsg = int(epsg)
    except TypeError:
        raise ValueError(
            "EPSG code must be an integer or string representing an integer"
        )

    # Validate with pyproj
    try:
        CRS.from_epsg(epsg)
    except (CRSError, TypeError):
        raise ValueError(f"EPSG code {epsg} is not valid")

    return epsg


def check_email(email: str) -> str:
    """Validate an email address using the email-validator library allow empty email."""
    if email == "":
        return email
    try:
        # Checks syntax only — deliverability (DNS/MX) checks are unreliable
        # and cause inconsistencies between web process and Celery worker
        validate_email(email, check_deliverability=False)
        return email  # Return email if valid
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email: {e}")


class UserModel(FullPipelineConfig):
    """Pydantic model for user input."""

    # Taken from the framework's BaseJobConfig even though the base class itself is
    # not inherited (see the module docstring): without it, `job.model.job_id = x`
    # bypasses validate_job_id entirely, so an invalid id can reach the database and
    # the work-dir path. Validation on construction alone is not enough.
    model_config = ConfigDict(validate_assignment=True)

    # Input fields
    email: Annotated[
        str,
        Field(
            "",
            description="Email address to be notified when job submission is complete.",
            title="Email",
            json_schema_extra={"type": "email"},
        ),
        AfterValidator(check_email),
    ]
    job_id: Annotated[
        str,
        Field(
            "poised_python_of_wonder",
            description='Identifier for your submission. Only letters, numbers and "_".',  # noqa
            title="Job ID",
            json_schema_extra={"type": "text"},
        ),
        AfterValidator(validate_job_id),
    ]
    membership_upload: Annotated[
        dict[str, Any],
        Field(
            {
                "file_name": "No file uploaded",
                "len": 0,
                "epsg": 25832,
                "center": [51.70, 11.20],
                "zoom": 10,
                "street_processing": "PENDING",
            },
            description="Upload a file with the membership data",
            title="Membership upload",
            json_schema_extra={"type": "file-upload"},
        ),
    ]
    predictor_upload: Annotated[
        dict[str, Any],
        Field(
            {"file_name": "No file uploaded", "len": 0},
            description="Upload a file with the predictor data",
            title="Predictor upload",
            json_schema_extra={"type": "file-upload"},
        ),
    ]
    epsg: Annotated[
        int,
        Field(
            25832,
            description="EPSG code of the uploaded classification data.",
            title="EPSG code",
            json_schema_extra={"type": "text"},
        ),
        AfterValidator(check_epsg),
    ]


class JobModel(UserModel):
    """Pydantic model for job information stored in the database."""

    submitted: bool = False
    notified_end: bool = False
    stage: int = 0
    status: str = "PENDING"
    # TODO get from sensor_routing version
    version: str = "0.1.5"
    celery_task_id: str | None = None
    start_date: date | None = None
