"""This module provides a class to manage object storage using rclone."""

import logging
import os
import subprocess
import sys
import time

from cosmopolitan_app.config import (
    JOB_WORK_DIR_TEMPLATE,
    OBJECT_STORAGE_ACCESS_KEY,
    OBJECT_STORAGE_BUCKET,
    OBJECT_STORAGE_HOST,
    OBJECT_STORAGE_REMOTE_NAME,
    OBJECT_STORAGE_SECRET_KEY,
)


class ObjectStorageError(Exception):
    """Exception raised for errors in the ObjectStorageManager class."""

    def __init__(self, message="An error occurred while managing object storage."):
        """Initialize the ObjectStorageError class."""
        super().__init__(message)


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
            logging.error(
                f"Object storage quota exceeded for command: {call}\n{error_msg}\n{output}",  # noqa
                extra={"tag": "object_storage"},
            )
        else:
            logging.error(
                f"Command failed: {call}\n{error_msg}\n{output}",
                extra={"tag": "object_storage"},
            )
        raise ObjectStorageError


def run_rclone_with_retry(params: list) -> subprocess.CompletedProcess:
    """Run rclone command with retry logic for NFS lock file conflicts.

    Args:
        params: The rclone command parameters

    Raises:
        ObjectStorageError: If all retry attempts fail
    """
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                params,
                capture_output=True,
                text=True,
            )
            check_result(params, result)
        except ObjectStorageError:
            if attempt < max_retries - 1:
                logging.warning(
                    f"{' '.join(params)} failed. Retry attempt {attempt + 1}",
                    extra={"tag": "object_storage"},
                )
                time.sleep(retry_delay)
            else:
                raise

    return result


def setup_remote() -> None:
    """Set up rclone remote configuration.

    Args:
        dirname: Name of the directory (used for error handling)
    """
    logging.debug("Setting up rclone remote.", extra={"tag": "object_storage"})
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
    )
    check_result(config_params, result)

    logging.debug(
        f"Successfully created remote {OBJECT_STORAGE_REMOTE_NAME}",
        extra={"tag": "object_storage"},
    )


def get_local_files(local_path: str) -> set:
    """Get set of all files in a local directory (relative paths).

    Args:
        local_path: Path to local directory

    Returns:
        Set of relative file paths
    """
    files = set()
    if not os.path.exists(local_path):
        return files

    for root, _, filenames in os.walk(local_path):
        for filename in filenames:
            # Get full path and make it relative to local_path
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, local_path)
            files.add(rel_path)

    return files


def get_remote_files(remote_path: str) -> set:
    """Get set of all files in a remote directory using rclone ls.

    Args:
        remote_path: Remote path in format "remote:bucket/dirname"

    Returns:
        Set of relative file paths
    """
    ls_params = ["rclone", "ls", remote_path]

    result = run_rclone_with_retry(ls_params)

    # rclone ls returns lines like: "  123456 path/to/file.txt"
    # Extract just the filenames
    files = set()
    for line in result.stdout.strip().split("\n"):
        if line:
            # Split on whitespace and take everything after the size
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                files.add(parts[1])

    return files


def get_files(dirname: str) -> None:
    """Download files from object storage to local work directory.

    This copies files from remote to local without deleting local files using rclone
    copy.

    Args:
        dirname: Name of the directory to download

    Raises:
        ObjectStorageError: If download fails or verification fails
    """
    logging.debug(
        f"Downloading files from object storage for {dirname}",
        extra={"tag": "object_storage"},
    )
    local_path = JOB_WORK_DIR_TEMPLATE.format(job_id=dirname)
    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{dirname}"

    local_files_before = get_local_files(local_path)
    # Download: copy files from remote to local without deleting local files
    sync_params = [
        "rclone",
        "copy",
        remote_path,
        local_path,
        "--checksum",
    ]

    result = run_rclone_with_retry(sync_params)
    logging.debug(
        f"Rclone sync result: {result.stdout}", extra={"tag": "object_storage"}
    )

    # Verify download - check that all remote files are now in local
    # (local may have additional files, which is acceptable with copy)
    local_files_after = get_local_files(local_path)
    remote_files = get_remote_files(remote_path)

    logging.debug(
        f"Downloaded {len(local_files_after - local_files_before)} new files to local",
        extra={"tag": "object_storage"},
    )

    # Check that all remote files are present locally
    if not remote_files.issubset(local_files_after):
        missing_files = remote_files - local_files_after
        error_msg = (
            f"Download verification failed for {dirname}!\n"
            f"Missing files from remote: {sorted(missing_files)}\n"
            f"Files from local: {sorted(local_files_after)}\n"
            f"Files from remote: {sorted(remote_files)}"
        )
        logging.error(error_msg, extra={"tag": "object_storage"})
        raise ObjectStorageError(error_msg)


