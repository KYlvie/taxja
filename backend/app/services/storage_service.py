"""Storage service for document files (MinIO/S3)"""
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

_STORAGE_CONNECT_TIMEOUT_SECONDS = 3
_STORAGE_READ_TIMEOUT_SECONDS = 15
_STORAGE_MAX_RETRIES = 1


class StorageUnavailableError(RuntimeError):
    """Raised when the configured object storage endpoint is not reachable."""


class StorageService:
    """Service for managing document storage in MinIO/S3"""

    def __init__(self):
        """Initialize storage client with AES-256 encryption"""
        endpoint = settings.MINIO_ENDPOINT
        # Ensure endpoint has http:// prefix for boto3
        if endpoint and not endpoint.startswith(("http://", "https://")):
            secure = getattr(settings, 'MINIO_SECURE', False)
            prefix = "https://" if secure else "http://"
            endpoint = prefix + endpoint

        self.endpoint_url = endpoint
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.bucket_name = settings.MINIO_BUCKET
        self.region = getattr(settings, 'MINIO_REGION', 'us-east-1')

        # Initialize S3 client (compatible with MinIO)
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(
                connect_timeout=_STORAGE_CONNECT_TIMEOUT_SECONDS,
                read_timeout=_STORAGE_READ_TIMEOUT_SECONDS,
                retries={
                    "max_attempts": _STORAGE_MAX_RETRIES,
                    "mode": "standard",
                },
            ),
        )

        # Ensure bucket exists with encryption
        try:
            self._ensure_bucket_exists()
        except (BotoCoreError, OSError) as exc:
            logger.error(
                "Object storage unavailable during initialization for endpoint %s: %s",
                self.endpoint_url,
                exc,
            )
            raise StorageUnavailableError(
                f"Could not connect to storage endpoint {self.endpoint_url}"
            ) from exc

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist and enable AES-256 encryption"""
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket exists: {self.bucket_name}")
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
                
                # Enable default AES-256 encryption for the bucket
                try:
                    self.client.put_bucket_encryption(
                        Bucket=self.bucket_name,
                        ServerSideEncryptionConfiguration={
                            'Rules': [
                                {
                                    'ApplyServerSideEncryptionByDefault': {
                                        'SSEAlgorithm': 'AES256'
                                    }
                                }
                            ]
                        }
                    )
                    logger.info(f"Enabled AES-256 encryption for bucket: {self.bucket_name}")
                except ClientError as e:
                    logger.warning(f"Could not enable encryption (MinIO may not support this API): {e}")
            except ClientError as e:
                logger.error(f"Failed to create bucket: {e}")

    def upload_file(self, file_bytes: bytes, file_path: str, content_type: Optional[str] = None) -> bool:
        """
        Upload file to storage with server-side encryption

        Args:
            file_bytes: File content as bytes
            file_path: Path/key for the file in storage
            content_type: MIME type of the file (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
                
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_bytes,
                **extra_args
            )
            logger.info(f"Uploaded file with AES-256 encryption: {file_path}")
            return True
        except (ClientError, BotoCoreError, OSError) as e:
            logger.error(f"Failed to upload file {file_path}: {e}")
            return False

    def download_file(self, file_path: str) -> Optional[bytes]:
        """
        Download file from storage

        Args:
            file_path: Path/key of the file in storage

        Returns:
            File content as bytes, or None if not found
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=file_path)
            file_bytes = response["Body"].read()
            logger.info(f"Downloaded file: {file_path}")
            return file_bytes
        except (ClientError, BotoCoreError, OSError) as e:
            logger.error(f"Failed to download file {file_path}: {e}")
            return None

    def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage

        Args:
            file_path: Path/key of the file in storage

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        except (ClientError, BotoCoreError, OSError) as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in storage

        Args:
            file_path: Path/key of the file in storage

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except (ClientError, BotoCoreError, OSError):
            return False

    def get_file_url(self, file_path: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for file access

        Args:
            file_path: Path/key of the file in storage
            expiration: URL expiration time in seconds (default 1 hour)

        Returns:
            Presigned URL, or None if failed
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": file_path},
                ExpiresIn=expiration,
            )
            return url
        except (ClientError, BotoCoreError, OSError) as e:
            logger.error(f"Failed to generate presigned URL for {file_path}: {e}")
            return None

