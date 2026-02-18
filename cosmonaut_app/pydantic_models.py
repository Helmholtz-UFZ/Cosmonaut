import logging
import re
import sys
from datetime import date
from pyproj.exceptions import CRSError
from pyproj import CRS

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, Field
from sensor_routing.full_pipeline_cli import FullPipelineConfig
from typing import Annotated, Any, Dict, List

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
        # Checks syntax and domain
        # Skip deliverability check during tests (pytest environment)
        in_tests = "pytest" in sys.modules
        validate_email(email, check_deliverability=not in_tests)
        return email  # Return email if valid
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email: {e}")


def validate_job_id(job_id: str) -> str:
    """Validate job id.

    The function further creates input dir for the job. If the job id was
    changed the function and moves all previously uploaded files into the
    new input dir.
    """
    log.debug(f"Check job id {job_id}")

    job_id_regex = r"^\w+$"
    if not re.match(job_id_regex, job_id):
        raise ValueError("Job id must contain only letters numbers or underscore")

    min_job_id_length = 8
    max_job_id_length = 50

    if len(job_id) < min_job_id_length or len(job_id) > max_job_id_length:
        raise ValueError(
            f"Job id must be between {min_job_id_length} and {max_job_id_length} characters"  # noqa
        )
    return job_id


class UserModel(FullPipelineConfig):
    """Pydantic model for user input."""

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
        Dict[str, Any],
        Field(
            {
                "file_name": "No file uploaded",
                "len": 0,
                "epsg": 25832,
                "center": [51.70, 11.20],
                "zoom": 10,
            },
            description="Upload a file with the membership data",
            title="Membership upload",
            json_schema_extra={"type": "file-upload"},
        ),
    ]
    predictor_upload: Annotated[
        Dict[str, Any],
        Field(
            {"file_name": "No file uploaded", "len": 0},
            description="Upload a file with the predictor data",
            title="Predictor upload",
            json_schema_extra={"type": "file-upload"},
        ),
    ]
    selected_road_tags: Annotated[
        List[str],
        Field(
            [],
            description="Selected road tags from OpenStreetMap.",
            title="Selected road tags",
            json_schema_extra={"type": "list"},
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
