import io
import json
import logging
import os
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from cosmonaut_app.config import (
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_HOST,
    MINIO_PORT,
)


def _to_bool(val, default=None):
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _resolve_minio_endpoint_and_secure(host: str, port) -> tuple[str, bool]:
    """
    Decide endpoint and TLS (secure) based on:
    - scheme in MINIO_HOST (http/https)
    - env MINIO_SECURE
    - port heuristic (443 -> TLS; 9000 -> plain)
    """
    parsed = urlparse(str(host))
    scheme = parsed.scheme
    hostname = parsed.netloc if parsed.netloc else parsed.path

    # Build endpoint host:port
    port_str = str(port) if port not in (None, "") else ""
    endpoint = f"{hostname}:{port_str}" if port_str else hostname

    # 1) Scheme wins if provided
    if scheme == "https":
        return endpoint, True
    if scheme == "http":
        return endpoint, False

    # 2) Explicit env override
    env_secure = _to_bool(os.getenv("MINIO_SECURE"), default=None)
    if env_secure is not None:
        return endpoint, env_secure

    # 3) Port heuristic
    if str(port_str) == "443":
        return endpoint, True
    # Default MinIO in docker on 9000 is HTTP
    if str(port_str) == "9000":
        return endpoint, False

    # 4) Safe default: no TLS unless told otherwise
    return endpoint, False


class MiniIOManager:
    """
    Manage uploads/downloads to a MinIO bucket.
    """

    def __init__(self, bucket_name: str):
        logging.info("Initializing MinIO manager for bucket %s", bucket_name)
        self.bucket_name = bucket_name

        endpoint, secure = _resolve_minio_endpoint_and_secure(MINIO_HOST, MINIO_PORT)
        logging.info("Constructed MinIO endpoint: %s (secure=%s)", endpoint, secure)

        try:
            self.minio_client = Minio(
                endpoint=endpoint,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=secure,
            )
            logging.info("MinIO client initialized successfully")

            # Ensure bucket exists (also checks connectivity once)
            if not self.minio_client.bucket_exists(self.bucket_name):
                self.minio_client.make_bucket(self.bucket_name)
        except Exception as e:
            logging.error("Failed to initialize MinIO client: %s", e, exc_info=True)
            raise

    def upload_file(self, file_path: str, object_key: str) -> bool:
        logging.info("Uploading file %s as %s", file_path, object_key)
        _, ext = os.path.splitext(file_path)
        allowed = {".tif", ".geojson", ".json", ".csv", ".gpx"}
        if ext not in allowed:
            logging.error(
                "Failed to upload %s: only %s are allowed.",
                file_path,
                ", ".join(sorted(allowed)),
            )
            return False
        if not os.path.exists(file_path):
            logging.error("File does not exist: %s", file_path)
            return False
        try:
            self.minio_client.fput_object(self.bucket_name, object_key, file_path)
            logging.info("File %s uploaded successfully as %s", file_path, object_key)
            return True
        except Exception as e:
            logging.error("Failed to upload file %s: %s", file_path, e, exc_info=True)
            return False

    def download_file(self, object_key: str, file_path: str) -> None:
        try:
            self.minio_client.fget_object(self.bucket_name, object_key, file_path)
            logging.info("File %s downloaded successfully as %s", object_key, file_path)
        except Exception as e:
            logging.error("Failed to download file %s: %s", object_key, e)

    def delete_file(self, object_key: str) -> None:
        try:
            self.minio_client.remove_object(self.bucket_name, object_key)
            logging.info("File %s deleted successfully", object_key)
        except Exception as e:
            logging.error("Failed to delete file %s: %s", object_key, e)

    def make_file_public(self, object_key: str) -> None:
        try:
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}/{object_key}"],
                    }
                ],
            }
            self.minio_client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            logging.info("File %s made public successfully", object_key)
        except S3Error as e:
            logging.error("Failed to make file %s public: %s", object_key, e)

    def get_file_url(self, object_key: str) -> str | None:
        try:
            url = self.minio_client.presigned_get_object(self.bucket_name, object_key)
            logging.info("URL for file %s retrieved", object_key)
            return url
        except Exception as e:
            logging.error("Failed to get URL for file %s: %s", object_key, e)
            return None

    def get_files(self) -> list[str] | None:
        try:
            return [
                obj.object_name
                for obj in self.minio_client.list_objects(self.bucket_name)
            ]
        except Exception as e:
            logging.warning(
                "Failed to list files in bucket %s: %s", self.bucket_name, e
            )
            return None

    def upload_placeholder(self, object_key: str) -> None:
        try:
            logging.info("Creating placeholder for object key: %s", object_key)
            empty = io.BytesIO(b"")
            self.minio_client.put_object(
                self.bucket_name, object_key, data=empty, length=0
            )
            logging.info("Placeholder for %s created", object_key)
        except Exception as e:
            logging.error(
                "Failed to create placeholder for %s: %s", object_key, e, exc_info=True
            )

    @staticmethod
    def download_directory(minio_path: str, local_path: str) -> None:
        logging.info("Downloading directory %s to %s", minio_path, local_path)
        try:
            os.makedirs(local_path, exist_ok=True)

            endpoint, secure = _resolve_minio_endpoint_and_secure(
                MINIO_HOST, MINIO_PORT
            )
            m = Minio(
                endpoint,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=secure,
            )

            objects = m.list_objects(
                "cosmic-routing", prefix=minio_path, recursive=True
            )
            for obj in objects:
                local_file = os.path.join(
                    local_path, os.path.relpath(obj.object_name, minio_path)
                )
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                if not os.path.exists(local_file):
                    m.fget_object("cosmic-routing", obj.object_name, local_file)
                    logging.info("Downloaded %s to %s", obj.object_name, local_file)
        except Exception as e:
            logging.error("Failed to download directory %s: %s", minio_path, e)
