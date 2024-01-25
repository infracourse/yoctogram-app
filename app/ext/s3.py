from datetime import datetime, timedelta
import logging
from time import time
from typing import Dict, Any, Sequence
from urllib.parse import urlparse

from boto3.session import Session as AWSSession
from botocore.config import Config
from botocore.exceptions import ClientError
from freezegun import freeze_time
from mypy_boto3_s3.client import S3Client

from app.core.config import settings


def get_bucket_conditions(
    public: bool,
) -> Sequence[Sequence[str | int] | Dict[str, Any]]:
    return [
        ["content-length-range", 1, 10 * 1000 * 1000],
        {
            "bucket": settings.PUBLIC_IMAGES_BUCKET
            if public
            else settings.PRIVATE_IMAGES_BUCKET
        },
    ]


def get_resource_prefix() -> str:
    now = datetime.now()
    return f"{now.year}/{now.month}/{now.day}"


def parse_s3_uri(uri: str) -> Dict[str, str]:
    o = urlparse(uri)
    return {"Bucket": o.netloc, "Key": o.path.lstrip("/")}


def create_presigned_post(
    session: AWSSession,
    object_name: str,
    public: bool = False,
) -> Dict[str, Any]:
    s3_client: S3Client = session.client(
        "s3", endpoint_url=f"https://s3.{settings.AWS_DEFAULT_REGION}.amazonaws.com"
    )
    bucket_name = (
        settings.PUBLIC_IMAGES_BUCKET if public else settings.PRIVATE_IMAGES_BUCKET
    )
    bucket_key = f"{get_resource_prefix()}/{object_name}"
    try:
        response = s3_client.generate_presigned_post(
            bucket_name,
            bucket_key,
            Conditions=get_bucket_conditions(public),
            ExpiresIn=int(timedelta(hours=1).total_seconds()),
        )
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL and required fields
    return {"create_response": response, "s3_uri": f"s3://{bucket_name}/{bucket_key}"}


def create_presigned_url(
    session: AWSSession, s3_uri: str, content_type: str, public: bool
) -> str:
    s3_client: S3Client = session.client(
        "s3",
        config=Config(
            region_name=settings.AWS_DEFAULT_REGION, s3={"addressing_style": "virtual"}
        ),
    )
    try:
        current_timestamp = time()
        cache_age = settings.CLOUDFRONT_PRESIGNED_URL_EXPIRY - int(
            timedelta(hours=1).total_seconds()
        )

        # Freeze the time at the beginning of the epoch week to allow browser to
        # cache the presigned URL for a week
        with freeze_time(
            datetime.fromtimestamp(
                current_timestamp
                - (current_timestamp % settings.CLOUDFRONT_PRESIGNED_URL_EXPIRY)
            )
        ):
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params=parse_s3_uri(s3_uri)
                | {
                    "ResponseContentType": content_type,
                    "ResponseCacheControl": f"private, max-age={cache_age}, immutable",
                },
                ExpiresIn=settings.CLOUDFRONT_PRESIGNED_URL_EXPIRY,
            )

            # Replace the S3 hostname with the Cloudfront distribution
            return (
                urlparse(presigned_url)
                ._replace(
                    netloc=(
                        settings.PUBLIC_IMAGES_CLOUDFRONT_DISTRIBUTION
                        if public
                        else settings.PRIVATE_IMAGES_CLOUDFRONT_DISTRIBUTION
                    )
                )
                .geturl()
            )
    except ClientError as e:
        logging.error(e)
        return None


def verify_exists(session: AWSSession, s3_uri: str) -> bool:
    s3_client: S3Client = session.client("s3")
    try:
        s3_client.head_object(**parse_s3_uri(s3_uri))
        return True
    except s3_client.exceptions.NoSuchKey:
        return False
