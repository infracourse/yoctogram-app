from datetime import timedelta
import secrets
from typing import Optional

from pydantic import PostgresDsn, field_validator
from pydantic_core.core_schema import ValidationInfo
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PRODUCTION: bool = True
    DEBUG: bool = False

    PROJECT_NAME: str = "yoctogram"

    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FORWARD_FACING_NAME: str

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    JWT_ALGORITHM: str = "HS256"

    CHUNK_SIZE: int = 2048
    IMAGE_PAGINATION: int = 100

    LOCAL_UPLOAD_DIR: str = "/uploads"

    AWS_DEFAULT_REGION: str = "us-west-2"

    PUBLIC_IMAGES_BUCKET: Optional[str] = None
    PRIVATE_IMAGES_BUCKET: Optional[str] = None

    PUBLIC_IMAGES_CLOUDFRONT_DISTRIBUTION: str = None
    PRIVATE_IMAGES_CLOUDFRONT_DISTRIBUTION: str = None

    CLOUDFRONT_PRESIGNED_URL_EXPIRY: int = int(timedelta(days=7).total_seconds())

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_HOST"),
            port=info.data.get("POSTGRES_PORT"),
            path=info.data.get("POSTGRES_DB"),
        )

    @field_validator(
        "PUBLIC_IMAGES_BUCKET",
        "PRIVATE_IMAGES_BUCKET",
        "PUBLIC_IMAGES_CLOUDFRONT_DISTRIBUTION",
        "PRIVATE_IMAGES_CLOUDFRONT_DISTRIBUTION",
        mode="before",
    )
    @classmethod
    def require_s3_cloudfront_in_prod(cls, v: str, info: ValidationInfo) -> str:
        if not info.data.get("PRODUCTION"):
            return "unused"
        if not isinstance(v, str):
            raise ValueError("Require S3 bucket names in production")
        return v

    class Config:
        case_sensitive = True


settings = Settings()
