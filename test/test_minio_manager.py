"""Test the MinIO manager class."""

import pytest
from cosmonaut_app.minio_manager import MiniIOManager


@pytest.fixture
def minio_manager():
    """Create a MinIO manager instance."""
    return MiniIOManager("cosmic-routing")


@pytest.fixture
def test_files(tmp_path):
    """Create temporary test files with different extensions."""
    files = {}

    # Create allowed file types
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("col1,col2\n1,2\n3,4\n")
    files["csv"] = str(csv_file)

    json_file = tmp_path / "test.json"
    json_file.write_text('{"key": "value"}')
    files["json"] = str(json_file)

    gpx_file = tmp_path / "test.gpx"
    gpx_file.write_text('<?xml version="1.0"?><gpx></gpx>')
    files["gpx"] = str(gpx_file)

    geojson_file = tmp_path / "test.geojson"
    geojson_file.write_text('{"type": "FeatureCollection", "features": []}')
    files["geojson"] = str(geojson_file)

    # Create disallowed file type
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("This is a text file")
    files["txt"] = str(txt_file)

    return files


def test_bucket_exists(minio_manager):
    """Test that the cosmic-routing bucket exists."""
    assert minio_manager.minio_client.bucket_exists("cosmic-routing")


def test_upload_allowed_files(minio_manager, test_files):
    """Test uploading allowed file types succeeds."""
    allowed_types = ["csv", "json", "gpx", "geojson"]

    for file_type in allowed_types:
        file_path = test_files[file_type]
        object_key = f"test_{file_type}.{file_type}"

        # Upload should succeed
        result = minio_manager.upload_file(file_path, object_key)
        assert result is True, f"Failed to upload {file_type} file"

        # Cleanup
        minio_manager.delete_file(object_key)


def test_upload_rejected_files(minio_manager, test_files):
    """Test that disallowed file types are rejected."""
    file_path = test_files["txt"]
    object_key = "test_rejected.txt"

    # Upload should fail (return False)
    result = minio_manager.upload_file(file_path, object_key)
    assert result is False, "Upload of .txt file should be rejected"


def test_upload_nonexistent_file(minio_manager):
    """Test uploading a file that doesn't exist."""
    result = minio_manager.upload_file("/nonexistent/file.csv", "test.csv")
    assert result is False, "Upload of nonexistent file should fail"


def test_download_file(minio_manager, test_files, tmp_path):
    """Test downloading a file from MinIO."""
    # First upload a file
    upload_path = test_files["csv"]
    object_key = "test_download.csv"

    upload_result = minio_manager.upload_file(upload_path, object_key)
    assert upload_result is True, "Upload failed"

    # Download the file
    download_path = tmp_path / "downloaded.csv"
    minio_manager.download_file(object_key, str(download_path))

    # Verify file was downloaded and content matches
    assert download_path.exists(), "Downloaded file doesn't exist"
    assert download_path.read_text() == "col1,col2\n1,2\n3,4\n"

    # Cleanup
    minio_manager.delete_file(object_key)


def test_list_files(minio_manager, test_files):
    """Test listing files in the bucket."""
    # Upload a test file
    object_key = "test_list.json"
    minio_manager.upload_file(test_files["json"], object_key)

    # List files
    files = minio_manager.get_files()
    assert files is not None, "get_files() returned None"
    assert object_key in files, f"{object_key} not found in bucket"

    # Cleanup
    minio_manager.delete_file(object_key)


def test_delete_file(minio_manager, test_files):
    """Test deleting a file from MinIO."""
    # Upload a file
    object_key = "test_delete.json"
    minio_manager.upload_file(test_files["json"], object_key)

    # Verify it exists
    files = minio_manager.get_files()
    assert object_key in files

    # Delete it
    minio_manager.delete_file(object_key)

    # Verify it's gone
    files = minio_manager.get_files()
    assert object_key not in files


def test_upload_download_delete_cycle(minio_manager, test_files, tmp_path):
    """Test the complete upload/download/delete cycle."""
    # Upload
    upload_path = test_files["geojson"]
    object_key = "test_cycle.geojson"

    upload_result = minio_manager.upload_file(upload_path, object_key)
    assert upload_result is True, "Upload failed"

    # Verify it exists
    files = minio_manager.get_files()
    assert object_key in files, "Uploaded file not found in bucket"

    # Download
    download_path = tmp_path / "cycle_downloaded.geojson"
    minio_manager.download_file(object_key, str(download_path))
    assert download_path.exists(), "Downloaded file doesn't exist"

    # Verify content
    original_content = open(upload_path).read()
    downloaded_content = download_path.read_text()
    assert original_content == downloaded_content, "Content mismatch"

    # Delete
    minio_manager.delete_file(object_key)

    # Verify it's gone
    files = minio_manager.get_files()
    assert object_key not in files, "File still exists after deletion"


def test_get_file_url(minio_manager, test_files):
    """Test getting a presigned URL for a file."""
    # Upload a file
    object_key = "test_url.csv"
    minio_manager.upload_file(test_files["csv"], object_key)

    # Get URL
    url = minio_manager.get_file_url(object_key)
    assert url is not None, "Failed to get file URL"
    assert (
        "cosmic-routing" in url or object_key in url
    ), "URL doesn't contain expected components"

    # Cleanup
    minio_manager.delete_file(object_key)
