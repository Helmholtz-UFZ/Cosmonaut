import logging
import re

# from sensor_routing.sensor_routing_cli import Config

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, Field, BaseModel, ConfigDict
from typing import Annotated, Any, Dict, List


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


class FullPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    segment_number: Annotated[
        int,
        Field(
            1,
            alias="sn",
            ge=1,
            le=10,
            description="Must be between 1 and 10",
            title="Segments per class",
            type="integer",
        ),
    ]
    lower_benefit_limit: Annotated[
        float,
        Field(
            0.1,
            alias="lbf",
            ge=0.0,
            le=1.0,
            description="Must be between 0.0 and 1.0",
            title="Lower benefit limit",
            type="float",
        ),
    ]
    time_limit: Annotated[
        int,
        Field(
            80,
            alias="tl",
            gt=0,
            description="Must be a positive number",
            title="Time limit [h]",
            type="integer",
        ),
    ]
    optimization_objective: Annotated[
        str,
        Field(
            "d",
            alias="oo",
            pattern="^(d|t|i)$",
            description="Must be 'd' (distance) or 't' (time)",
            title="Objective",
            type="text",
        ),
    ]
    max_aco_iteration: Annotated[
        int,
        Field(
            50,
            alias="mai",
            gt=0,
            description="Must be a positive integer",
            title="Max ACO iteration",
            type="integer",
        ),
    ]
    ant_no: Annotated[
        int,
        Field(
            500,
            alias="an",
            gt=0,
            description="Must be a positive integer",
            title="Ant number",
            type="integer",
        ),
    ]
    is_reversed: Annotated[
        bool,
        Field(
            False,
            alias="ir",
            description="Must be true or false",
            title="Reversed network",
            type="checkbox",
        ),
    ]
    working_directory: Annotated[
        str,
        Field(
            "work_dir",
            alias="wd",
            description="Working directory path",
            title="Working directory",
            type="text",
        ),
    ]
    max_distance: Annotated[
        int,
        Field(
            50,
            alias="md",
            gt=0,
            description="Must be a positive integer",
            title="Max distance",
            type="integer",
        ),
    ]
    benefit_type: Annotated[
        str,
        Field(
            "t",
            alias="bt",
            pattern="^(t|m)$",
            description="Must be 't' (total) or 'm' (max)",
            title="Benefit type",
            type="text",
        ),
    ]
    route_type: Annotated[
        str,
        Field(
            "g",
            alias="rt",
            pattern="^(g|b)$",
            description="Must be 'g' (good) or 'b' (bad)",
            title="Route type",
            type="text",
        ),
    ]

    # HPE-specific parameters
    num_points: Annotated[
        int,
        Field(
            50,
            alias="np",
            gt=0,
            description="Number of points for HPE optimization",
            title="Number of points",
            type="integer",
        ),
    ]
    goal_ratio: Annotated[
        float,
        Field(
            100.0,
            alias="gr",
            gt=0,
            description="Goal ratio for HPE optimization",
            title="Goal ratio",
            type="float",
        ),
    ]
    use_fixed_seeds: Annotated[
        bool,
        Field(
            False,
            alias="ufs",
            description="Use fixed seeds for reproducible results",
            title="Use fixed seeds",
            type="checkbox",
        ),
    ]
    debug_seed: Annotated[
        int,
        Field(
            42,
            alias="ds",
            gt=0,
            description="Debug seed value",
            title="Debug seed",
            type="integer",
        ),
    ]
    allow_fewer_points: Annotated[
        bool,
        Field(
            True,
            alias="afp",
            description="Allow fewer points than requested",
            title="Allow fewer points",
            type="checkbox",
        ),
    ]


class UserModel(FullPipelineConfig):
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
        Dict[str, Any],
        Field(
            {
                "file_name": "No file uploaded",
                "len": 0,
                "epsg": 25832,
                "center": [51.70, 11.20],
                "zoom": 10,
            },
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
    epsg: Annotated[
        int,
        Field(
            25832,
            description="EPSG code of the uploaded classification data.",
            title="EPSG code",
            type="text",
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
