import base64
import csv
import glob
import json
import logging
import math
import os
import uuid
from datetime import date

import pandas as pd
from cosmo_ecosystem import job_log, job_persistence
from cosmo_ecosystem.base_job import BaseJob
from cosmo_ecosystem.job_retention import days_to_live
from pyproj import CRS, Transformer
from sensor_routing.constants import (
    MEMBERSHIP_FILENAME,
    OSM_FILENAME,
    PREDICTOR_FILENAME,
    ROUTE_FILENAME,
)
from sensor_routing.full_pipeline_cli import (
    parse_membership_file,
    parse_predictor_file,
    validate_predictor_membership_consistency,
)

from cosmonaut_app.background_job_manager import background_job_manager
from cosmonaut_app.constants.general import (
    GPX_FILE,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    OSM_DATA_DOWNLOAD_FILE,
    OSM_DATA_EDITED_FILE,
    QR_CODE_FILE,
    ROUTE_OPTIONS_FILE,
    STREET_DERIVED_HASHES_FILE,
    STREET_EDITS_FILE,
)
from cosmonaut_app.db_manager import DataBaseManager
from cosmonaut_app.error_handling import FileValidationError
from cosmonaut_app.navigation_routing import RouteCreator
from cosmonaut_app.pydantic_models import FullPipelineConfig, JobModel, StreetEdits

log = logging.getLogger(__name__)


def _transform_csv(input_file, epsg_input, epsg_output):
    """Transform coordinates in a CSV file from one CRS to another.

    Args:
        input_file: Path to the input CSV file.
        epsg_input: EPSG code of the input CRS.
        epsg_output: EPSG code of the output CRS.

    Returns:
        DataFrame with transformed coordinates.
    """
    log.info(f"Starting transformation of CSV file: {input_file}")

    if not input_file.endswith((".csv", ".txt")):
        log.error("Input file must be a CSV or TXT file.")
        raise ValueError("Input file must be a CSV file.")

    with open(input_file) as csvfile:
        sample = csvfile.read(4096)
        dialect = csv.Sniffer().sniff(sample)
        has_header = csv.Sniffer().has_header(sample)
        delimiter = dialect.delimiter

    crs_input = CRS.from_epsg(epsg_input)
    crs_output = CRS.from_epsg(epsg_output)
    transformer = Transformer.from_crs(crs_input, crs_output)

    df = pd.read_csv(input_file, delimiter=delimiter, header=0 if has_header else None)

    if not has_header:
        df.columns = [f"col_{i}" for i in range(len(df.columns))]

    potential_coord_cols = []
    for col in df.columns:
        if df[col].dtype.kind in "iuf":
            if (df[col].min() < 0 or df[col].max() > 1) and len(df[col].unique()) > 10:
                potential_coord_cols.append(col)

    if len(potential_coord_cols) == 2:
        x_col, y_col = potential_coord_cols
    elif has_header:
        x_candidates = [
            col
            for col in df.columns
            if any(term in col.lower() for term in ["east", "long", "x", "lon"])
        ]
        y_candidates = [
            col
            for col in df.columns
            if any(term in col.lower() for term in ["north", "lat", "y"])
        ]

        if len(x_candidates) > 0 and len(y_candidates) > 0:
            x_col = x_candidates[0]
            y_col = y_candidates[0]
        else:
            raise ValueError("Could not automatically identify coordinate columns.")
    else:
        raise ValueError("Could not automatically identify coordinate columns.")

    df["Latitude"], df["Longitude"] = transformer.transform(
        df[x_col].values, df[y_col].values
    )

    df.drop([x_col, y_col], axis=1, inplace=True)

    return df


def _get_bounds(classification_df):
    """Calculate the rectangular bounds of the given points.

    Returns:
        A list containing [[min_lat, min_lon], [max_lat, max_lon]].
    """
    lon = classification_df.Longitude
    lat = classification_df.Latitude

    min_lon, max_lon = lon.min(), lon.max()
    min_lat, max_lat = lat.min(), lat.max()

    return [[min_lat, min_lon], [max_lat, max_lon]]


