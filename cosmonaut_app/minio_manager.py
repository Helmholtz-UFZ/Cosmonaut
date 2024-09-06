from minio import Minio
import os
import datetime
import io

# TODO: Temporary loading of environment variables, later should be automatically loaded for Docker
from dotenv import load_dotenv

load_dotenv(".env_test_priv")

from cosmonaut_app.config import MINIO_ACCESS_KEY, MINIO_SECRET_KEY
import logging


class MiniIOManager:
    """
    A class to manage file uploads and deletions to a MinIO bucket.

    Attributes:
        bucket_name (str): The name of the MinIO bucket.
        minio_client (Minio): The MinIO client object.

    Methods:
        upload_file(file_path, object_key): Uploads a file to the MinIO bucket.
        delete_file(object_key): Deletes a file from the MinIO bucket.
    """

    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.minio_client = Minio(
            "minio.ufz.de",
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=True,
        )

    def upload_file(self, file_path, object_key):
        """
        Uploads a file to the MinIO bucket.

        Args:
            file_path (str): The path of the file to be uploaded.
            object_key (str): The key to assign to the uploaded file in the MinIO bucket.
        """
        _, file_extension = os.path.splitext(file_path)
        allowed_extensions = [".tif", ".geojson", ".json", ".csv"]
        if file_extension not in allowed_extensions:
            logging.error(
                f"Failed to upload file {file_path}: Only {', '.join(allowed_extensions)} files are allowed."
            )
            return

        try:
            self.minio_client.fput_object(self.bucket_name, object_key, file_path)
            logging.info(f"File {file_path} uploaded successfully as {object_key}")
        except Exception as e:
            logging.error(f"Failed to upload file {file_path}: {str(e)}")

    def download_file(self, object_key, file_path):
        """
        Downloads a file from the MinIO bucket.

        Args:
            object_key (str): The key of the file to be downloaded from the MinIO bucket.
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
        """
        Creates a placeholder object in the MinIO bucket to simulate a directory.

        Args:
            object_key (str): The key for the placeholder object, typically ending with a '/' to simulate a directory path.
        """
        try:
            # Create an empty file-like object
            empty_file = io.BytesIO(b"")
            self.minio_client.put_object(
                self.bucket_name, object_key, data=empty_file, length=0
            )
            logging.info(f"Placeholder for {object_key} created successfully")
        except Exception as e:
            logging.error(f"Failed to create placeholder for {object_key}: {str(e)}")

    @staticmethod
    def download_directory(minio_path, local_path):
        """
        Downloads all objects from a MinIO bucket with the specified prefix to a local directory.

        Args:
            minio_path (str): The prefix of the objects to be downloaded from the MinIO bucket.
            local_path (str): The local directory to save the downloaded objects.
        """
        try:
            # Ensure the local path exists
            if not os.path.exists(local_path):
                os.makedirs(local_path)

            # List all objects in the bucket with the specified prefix
            minio_client = Minio(
                "minio.ufz.de",
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=True,
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

                # Download the object
                minio_client.fget_object(
                    "cosmic-routing", obj.object_name, local_file_path
                )
                logging.info(f"Downloaded {obj.object_name} to {local_file_path}")

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
