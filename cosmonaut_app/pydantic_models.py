import logging
import re

from sensor_routing.sensor_routing_cli import Config

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, Field
from typing import Annotated, Dict, List


def check_email(email: str) -> str:
    """Validate an email address using the email-validator library allow empty email."""
    if email == "":
        return email
    try:
        # Checks syntax and domain
        validate_email(email, check_deliverability=True)
        return email  # Return email if valid
    except EmailNotValidError as e:
        raise ValueError(f"Invalid email: {e}")


def validate_job_id(job_id: str) -> str:
    """Validate job id.

    The function further creates input dir for the job. If the job id was
    changed the function and moves all previously uploaded files into the
    new input dir.
    """
    logging.debug(f"Check job id {job_id}", extra={"tag": "frontend"})

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


class UserModel(Config):
    """Pydantic model for user input."""

    # Input fields
    email: Annotated[
        str,
        Field(
            "test@test.com",
            description="Email address to be notified when job submission is complete.",
            title="Email",
            type="email",
        ),
        AfterValidator(check_email),
    ]
    job_id: Annotated[
        str,
        Field(
            "poised_python_of_wonder",
            description='Identifier for your submission. Only letters, numbers and "_".',  # noqa
            title="Job ID",
            type="text",
        ),
        AfterValidator(validate_job_id),
    ]
    classification_upload: Annotated[
        Dict[str, Dict],
        Field(
            {},
            description=("Upload a file with the crns data"),
            title="Crns upload",
            type="file-upload",
        ),
    ]
    selected_road_tags: Annotated[
        List[str],
        Field(
            [],
            description="Selected road tags from OpenStreetMap.",
            title="Selected road tags",
            type="list",
        ),
    ]


class JobModel(UserModel):
    """Pydantic model for job information stored in the database."""

    submitted: bool = False
    notified_end: bool = False
    stage: int = 0
    status: str = "PENDING"
    # TODO get from sensor_routing version
    version: str = "0.1.5"