def save_files(dirname: str) -> None:
    """Upload files from local work directory to object storage.

    This overwrites remote files with local files using rclone sync.

    Args:
        dirname: Name of the directory to upload

    Raises:
        ObjectStorageError: If upload fails or verification fails
    """
    logging.debug(
        f"Uploading files to object storage for {dirname}",
        extra={"tag": "object_storage"},
    )
    local_path = JOB_WORK_DIR_TEMPLATE.format(job_id=dirname)
    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{dirname}"
    remote_files_before = get_remote_files(remote_path)

    # List local files before upload
    local_files_before = get_local_files(local_path)
    logging.debug(
        f"Uploading {len(local_files_before)} files: {sorted(local_files_before)}",
        extra={"tag": "object_storage"},
    )

    # Upload: make remote identical to local
    sync_params = [
        "rclone",
        "sync",
        local_path,
        remote_path,
        "--checksum",
    ]

    run_rclone_with_retry(sync_params)

    # Verify upload
    local_files = get_local_files(local_path)
    remote_files_after = get_remote_files(remote_path)

    logging.debug(
        f"Uploaded {len(remote_files_after - remote_files_before)} new files to remote",
        extra={"tag": "object_storage"},
    )

    if local_files != remote_files_after:
        error_msg = (
            f"Upload verification failed for {dirname}!\n"
            f"Files from local: {sorted(local_files)}\n"
            f"Files from remote: {sorted(remote_files_after)}"
        )
        logging.error(error_msg, extra={"tag": "object_storage"})
        raise ObjectStorageError(error_msg)


def delete_file_from_storage(filepath: str) -> None:
    """Delete a file from the object storage using rclone.

    Args:
        filepath: Path of the file to delete from object storage
    """
    logging.debug(
        f"Deleting file {filepath} from object storage.",
        extra={"tag": "object_storage"},
    )

    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{filepath}"

    delete_params = [
        "rclone",
        "delete",
        remote_path,
    ]

    run_rclone_with_retry(delete_params)

    logging.debug(
        f"Successfully deleted file {filepath} from object storage",
        extra={"tag": "object_storage"},
    )


def delete_directory_from_storage(dirpath: str) -> None:
    """Delete a directory from the object storage using rclone.

    Args:
        dirpath: Path of the directory to delete from object storage
    """
    logging.debug(
        f"Deleting directory {dirpath} from object storage.",
        extra={"tag": "object_storage"},
    )

    remote_path = f"{OBJECT_STORAGE_REMOTE_NAME}:{OBJECT_STORAGE_BUCKET}/{dirpath}"

    purge_params = [
        "rclone",
        "purge",
        remote_path,
    ]

    run_rclone_with_retry(purge_params)

    logging.debug(
        f"Successfully deleted directory {dirpath} from object storage",
        extra={"tag": "object_storage"},
    )


def create_bucket() -> None:
    """Create the object storage bucket if it doesn't already exist."""
    logging.debug(
        f"Creating bucket {OBJECT_STORAGE_BUCKET}", extra={"tag": "object_storage"}
    )

    # Check if bucket already exists
    lsd_params = [
        "rclone",
        "lsd",
        f"{OBJECT_STORAGE_REMOTE_NAME}:",
    ]

    result = run_rclone_with_retry(lsd_params)

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

    run_rclone_with_retry(bucket_params)


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
            logging.info(
                "Object storage remote setup completed successfully.",
                extra={"tag": "object_storage"},
            )
        elif command == "create_bucket":
            create_bucket()
            logging.info(
                "Bucket creation completed successfully.",
                extra={"tag": "object_storage"},
            )
        else:
            print(f"Unknown command: {command}")
            print(
                "Usage: python object_storage_manager.py [setup_remote|create_bucket]"
            )
            sys.exit(1)
    except ObjectStorageError as e:
        logging.error(
            f"Failed to execute {command}: {e}", extra={"tag": "object_storage"}
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
