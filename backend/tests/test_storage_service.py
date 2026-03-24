"""Tests for storage service error handling around MinIO/S3 availability."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import EndpointConnectionError

from app.services.storage_service import StorageService, StorageUnavailableError


@patch("app.services.storage_service.boto3.client")
@patch("app.services.storage_service.StorageService._ensure_bucket_exists")
def test_upload_file_returns_false_on_endpoint_connection_error(
    mock_ensure_bucket_exists,
    mock_boto_client,
):
    mock_client = MagicMock()
    mock_boto_client.return_value = mock_client
    mock_ensure_bucket_exists.return_value = None

    service = StorageService()
    mock_client.put_object.side_effect = EndpointConnectionError(
        endpoint_url="http://localhost:9000"
    )

    assert service.upload_file(b"hello", "users/1/documents/test.txt", "text/plain") is False


@patch("app.services.storage_service.boto3.client")
@patch("app.services.storage_service.StorageService._ensure_bucket_exists")
def test_storage_service_init_raises_storage_unavailable_when_bucket_check_fails(
    mock_ensure_bucket_exists,
    mock_boto_client,
):
    mock_boto_client.return_value = MagicMock()
    mock_ensure_bucket_exists.side_effect = EndpointConnectionError(
        endpoint_url="http://localhost:9000"
    )

    with pytest.raises(StorageUnavailableError):
        StorageService()
