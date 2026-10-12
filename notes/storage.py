import boto3

from django.conf import settings


def get_r2_client():
    """
    Returns a boto3 S3 client configured for Cloudflare R2.
    """

    return boto3.client(
        service_name="s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name="auto", # Required by boto3, not used by R2 - as per Cloudflare R2 docs
    )
