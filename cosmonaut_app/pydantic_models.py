"""Pydantic models for user input and persisted job state.

``UserModel`` subclasses ``cosmo_suite.pydantic_models.BaseJobConfig``, the minimal
contract: a ``job_id`` validated by ``validate_job_id`` plus
``validate_assignment=True``, so no model can be assigned an invalid job id after
construction either.

It does **not** subclass ``UploadJobConfig``. That layer adds ``upload_file_name``
for the framework ``Job``'s single-upload pattern; cosmonaut has two uploads, each
with its own JSON column (``membership_upload`` / ``predictor_upload``), and
``JobTable`` has no ``upload_file_name`` column — inheriting it would make
``model_dump()`` produce a key ``CosmonautJob.save()`` cannot write. Revisit only
if the framework ``Job`` is adopted.
"""

import logging
from datetime import date
from typing import Annotated, Any

from cosmo_suite.pydantic_models import BaseJobConfig
from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, Field
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


class UserModel(BaseJobConfig, FullPipelineConfig):
    """Pydantic model for user input.

    ``job_id`` and ``validate_assignment=True`` come from ``BaseJobConfig``.
    """

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