class CosmonautJob(BaseJob):
    """
    This class represents a job submission by the user.

    It submits jobs to the PostgreSQL database,
    uploads the file to the object storage
    and can retrieve the job again.

    All business data is stored in self.model (JobModel instance).
    Filesystem paths are stored as direct instance attributes.

    Implements ``cosmo_ecosystem.base_job.BaseJob``: ``job_id``, ``save``,
    ``delete``, ``submit`` and ``time_to_live`` are what framework code may call
    on a job it did not build. Everything else here is domain.

    Persistence is ``cosmo_ecosystem.job_persistence``: constructing a job reads
    its row only and ``working_dir`` is just the path. Code that reads the files
    calls ``job_persistence.work_dir(job_id)`` (or ``pull_file`` for one file)
    first. ``save`` uploads the work dir, then writes the row; methods that
    change files pull before they write, so the upload cannot push an outdated
    local copy over a newer stored one. ``update_columns`` writes named columns
    and touches no storage.
    """

    @property
    def job_id(self) -> str:
        """Return the job's unique id.

        The contract member. This app stores the id inside the Pydantic model,
        so the property is what lets generic framework code take an id without
        knowing that. Read-only on purpose: assigning through the model keeps
        validate_assignment in play, which is what stops an invalid id from
        reaching the database and the work-dir path.
        """
        return self.model.job_id

    def __init__(self, job_id=None):
        """Init class by id or make a new one.

        Args:
            job_id: Load an existing job's row. ``None`` creates a new job.
                Construction makes no rclone call; call
                ``job_persistence.work_dir`` where the job's files are needed.

        Raises:
            JobNotFound: If ``job_id`` has no row.
        """
        if job_id is not None:
            log.info(f"Load job with id {job_id}")
            self.load(job_id)
        else:
            log.info("Create new job")
            self._blank_job()

    def load(self, job_id):
        """Load the job's row into the model. Reads the database only."""
        job_data = job_persistence.load_row(job_id)

        # Extract config JSON and merge back into job_data
        config_data = job_data.pop("config", {})
        if config_data:
            job_data.update(config_data)

        # Instantiate model with all fields
        self.model = JobModel(**job_data)

        # Backfill street_processing for jobs saved before it was included
        # in upload_membership(). Can be removed once all existing jobs have
        # rotated out (retention ≤ DAYS_DELETE_SUBMITTED).
        if "street_processing" not in self.model.membership_upload:
            self.model.membership_upload["street_processing"] = "PENDING"
        # Backfill for jobs whose download predates its recorded checksum;
        # street_selector adopts the stored download's checksum on first use.
        # Removable on the same terms as the backfill above.
        if "download_sha256" not in self.model.membership_upload:
            self.model.membership_upload["download_sha256"] = None

        # The path only: the dir may be absent or stale on this pod.
        self.working_dir = job_persistence.local_dir(job_id)

    def _blank_job(self):
        """Create a new job with a unique ID."""
        self.model = JobModel()  # Initialize with defaults
        while True:
            job_id = str(uuid.uuid4())[:8]
            if not DataBaseManager.check_existence(job_id):
                break

        self.model.job_id = job_id
        self.model.start_date = date.today()
        self.working_dir = job_persistence.local_dir(job_id)

        self.save()

    def _row(self) -> dict:
        """Return the model as the job table's columns, config nested."""
        data = self.model.model_dump(mode="json")

        # Separate Config fields from JobModel fields
        config_field_names = set(FullPipelineConfig.model_fields.keys())
        config_data = {}
        for field_name in list(data.keys()):
            if field_name in config_field_names:
                config_data[field_name] = data.pop(field_name)

        # Add config as JSON field
        data["config"] = config_data
        return data

    def save(self):
        """Upload the work dir to object storage, then write the job's row.

        Files first, row second (``job_persistence.save``). Use it where inputs
        or outputs change, after pulling (``job_persistence.work_dir``): the
        upload is ``rclone copy --checksum``, so every local file that differs
        from the stored one wins. ``update_columns`` is the row-only write.
        """
        log.info(f"Save job {self.model.job_id}")
        # parameters.json is written before job_persistence.save creates the dir.
        os.makedirs(self.working_dir, exist_ok=True)
        self.dump_routing_params()
        job_persistence.save(self.model.job_id, self._row())

    def update_columns(self, *fields: str):
        """Write the named model fields to the job's row. No storage access.

        Args:
            *fields: ``JobModel`` field names. Config fields land in the one
                ``config`` column, which is written whole.
        """
        row = self._row()
        config_field_names = set(FullPipelineConfig.model_fields.keys())
        columns = {}
        for field_name in fields:
            column = "config" if field_name in config_field_names else field_name
            columns[column] = row[column]
        log.info(f"Update columns {sorted(columns)} of job {self.model.job_id}")
        job_persistence.update_columns(self.model.job_id, columns)

    def dump_routing_params(self):
        """
        Dump routing parameters (Config fields) to parameters.json in working directory.

        Extracts only the fields from the Config model and writes them to
        a JSON file in the working directory.
        """
        log.info(f"Dumping routing parameters for job {self.model.job_id}")

        # Get all data from model
        data = self.model.model_dump(mode="json")

        # Extract only Config fields
        config_field_names = set(FullPipelineConfig.model_fields.keys())
        config_data = {
            field_name: data[field_name]
            for field_name in data.keys()
            if field_name in config_field_names
        }

        # Write to parameters.json in working directory
        parameters_file = os.path.join(self.working_dir, "parameters.json")
        with open(parameters_file, "w") as f:
            json.dump(config_data, f, indent=2)

        log.debug(f"Routing parameters written to {parameters_file}")

    def _calculate_map_position_from_bounds(self, bounds):
        """
        Calculate center position and zoom level from bounds.

        Args:
            bounds: [[min_lat, min_lon], [max_lat, max_lon]]

        Returns:
            tuple: (position [lat, lon], zoom level)
        """
        min_lat, min_lon = bounds[0]
        max_lat, max_lon = bounds[1]

        # Calculate center
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        position = [center_lat, center_lon]

        # Calculate zoom level
        lat_diff = max_lat - min_lat
        lon_diff = max_lon - min_lon

        # Leaflet zoom calculation: fit the larger dimension
        # Each zoom level doubles the map scale
        # At zoom 0, the world is 256 pixels wide
        # World width in degrees is 360, height is ~170 (Web Mercator)
        lat_zoom = math.log2(170 * 800 / (lat_diff * 256)) if lat_diff > 0 else 15
        lon_zoom = math.log2(360 * 1000 / (lon_diff * 256)) if lon_diff > 0 else 15

        # Use the smaller zoom to ensure everything fits
        zoom = int(min(lat_zoom, lon_zoom, 18))  # Cap at zoom 18

        # Ensure minimum zoom of 5
        zoom = max(5, zoom)

        return position, zoom

    def delete(self):
        """Delete the job everywhere: remote prefix, local work dir and row.

        Delegates to ``cosmo_ecosystem.job_persistence.delete_job``, the same
        deletion the nightly cleanup and the job manager use.
        """
        job_persistence.delete_job(self.model.job_id)

    def upload_membership(self, file_name, content, epsg_input):
        """Upload and process membership CSV file; written through to storage."""
        log.info(f"Upload membership file {file_name} with EPSG {epsg_input}")
        # Pull before writing: the save below uploads the whole work dir.
        job_persistence.work_dir(self.model.job_id)

        # Remove previous membership file if it exists
        previous_file = self.model.membership_upload["file_name"]
        previous_file_path = os.path.join(self.working_dir, previous_file)
        if os.path.exists(previous_file_path):
            job_persistence.delete_files(self.model.job_id, [previous_file])
            log.info(f"Removed previous membership file {previous_file}")

        _content_type, content_string = content.split(",", 1)
        decoded = base64.b64decode(content_string)

        # Save with canonical name for sensor_routing pipeline
        file_path = os.path.join(self.working_dir, MEMBERSHIP_FILENAME)

        with open(file_path, "wb") as f:
            f.write(decoded)

        # Validate with sensor_routing parser
        try:
            membership_df = parse_membership_file(file_path)
        except Exception as e:
            log.info(f"Membership file validation failed: {e}")
            # Local only: the rejected file was never uploaded, and the stored
            # copy (if any) still matches the row.
            os.remove(file_path)
            raise FileValidationError(str(e))

        try:
            classification_data = _transform_csv(file_path, epsg_input, 4326)
        except ValueError as e:
            log.info(f"Error transforming CSV file: {e}")
            os.remove(file_path)
            raise FileValidationError(str(e))

        # Calculate bounds, position, and zoom
        bounds = _get_bounds(classification_data)
        position, zoom = self._calculate_map_position_from_bounds(bounds)

        # Store EPSG as model attribute
        self.model.epsg = epsg_input

        # Store information about the membership upload
        self.model.membership_upload = {
            "file_name": MEMBERSHIP_FILENAME,
            "len": len(classification_data),
            "center": position,
            "zoom": zoom,
            "bounds": bounds,
            "street_processing": "PENDING",
            # The upload worker records the new download's checksum.
            "download_sha256": None,
        }
        self.save()
        log.debug("Finished uploading and processing membership file")
        return file_path, bounds, membership_df

    def upload_predictor(self, content):
        """Upload and validate predictor CSV file; written through to storage."""
        log.info(f"Upload predictor file for job {self.model.job_id}")
        # Pull before writing: the save below uploads the whole work dir, and
        # the consistency check reads the membership file.
        job_persistence.work_dir(self.model.job_id)

        _content_type, content_string = content.split(",", 1)
        decoded = base64.b64decode(content_string)

        # Save with canonical name for sensor_routing pipeline
        file_path = os.path.join(self.working_dir, PREDICTOR_FILENAME)

        with open(file_path, "wb") as f:
            f.write(decoded)

        # Validate with sensor_routing parser
        try:
            parse_predictor_file(file_path)
        except Exception as e:
            log.info(f"Predictor file validation failed: {e}")
            os.remove(file_path)
            raise FileValidationError(str(e))

        # Cross-validate with membership file
        membership_path = os.path.join(self.working_dir, MEMBERSHIP_FILENAME)
        try:
            validate_predictor_membership_consistency(file_path, membership_path)
        except Exception as e:
            log.info(f"Predictor-membership consistency check failed: {e}")
            os.remove(file_path)
            raise FileValidationError(str(e))

        self.model.predictor_upload = {
            "file_name": PREDICTOR_FILENAME,
            "len": len(decoded),
        }
        self.save()
        log.debug("Finished uploading and processing predictor file")

    def delete_predictor(self):
        """Delete predictor file everywhere and reset predictor_upload."""
        log.info(f"Deleting predictor data for job {self.model.job_id}")

        job_persistence.delete_files(self.model.job_id, [PREDICTOR_FILENAME])

        default_predictor_upload = JobModel.model_fields["predictor_upload"].default
        self.model.predictor_upload = default_predictor_upload.copy()
        self.update_columns("predictor_upload")

        log.info(f"Predictor data deleted for job {self.model.job_id}")

    def get_street_processing_status(self):
        """Get street processing status, syncing from Celery if task is running.

        Returns:
            str: "PENDING", "RUNNING", "COMPLETED", or "FAILED"
        """
        sp = self.model.membership_upload["street_processing"]
        if sp in ("PENDING", "COMPLETED", "FAILED"):
            return sp
        # sp is a Celery task ID — check its status
        celery_info = background_job_manager.get_job_status(sp)
        celery_status = celery_info["status"]
        if celery_status == "SUCCESS":
            self.model.membership_upload["street_processing"] = "COMPLETED"
            self.model.stage = max(self.model.stage, 2)
            self.update_columns("membership_upload", "stage")
            return "COMPLETED"
        elif celery_status in ("FAILURE", "REVOKED"):
            self.model.membership_upload["street_processing"] = "FAILED"
            self.update_columns("membership_upload")
            return "FAILED"
        return "RUNNING"

    def delete_membership(self):
        """Delete membership, predictor, OSM files, plots everywhere; reset state.

        The street-edit intent is reset too.
        """
        log.info(f"Deleting membership data for job {self.model.job_id}")

        # Revoke running upload task if street_processing holds a task ID
        sp = self.model.membership_upload["street_processing"]
        if sp not in ("PENDING", "COMPLETED", "FAILED"):
            background_job_manager.revoke_job(sp, terminate=True)
            log.info(f"Revoked upload processing task {sp} for job {self.model.job_id}")

        # Plot files (new name + legacy names). Only those on this pod's disk
        # are found; the others are overwritten by the next upload's plots.
        plot_files = [
            os.path.relpath(plot_file, self.working_dir)
            for plot_file in glob.glob(os.path.join(self.working_dir, "*_output*.tif"))
        ]
        job_persistence.delete_files(
            self.model.job_id,
            [
                MEMBERSHIP_FILENAME,
                PREDICTOR_FILENAME,
                OSM_DATA_DOWNLOAD_FILE,
                OSM_DATA_EDITED_FILE,
                OSM_FILENAME,
                STREET_DERIVED_HASHES_FILE,
                # Legacy intent file of jobs edited before the street_edits column.
                STREET_EDITS_FILE,
                *plot_files,
                "membership.tif",
            ],
        )

        # Reset the uploads to default values
        default_membership_upload = JobModel.model_fields["membership_upload"].default
        self.model.membership_upload = default_membership_upload.copy()
        default_predictor_upload = JobModel.model_fields["predictor_upload"].default
        self.model.predictor_upload = default_predictor_upload.copy()
        # The street edits refer to the deleted network's roads. Explicit
        # defaults, not NULL: a legacy street_edits.json left on another pod's
        # disk is adopted only into a NULL column, so it can never come back.
        self.model.street_edits = StreetEdits()

        self.update_columns("membership_upload", "predictor_upload", "street_edits")

        log.info(f"Membership data deleted for job {self.model.job_id}")

    def create_qr_code_routing(self):
        log.info(f"Creating QR code for routing job {self.model.job_id}")
        solution_path = os.path.join(self.working_dir, ROUTE_FILENAME)

        route_creator = RouteCreator(
            solution_path=solution_path,
            working_dir=self.working_dir,
            job_id=self.model.job_id,
            source_epsg=self.model.epsg,
        )
        # Honor the persisted direction — a GPX regenerated after an object storage
        # round-trip must match what the user chose on Route Download.
        return route_creator.create_gpx(reverse=self.is_route_reversed())

    def is_route_reversed(self) -> bool:
        """Return the persisted route direction (False when never toggled)."""
        options_path = os.path.join(self.working_dir, ROUTE_OPTIONS_FILE)
        if not os.path.exists(options_path):
            return False
        with open(options_path) as f:
            return json.load(f)["reversed"]

    def set_route_reversed(self, reversed_flag: bool):
        """Persist the route direction and regenerate GPX + QR code to match.

        Written through to object storage (save after create_qr_code_routing):
        the QR code's presigned URL points at the object storage copy of
        route.gpx, and the download route pulls from object storage.
        """
        log.info(
            f"Setting route direction for job {self.model.job_id}: "
            f"reversed={reversed_flag}"
        )
        options_path = os.path.join(self.working_dir, ROUTE_OPTIONS_FILE)
        with open(options_path, "w") as f:
            json.dump({"reversed": reversed_flag}, f)

        # Force regeneration — create_gpx skips existing files.
        job_persistence.delete_files(self.model.job_id, [GPX_FILE])
        self.create_qr_code_routing()
        self.save()

    def get_route_polyline(self):
        """Return the route as WGS84 [[lat, lon], ...] positions, or None if unavailable.

        The order follows the persisted route direction, so direction-derived
        map layers (arrowheads, start/end markers) always match the GPX.
        """
        route_path = os.path.join(self.working_dir, ROUTE_FILENAME)
        if not os.path.exists(route_path):
            return None
        with open(route_path) as f:
            solution = json.load(f)
        transformer = Transformer.from_crs(self.model.epsg, 4326, always_xy=True)
        positions = []
        for x, y in solution["Path"]:
            lon, lat = transformer.transform(x, y)
            positions.append([lat, lon])
        if self.is_route_reversed():
            positions.reverse()
        return positions

    def submit(self):
        """Submit the job to background worker."""
        log.info(f"Submitting job {self.model.job_id} to background worker")
        try:
            # Mark as submitted and set status to RUNNING
            self.model.submitted = True
            self.model.status = JOB_STATUS_RUNNING
            self.model.stage = max(self.model.stage, 4)
            # Pull, then upload: the worker pulls from object storage, and an
            # outdated local copy must not replace the stored one. A pull may
            # replace derived street files that ran ahead of storage; the worker
            # recomputes them (StreetSelector.ensure_projected). The save also
            # writes parameters.json via dump_routing_params().
            job_persistence.work_dir(self.model.job_id)
            self.save()

            celery_task_id, failed = background_job_manager.submit_routing_job(self)

            if failed:
                self._fail_to_start()
                return None

            # Store task ID — DB update only, worker already has the files
            self.model.celery_task_id = celery_task_id
            self.update_columns("celery_task_id")

            log.info(f"Job {self.model.job_id} submitted with task_id={celery_task_id}")
            return celery_task_id

        except Exception as e:
            log.error(f"Failed to submit job {self.model.job_id}: {str(e)}")
            raise

    def _fail_to_start(self):
        """Write FAILED and say so in the job log: the job was never enqueued.

        The RUNNING written before the enqueue must not outlive a failed
        enqueue (cosmo-ecosystem ADR 0002); wording as the framework's
        ``Job.submit``.
        """
        message = f"Cannot start job {self.model.job_id}."
        log.error(message)
        job_log.append(self.model.job_id, message, level=logging.ERROR)
        self.model.status = JOB_STATUS_FAILED
        self.update_columns("status")

    def get_status(self) -> str:
        """Return the job's status as its row holds it.

        The job row is the only source of a job's status (cosmo-ecosystem
        ADR 0002): the job run writes RUNNING, COMPLETED or FAILED, and a cancel
        writes FAILED. The Celery state is not consulted.

        Returns:
            str: PENDING, RUNNING, COMPLETED or FAILED
        """
        return self.model.status

    def cancel(self):
        """Cancel the job's run: revoke its task, then record FAILED.

        A terminated worker writes nothing, so the canceller writes FAILED to
        the row and a record to the job log (cosmo-ecosystem ADR 0002). A run
        that wrote COMPLETED just before the kill is overwritten, accepted.
        """
        background_job_manager.revoke_job(self.model.celery_task_id, terminate=True)
        message = f"Job {self.model.job_id}: run cancelled by user."
        log.info(message)
        job_log.append(self.model.job_id, message)
        self.model.status = JOB_STATUS_FAILED
        self.update_columns("status")

    def time_to_live(self) -> int:
        """Return number of days until this job is deleted by cleanup.

        The framework's expiry rule, so the number shown is the one the
        cleanup applies.
        """
        return days_to_live(self.model.start_date, self.model.submitted)

    def get_completed_steps(self) -> list[str]:
        """Return step keys that are done, based on existing model state.

        Stage thresholds (set by each page on layout entry, except user_info
        which bumps on Next click):
          stage >= 1  →  user_info done
          stage >= 2  →  data_upload done (entering street_selection)
          stage >= 3  →  street_selection done (entering routing_params)
          stage >= 4  →  routing_params done (entering route_computation)
          status == COMPLETED  →  route_computation done

        route_download is terminal — never marked done.
        """
        completed = []
        if self.model.stage >= 1:
            completed.append("user_info")
        if self.model.stage >= 2:
            completed.append("data_upload")
        if self.model.stage >= 3:
            completed.append("street_selection")
        if self.model.stage >= 4:
            completed.append("routing_params")
        if self.model.status == JOB_STATUS_COMPLETED:
            completed.append("route_computation")
        return completed

    def get_logs(self) -> str:
        """Return the job log of the job's latest run, from the database.

        Readable from any pod while the run is still going.
        """
        return job_log.read(self.model.job_id)

    def reset(self):
        """Reset job to PENDING state by clearing output files and task state.

        This method:
        - Cancels the run if job is currently RUNNING
        - Deletes output files (solutions, GPX, QR codes) everywhere
        - Clears the job log
        - Preserves input files (uploaded data, parameters, OSM data, plots)
        - Sets status to PENDING
        - Clears celery_task_id and submitted flag
        - Updates the database row
        """
        log.info(f"Resetting job {self.model.job_id}")

        if self.model.status == JOB_STATUS_RUNNING and self.model.celery_task_id:
            log.info(f"Cancelling running task {self.model.celery_task_id}")
            self.cancel()

        # Delete known output files
        job_persistence.delete_files(
            self.model.job_id, [ROUTE_FILENAME, GPX_FILE, QR_CODE_FILE]
        )
        job_log.clear(self.model.job_id)

        # Reset job state
        self.model.status = JOB_STATUS_PENDING
        self.model.celery_task_id = None
        self.model.submitted = False
        self.model.stage = min(self.model.stage, 4)

        self.update_columns("status", "celery_task_id", "submitted", "stage")

        log.info(f"Job {self.model.job_id} reset to PENDING")
