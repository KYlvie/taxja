"""
One-time cleanup script: delete all users, data, and MinIO files.
Run from backend/ directory: python cleanup_all.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.db.base import engine
from app.core.config import settings
import boto3
from botocore.exceptions import ClientError

def clean_database():
    """Truncate all user-data tables (preserve schema + plans/configs)."""
    # Order matters: delete child tables first to avoid FK violations
    tables_to_truncate = [
        # Children first
        "transaction_line_items",
        "asset_events",
        "asset_policy_snapshots",
        "classification_corrections",
        "dismissed_suggestions",
        "employer_annual_archive_documents",
        "employer_month_documents",
        "employer_annual_archives",
        "employer_months",
        "import_conflicts",
        "import_metrics",
        "historical_import_uploads",
        "historical_import_sessions",
        "credit_ledger",
        "topup_purchases",
        "credit_balances",
        "usage_records",
        "payment_events",
        "chat_messages",
        "notifications",
        "audit_logs",
        "disclaimer_acceptances",
        "account_deletion_logs",
        "tax_filing_data",
        "loss_carryforwards",
        # Mid-level
        "transactions",
        "documents",
        "recurring_transactions",
        "property_loans",
        "properties",
        "tax_reports",
        # Subscriptions
        "subscriptions",
        # Users last
        "users",
    ]

    for table in tables_to_truncate:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            print(f"  [DB] Truncated: {table}")
        except Exception as e:
            print(f"  [DB] Skip {table} (not found)")

    print("[DB] All user data deleted.\n")


def clean_minio():
    """Delete all objects in the MinIO bucket."""
    endpoint = settings.MINIO_ENDPOINT
    if endpoint and not endpoint.startswith(("http://", "https://")):
        secure = getattr(settings, "MINIO_SECURE", False)
        endpoint = f"{'https' if secure else 'http'}://{endpoint}"

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )

    bucket = settings.MINIO_BUCKET
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        print(f"[MinIO] Bucket '{bucket}' does not exist. Nothing to clean.")
        return

    # List and delete all objects
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket):
        objects = page.get("Contents", [])
        if not objects:
            continue
        delete_keys = [{"Key": obj["Key"]} for obj in objects]
        client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
        deleted += len(delete_keys)
        print(f"  [MinIO] Deleted {len(delete_keys)} objects...")

    print(f"[MinIO] Total deleted: {deleted} objects from '{bucket}'.\n")


def clean_redis():
    """Flush Redis cache."""
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.flushdb()
        print("[Redis] Cache flushed.\n")
    except Exception as e:
        print(f"[Redis] Skip: {e}\n")


if __name__ == "__main__":
    print("=" * 50)
    print("  TAXJA CLEANUP: Deleting all data")
    print("=" * 50)
    print()

    clean_database()
    clean_minio()
    clean_redis()

    print("=" * 50)
    print("  DONE. All users, files, and cache cleared.")
    print("=" * 50)
