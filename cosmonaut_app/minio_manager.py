import io
import logging
import os
import json

from minio import Minio
from minio.error import S3Error
from urllib.parse import urlparse

from cosmonaut_app.config import (
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_HOST,
    MINIO_PORT,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# TODO: Replace with rclone for performance


class MiniIOManager:
    """
    A class to manage file uploads and deletions to a MinIO bucket.

    Attributes:
        bucket_name (str): The name of the MinIO bucket.
        minio_client (Minio): The MinIO client object.

    Methods:
        upload_file(file_path, object_key): Uploads a file to the MinIO bucket.
        delete_file(object_key): Deletes a file from the MinIO bucket.
        make_file_public(object_key): Makes a file in the MinIO bucket public.
        get_file_url(object_key): Gets the URL of a file in the MinIO bucket.
    """

    def __init__(self, bucket_name):
        logging.info(f"Initializing MinIO manager for bucket {bucket_name}")
        self.bucket_name = bucket_name

        # Parse and sanitize MINIO_HOST to remove any scheme
        parsed_host = urlparse(MINIO_HOST)
        host = parsed_host.netloc if parsed_host.netloc else parsed_host.path
        endpoint = f"{host}:{MINIO_PORT}" if MINIO_PORT else host
        logging.info(f"Constructed MinIO endpoint: {endpoint}")

        # Initialize the Minio client
        try:
            self.minio_client = Minio(
                endpoint=endpoint,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                # secure=(MINIO_PORT == "443"),
            )
            logging.info("MinIO client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize MinIO client: {str(e)}")
            raise

    def upload_file(self, file_path, object_key):
        logging.info(f"Uploading file {file_path} as {object_key}")
        _, file_extension = os.path.splitext(file_path)
        allowed_extensions = [".tif", ".geojson", ".json", ".csv", ".gpx"]
        if file_extension not in allowed_extensions:
            logging.error(
                f"Failed to upload file {file_path}: Only {', '.join(allowed_extensions)} files are allowed."
            )
            return False

        try:
            if not os.path.exists(file_path):
                logging.error(f"File does not exist: {file_path}")
                return False

            self.minio_client.fput_object(self.bucket_name, object_key, file_path)
            logging.info(f"File {file_path} uploaded successfully as {object_key}")
            return True
        except Exception as e:
            logging.error(f"Failed to upload file {file_path}: {str(e)}", exc_info=True)
            return False

    def download_file(self, object_key, file_path):
        """
        Downloads a file from the MinIO bucket.

        Args:
            object_key (str): Key of the file to be downloaded from the MinIO bucket.
            file_path (str): The path to save the downloaded file.
        """
        try:
            self.minio_client.fget_object(self.bucket_name, object_key, file_path)
            logging.info(f"File {object_key} downloaded successfully as {file_path}")
        except Exception as e:
            logging.error(f"Failed to download file {object_key}: {str(e)}")

    def delete_file(self, object_key):
        """
        Deletes a file from the MinIO bucket.

        Args:
            object_key (str): The key of the file to be deleted from the MinIO bucket.
        """
        try:
            self.minio_client.remove_object(self.bucket_name, object_key)
            logging.info(f"File {object_key} deleted successfully")
        except Exception as e:
            logging.error(f"Failed to delete file {object_key}: {str(e)}")

    def make_file_public(self, object_key):
        """
        Makes a file in the MinIO bucket public.

        Args:
            object_key (str): The key of the file to be made public.
        """
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
            policy_json = json.dumps(policy)
            self.minio_client.set_bucket_policy(self.bucket_name, policy_json)
            logging.info(f"File {object_key} made public successfully")
        except S3Error as e:
            logging.error(f"Failed to make file {object_key} public: {str(e)}")

    def get_file_url(self, object_key):
        """
        Gets the URL of a file in the MinIO bucket.

        Args:
            object_key (str): The key of the file to get the URL for.

        Returns:
            str: The URL of the file.
        """
        try:
            url = self.minio_client.presigned_get_object(self.bucket_name, object_key)
            logging.info(f"URL for file {object_key} retrieved successfully")
            return url
        except Exception as e:
            logging.error(f"Failed to get URL for file {object_key}: {str(e)}")
            return None

    # return filenames asked for in the bucket
    def get_files(self):
        """
        Lists all files in the MinIO bucket.
        """
        try:
            objects = self.minio_client.list_objects(self.bucket_name)
            return [obj.object_name for obj in objects]
        except Exception as e:
            logging.warning(
                f"Failed to list files in bucket {self.bucket_name}: {str(e)}"
            )

    def upload_placeholder(self, object_key):
        try:
            logging.info(f"Creating placeholder for object key: {object_key}")
            empty_file = io.BytesIO(b"")
            self.minio_client.put_object(
                self.bucket_name, object_key, data=empty_file, length=0
            )
            logging.info(f"Placeholder for {object_key} created successfully")
        except Exception as e:
            logging.error(
                f"Failed to create placeholder for {object_key}: {str(e)}",
                exc_info=True,
            )

    @staticmethod
    def download_directory(minio_path, local_path):
        """
        Downloads all objects from a MinIO bucket
        with the specified prefix to a local directory.

        Args:
            minio_path (str): Prefix of the objects to be downloaded.
            local_path (str): Local directory to save the objects.
        """
        logging.info(f"Downloading directory {minio_path} to {local_path}")
        try:
            # Ensure the local path exists
            if not os.path.exists(local_path):
                os.makedirs(local_path)

            # List all objects in the bucket with the specified prefix
            minio_client = Minio(
                f"{MINIO_HOST}:{MINIO_PORT}",
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=(MINIO_PORT == 443),
            )
            objects = minio_client.list_objects(
                "cosmic-routing", prefix=minio_path, recursive=True
            )

            for obj in objects:
                # Construct the local file path
                local_file_path = os.path.join(
                    local_path, os.path.relpath(obj.object_name, minio_path)
                )
                local_file_dir = os.path.dirname(local_file_path)

                # Ensure the local directory exists
                if not os.path.exists(local_file_dir):
                    os.makedirs(local_file_dir)

                # Check if the file already exists locally
                if not os.path.exists(local_file_path):
                    # Download the object
                    minio_client.fget_object(
                        "cosmic-routing", obj.object_name, local_file_path
                    )
                    logging.info(f"Downloaded {obj.object_name} to {local_file_path}")
                else:
                    logging.info(
                        f"Skipped {obj.object_name} as it already exists locally"
                    )

        except Exception as e:
            logging.error(f"Failed to download directory {minio_path}: {str(e)}")


if __name__ == "__main__":
    bucket_name = "cosmic-routing"
    manager = MiniIOManager(bucket_name)
    try:
        manager.minio_client.bucket_exists(bucket_name)
        manager.upload_file("test_data/no_csv.txt", "no_csv.txt")
        manager.download_file("no_csv.txt", "test_data/no_csv_downloaded.txt")
        manager.delete_file("no_csv.txt")
    except Exception as e:
        logging.error(f"Bucket {bucket_name} does not exist: {str(e)}")
