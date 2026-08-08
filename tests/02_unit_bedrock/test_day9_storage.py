"""
Unit tests for Day 9: Storage Service (S3/MinIO wrapper)
Tests StorageService class structure and method signatures.
Note: Actual S3 operations require MinIO running; these tests verify the interface.
"""
from unittest.mock import MagicMock, patch

from src.services.storage import StorageService


class TestStorageService:
    def test_storage_service_initializes_with_defaults(self):
        svc = StorageService()
        assert svc.endpoint == "http://localhost:9000"
        assert svc.bucket == "baziforecaster"

    def test_storage_service_initializes_with_env_vars(self, monkeypatch):
        monkeypatch.setenv("S3_ENDPOINT", "http://custom:9000")
        monkeypatch.setenv("S3_BUCKET", "my-bucket")
        monkeypatch.setenv("S3_ACCESS_KEY", "testkey")
        monkeypatch.setenv("S3_SECRET_KEY", "testsecret")
        svc = StorageService()
        assert svc.endpoint == "http://custom:9000"
        assert svc.bucket == "my-bucket"
        assert svc.access_key == "testkey"

    @patch("src.services.storage.boto3")
    def test_upload_file_calls_boto3(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        svc = StorageService()
        svc.upload_file("key/path.txt", "/tmp/file.txt")
        mock_client.upload_file.assert_called_once_with("/tmp/file.txt", "baziforecaster", "key/path.txt")

    @patch("src.services.storage.boto3")
    def test_upload_string_calls_boto3(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        svc = StorageService()
        svc.upload_string("key/data.json", '{"test": true}')
        mock_client.put_object.assert_called_once()

    @patch("src.services.storage.boto3")
    def test_download_string_returns_content(self, mock_boto3):
        mock_client = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"downloaded content"
        mock_client.get_object.return_value = {"Body": mock_body}
        mock_boto3.client.return_value = mock_client
        svc = StorageService()
        result = svc.download_string("key/file.txt")
        assert result == "downloaded content"

    @patch("src.services.storage.boto3")
    def test_file_exists_returns_true(self, mock_boto3):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 100}
        mock_boto3.client.return_value = mock_client
        svc = StorageService()
        assert svc.file_exists("key/file.txt") is True

    @patch("src.services.storage.boto3")
    def test_file_exists_returns_false_on_404(self, mock_boto3):
        from botocore.exceptions import ClientError
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.ClientError = ClientError
        mock_boto3.client.return_value = mock_client
        svc = StorageService()
        assert svc.file_exists("key/missing.txt") is False
