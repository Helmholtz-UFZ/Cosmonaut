from minio import Minio
import os
import datetime

# TODO: Temporary loading of environment variables, later should be automatically loaded for Docker
from dotenv import load_dotenv

load_dotenv(".env_test_priv")

from cosmonaut_app.config import MINIO_ACCESS_KEY, MINIO_SECRET_KEY


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
        if file_extension != ".tif":
            print(f"Failed to upload file {file_path}: Only .tif files are allowed.")
            return

        try:
            self.minio_client.fput_object(self.bucket_name, object_key, file_path)
            print(f"File {file_path} uploaded successfully as {object_key}")
        except Exception as e:
            print(f"Failed to upload file {file_path}: {str(e)}")

    def delete_file(self, object_key):
        """
        Deletes a file from the MinIO bucket.

        Args:
            object_key (str): The key of the file to be deleted from the MinIO bucket.
        """
        try:
            self.minio_client.remove_object(self.bucket_name, object_key)
            print(f"File {object_key} deleted successfully")
        except Exception as e:
            print(f"Failed to delete file {object_key}: {str(e)}")


if __name__ == "__main__":
    bucket_name = "cosmic-routing"
    manager = MiniIOManager(bucket_name)
    try:
        manager.minio_client.bucket_exists(bucket_name)
        manager.upload_file("test_data/no_csv.txt", "no_csv.txt")
        manager.delete_file("no_csv.txt")
    except Exception as e:
        print(f"Bucket {bucket_name} does not exist: {str(e)}")
