import boto3
from botocore.config import Config
import uuid
from io import BytesIO
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_bytes(data: bytes, key: str, content_type: str = "image/jpeg") -> str:
    """Upload bytes to R2 and return the public URL."""
    client = _get_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return f"{settings.R2_PUBLIC_BASE_URL}/{key}"


def delete_object(key: str) -> None:
    """Delete an object from R2."""
    client = _get_client()
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)


def generate_presigned_url(key: str, expiry: int = 86400) -> str:
    """Generate a presigned URL for private objects."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expiry,
    )


def make_storage_key(app_name: str, kind: str, user_id: str, file_id: str, ext: str) -> str:
    """Build the canonical storage key: {app_name}/{kind}/{user_id}/{file_id}.{ext}"""
    return f"{app_name}/{kind}/{user_id}/{file_id}.{ext}"
