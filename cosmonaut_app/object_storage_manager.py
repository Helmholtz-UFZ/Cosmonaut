"""This module provides a class to manage object storage using rclone."""

import logging
import subprocess
import sys
import time
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from cosmonaut_app.config import (
    JOB_WORK_DIR_TEMPLATE,
    OBJECT_STORAGE_ACCESS_KEY,
    OBJECT_STORAGE_BUCKET,
    OBJECT_STORAGE_HOST,
    OBJECT_STORAGE_REMOTE_NAME,
    OBJECT_STORAGE_SECRET_KEY,
)
from cosmonaut_app.error_handling import ObjectStorageError

log = logging.getLogger(__name__)


def check_result(params: list, result: subprocess.CompletedProcess) -> None:
    """Check the result of a subprocess command and raise an error if it failed.

    Args:
        result: The result of the subprocess command

    Raises:
        ObjectStorageError: If the command failed
    """
    error_msg = result.stderr.replace(OBJECT_STORAGE_SECRET_KEY, "****")
    error_msg = error_msg.replace(OBJECT_STORAGE_ACCESS_KEY, "****")
    output = result.stdout.replace(OBJECT_STORAGE_SECRET_KEY, "****")
    output = output.replace(OBJECT_STORAGE_ACCESS_KEY, "****")
    call = " ".join(params)
    call = call.replace(OBJECT_STORAGE_SECRET_KEY, "****")
    call = call.replace(OBJECT_STORAGE_ACCESS_KEY, "****")
    if result.returncode != 0:
        if "QuotaExceeded" in error_msg:
            log.error(
                f"Object storage quota exceeded for command: {call}\n{error_msg}\n{output}"  # noqa
            )
        else:
            log.error(f"Command failed: {call}\n{error_msg}\n{output}")
        raise ObjectStorageError


def get_presigned_download_url(object_key: str, expiry: timedelta) -> str:
    """Generate a presigned GET URL for an object in S3-compatible storage.

    Args:
        object_key: Key of the object (e.g. "{job_id}/route.gpx")
        expiry: Duration for which the URL is valid

    Returns:
        str: Presigned URL that can be downloaded without credentials

    Raises:
        ObjectStorageError: If S3 operation fails
    """
    secure = OBJECT_STORAGE_HOST.startswith("https://")
    endpoint = OBJECT_STORAGE_HOST.replace("https://", "").replace("http://", "")
    client = Minio(
        endpoint=endpoint,
        access_key=OBJECT_STORAGE_ACCESS_KEY,
        secret_key=OBJECT_STORAGE_SECRET_KEY,
        secure=secure,
    )
    try:
        url = client.presigned_get_object(
            OBJECT_STORAGE_BUCKET,
            object_key,
            expires=expiry,
        )
        log.debug(f"Generated presigned URL for {object_key}")
        return url
    except S3Error as e:
        log.error(f"S3 error generating presigned URL for {object_key}: {e}")
        raise ObjectStorageError(f"Presigning failed for {object_key}") from e


