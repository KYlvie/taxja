"""Compatibility wrapper around MinIO/S3 operations used by backup flows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinioService:
    """Backward-compatible MinIO/S3 service used by legacy backup code."""

    def __init__(self) -> None:
        endpoint = settings.MINIO_ENDPOINT
        if endpoint and not endpoint.startswith(("http://", "https://")):
            secure = getattr(settings, "MINIO_SECURE", False)
            endpoint = f"{'https' if secure else 'http'}://{endpoint}"

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name=getattr(settings, "MINIO_REGION", "us-east-1"),
        )

    def bucket_exists(self, bucket_name: str) -> bool:
        try:
            self.client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False

    def create_bucket(self, bucket_name: str) -> None:
        self.client.create_bucket(Bucket=bucket_name)

    def list_objects(self, bucket_name: str) -> Iterable[object]:
        paginator = self.client.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=bucket_name):
            for item in page.get("Contents", []):
                objects.append(
                    type(
                        "MinioObject",
                        (),
                        {
                            "object_name": item["Key"],
                            "size": item.get("Size", 0),
                            "last_modified": item.get("LastModified"),
                        },
                    )()
                )
        return objects

    def upload_file(self, bucket_name: str, object_name: str, file_path: str) -> None:
        self.client.upload_file(file_path, bucket_name, object_name)

    def download_file(self, bucket_name: str, object_name: str, file_path: str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(bucket_name, object_name, str(path))

    def delete_file(self, bucket_name: str, object_name: str) -> None:
        self.client.delete_object(Bucket=bucket_name, Key=object_name)
