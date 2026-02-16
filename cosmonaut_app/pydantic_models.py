import logging
import re
import sys
from datetime import date
from pyproj.exceptions import CRSError
from pyproj import CRS


# from sensor_routing.sensor_routing_cli import FullPipelineConfig

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, Field, BaseModel, ConfigDict
from typing import Annotated, Any, Dict, List


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


# Local copy of FullPipelineConfig: sensor_routing uses Field(type=...) but
# dash_form_factory.FormFactory reads exclusively from json_schema_extra["type"].
# We keep this copy so FormFactory renders the correct form widgets.
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
            json_schema_extra={"type": "integer"},
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
            json_schema_extra={"type": "float"},
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
            json_schema_extra={"type": "integer"},
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
            json_schema_extra={"type": "text"},
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
            json_schema_extra={"type": "integer"},
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
            json_schema_extra={"type": "integer"},
        ),
    ]
    is_reversed: Annotated[
        bool,
        Field(
            False,
            alias="ir",
            description="Must be true or false",
            title="Reversed network",
            json_schema_extra={"type": "checkbox"},
        ),
    ]
    working_directory: Annotated[
        str,
        Field(
            "work_dir",
            alias="wd",
            description="Working directory path",
            title="Working directory",
            json_schema_extra={"type": "text"},
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
            json_schema_extra={"type": "integer"},
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
            json_schema_extra={"type": "text"},
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
            json_schema_extra={"type": "text"},
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
            json_schema_extra={"type": "integer"},
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
            json_schema_extra={"type": "float"},
        ),
    ]
    use_fixed_seeds: Annotated[
        bool,
        Field(
            False,
            alias="ufs",
            description="Use fixed seeds for reproducible results",
            title="Use fixed seeds",
            json_schema_extra={"type": "checkbox"},
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
            json_schema_extra={"type": "integer"},
        ),
    ]
    allow_fewer_points: Annotated[
        bool,
        Field(
            True,
            alias="afp",
            description="Allow fewer points than requested",
            title="Allow fewer points",
            json_schema_extra={"type": "checkbox"},
        ),
    ]


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
