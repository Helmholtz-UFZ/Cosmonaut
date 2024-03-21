from minio import Minio

class MiniIOManager:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.minio_client = Minio('minio.ufz.de',
                                  access_key='MrB4LovDjMtWdegRIyOk',
                                  secret_key='a0D4Yvvd1VAATEYnGzBgqOqYIfgXmIbt5ZPloxC8',
                                  secure=True)

    def upload_file(self, file_path, object_key):
        try:
            self.minio_client.fput_object(self.bucket_name, object_key, file_path)
            print(f"File {file_path} uploaded successfully as {object_key}")
        except Exception as e:
            print(f"Failed to upload file {file_path}: {str(e)}")

    def delete_file(self, object_key):
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
        manager.upload_file("path/to/local/file.txt", "object_key/file.txt")
        manager.delete_file("object_key/file.txt")
    except Exception as e:
        print(f"Bucket {bucket_name} does not exist: {str(e)}")
        