def run_rclone_with_retry(
    params: list, timeout: float = 600, check_connection: bool = False
) -> subprocess.CompletedProcess:
    """Run rclone command with retry logic for NFS lock file conflicts.

    Args:
        params: The rclone command parameters
        timeout: Timeout in seconds for the subprocess (default: 600 seconds = 10 minutes)
        check_connection: If True, verify MinIO connectivity before running the command

    Raises:
        ObjectStorageError: If all retry attempts fail or connection check fails
    """
    max_retries = 3
    retry_delay = 2

    # Optional connection check before running the main command
    if check_connection:
        check_params = [
            "rclone",
            "lsd",
            f"{OBJECT_STORAGE_REMOTE_NAME}:",
            "--contimeout",
            "3s",
        ]
        try:
            check_result_proc = subprocess.run(
                check_params,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if check_result_proc.returncode != 0:
                log.error(f"MinIO connection check failed: {check_result_proc.stderr}")
                raise ObjectStorageError("MinIO connection check failed")
            log.debug("MinIO connection check passed")
        except subprocess.TimeoutExpired:
            log.error("MinIO connection check timed out - storage may be unreachable")
            raise ObjectStorageError("MinIO connection check timed out") from None

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                params,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            check_result(params, result)
        except subprocess.TimeoutExpired:
            log.error(f"Command timed out after {timeout} seconds: {' '.join(params)}")
            raise ObjectStorageError(
                f"Command timed out after {timeout} seconds"
            ) from None
        except ObjectStorageError:
            if attempt < max_retries - 1:
                log.warning(f"{' '.join(params)} failed. Retry attempt {attempt + 1}")
                time.sleep(retry_delay)
            else:
                raise

    return result


def setup_remote() -> None:
    """Set up rclone remote configuration.

    Args:
        dirname: Name of the directory (used for error handling)
    """
    log.debug("Setting up rclone remote.")
    config_params = [
        "rclone",
        "config",
        "create",
        OBJECT_STORAGE_REMOTE_NAME,
        "s3",
        "provider=Other",
        f"access_key_id={OBJECT_STORAGE_ACCESS_KEY}",
        f"secret_access_key={OBJECT_STORAGE_SECRET_KEY}",
        "region=us-east-1",
        f"endpoint={OBJECT_STORAGE_HOST}",
        "acl=private",
        "force_path_style=true",
    ]

    result = subprocess.run(
        config_params,
        capture_output=True,
        text=True,
        timeout=10,  # 10 seconds for config operations
    )
    check_result(config_params, result)

    log.debug(f"Successfully created remote {OBJECT_STORAGE_REMOTE_NAME}")


def get_files(dirname: str, *, overwrite: bool = False) -> None:
    """Download files from object storage to local work directory.

    By default, only downloads files that don't exist locally
    (``--ignore-existing``).  This prevents stale remote copies from
    overwriting recent local edits (e.g. street selection changes that
    haven't been synced to MinIO yet) while still fetching new files
    created by worker tasks on other pods.

    With ``overwrite=True``, downloads all files using ``--checksum``
    comparison, overwriting local copies.  Use this on worker pods where
    the local directory should mirror the remote exactly.

    Args:
        dirname: Name of the directory to download.
        overwrite: If True, overwrite local files with remote versions.

    Raises:
        ObjectStorageError: If download fails or verification fails.
    """
    log.debug(f"Downloading files from object storage for {dirname}")
    local_path = JOB_WORK_DIR_TEMPLATE.format(job_id=dirname)
    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{dirname}"

    sync_params = [
        "rclone",
        "copy",
        remote_path,
        local_path,
    ]
    if overwrite:
        sync_params.append("--checksum")
    else:
        sync_params.append("--ignore-existing")

    result = run_rclone_with_retry(sync_params, timeout=600, check_connection=True)
    log.debug(f"Rclone download result: {result.stdout}")


def save_files(dirname: str) -> None:
    """Upload files from local work directory to object storage.

    This overwrites remote files with local files using rclone sync.

    Args:
        dirname: Name of the directory to upload

    Raises:
        ObjectStorageError: If upload fails or verification fails
    """
    log.debug(f"Uploading files to object storage for {dirname}")
    local_path = JOB_WORK_DIR_TEMPLATE.format(job_id=dirname)
    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{dirname}"

    # Upload: make remote identical to local
    sync_params = [
        "rclone",
        "sync",
        local_path,
        remote_path,
        "--checksum",
    ]

    run_rclone_with_retry(sync_params, timeout=600, check_connection=True)


def delete_file_from_storage(filepath: str) -> None:
    """Delete a file from the object storage using rclone.

    Args:
        filepath: Path of the file to delete from object storage
    """
    log.debug(f"Deleting file {filepath} from object storage.")

    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{filepath}"

    delete_params = [
        "rclone",
        "delete",
        remote_path,
    ]

    run_rclone_with_retry(delete_params, timeout=10)  # 10 seconds for delete

    log.debug(f"Successfully deleted file {filepath} from object storage")


def delete_directory_from_storage(dirpath: str) -> None:
    """Delete a directory from the object storage using rclone.

    Args:
        dirpath: Path of the directory to delete from object storage
    """
    log.debug(f"Deleting directory {dirpath} from object storage.")

    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{dirpath}"

    purge_params = [
        "rclone",
        "purge",
        remote_path,
    ]

    run_rclone_with_retry(purge_params, timeout=10)  # 10 seconds for purge

    log.debug(f"Successfully deleted directory {dirpath} from object storage")


def create_bucket() -> None:
    """Create the object storage bucket if it doesn't already exist."""
    log.debug(f"Creating bucket {OBJECT_STORAGE_BUCKET}")

    # Check if bucket already exists
    lsd_params = [
        "rclone",
        "lsd",
        f"{OBJECT_STORAGE_REMOTE_NAME}:",
    ]

    result = run_rclone_with_retry(lsd_params, timeout=10)  # 10 seconds for list

    # Parse output to check if bucket exists
    # rclone lsd output format: "-1 2023-01-01 12:00:00        -1 bucket-name"
    bucket_exists = False
    for line in result.stdout.strip().split("\n"):
        if line and OBJECT_STORAGE_BUCKET in line:
            bucket_exists = True
            break

    if bucket_exists:
        return

    # Create bucket if it doesn't exist
    remote_bucket = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}"
    bucket_params = [
        "rclone",
        "mkdir",
        remote_bucket,
    ]

    run_rclone_with_retry(bucket_params, timeout=10)  # 10 seconds for mkdir


def main():
    """Execute setup_remote or create_bucket based on command line argument."""
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) != 2:
        print("Usage: python object_storage_manager.py [setup_remote|create_bucket]")
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "setup_remote":
            setup_remote()
            log.info("Object storage remote setup completed successfully.")
        elif command == "create_bucket":
            create_bucket()
            log.info("Bucket creation completed successfully.")
        else:
            print(f"Unknown command: {command}")
            print(
                "Usage: python object_storage_manager.py [setup_remote|create_bucket]"
            )
            sys.exit(1)
    except ObjectStorageError as e:
        log.error(f"Failed to execute {command}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
