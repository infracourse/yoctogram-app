from datetime import datetime, timedelta
import logging
import uuid
from typing import Optional

from boto3.session import Session as AWSSession
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from app.api import deps
from app.core.config import settings
from app.ext.s3 import create_presigned_url
from app.models.image import Image
from app.schemas.user import UserDetail

router = APIRouter()


@router.get("/latest")
async def feed_latest(
    before: datetime = datetime.now() + timedelta(days=1),  # buffer for timezones
    after: datetime = datetime.fromtimestamp(0),
    user: UserDetail | None = Depends(deps.verify_jwt_to_uuid_or_none),
    db: DBSession = Depends(deps.get_db),
    aws: Optional[AWSSession] = Depends(deps.get_aws_session),
) -> Response:
    try:
        image_filters = [
            Image.created_at < before,
            Image.created_at > after,
            Image.public,
        ]

        if user is not None:
            image_filters[-1] = or_(Image.public, Image.owner_id == user.id)

        db_images = (
            db.query(Image)
            .filter(*image_filters)
            .order_by(Image.created_at.desc())
            .limit(settings.IMAGE_PAGINATION)
        )

        return_content = {"success": True, "count": db_images.count(), "results": []}
        for image_record in db_images:
            if settings.PRODUCTION:
                download_part_url = create_presigned_url(
                    aws,
                    image_record.path,
                    image_record.content_type,
                    image_record.public,
                )
            else:
                download_part_url = (
                    f"{settings.API_V1_STR}/images/media/dev/{image_record.id}"
                )

            return_content["results"].append(
                {
                    "id": str(image_record.id),
                    "creator": str(image_record.owner_id),
                    "download_url": download_part_url,
                    "created_at": str(image_record.created_at),
                }
            )

        return JSONResponse(return_content)
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )


@router.get("/by_user/{creator}")
async def feed_by_user(
    creator: uuid.UUID,
    before: datetime = datetime.now() + timedelta(days=1),  # buffer for timezones
    after: datetime = datetime.fromtimestamp(0),
    user: UserDetail | None = Depends(deps.verify_jwt_to_uuid_or_none),
    db: DBSession = Depends(deps.get_db),
    aws: Optional[AWSSession] = Depends(deps.get_aws_session),
) -> Response:
    try:
        user_id = user.id if user is not None else None

        db_images = (
            db.query(Image)
            .filter(
                Image.created_at < before,
                Image.created_at > after,
                Image.owner_id == creator,
                or_(Image.owner_id == user_id, Image.public),
            )
            .order_by(Image.created_at.desc())
            .limit(settings.IMAGE_PAGINATION)
        )

        return_content = {"success": True, "count": db_images.count(), "results": []}
        for image_record in db_images:
            if settings.PRODUCTION:
                download_part_url = create_presigned_url(
                    aws,
                    image_record.path,
                    image_record.content_type,
                    image_record.public,
                )
            else:
                download_part_url = (
                    f"{settings.API_V1_STR}/images/media/dev/{image_record.id}"
                )

            return_content["results"].append(
                {
                    "id": str(image_record.id),
                    "creator": str(image_record.owner_id),
                    "download_url": download_part_url,
                    "created_at": str(image_record.created_at),
                }
            )

        return JSONResponse(return_content)
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )
