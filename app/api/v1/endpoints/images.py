import os
import uuid
from typing import Optional

import aiofiles
from boto3.session import Session as AWSSession
from fastapi import APIRouter, UploadFile, Depends, Response
from fastapi.responses import FileResponse, JSONResponse
from magic import from_buffer
from pydantic import UUID4
from sqlalchemy.orm import Session as DBSession

from app.api import deps
from app.ext.s3 import create_presigned_post, create_presigned_url, verify_exists
from app.core.config import settings
from app.models.image import Image
from app.schemas.user import UserDetail

router = APIRouter()


@router.post("/upload/{privacy}/generate")
async def images_generate_upload_link(
    privacy: str,
    user: UserDetail = Depends(deps.get_current_user),
    db: DBSession = Depends(deps.get_db),
    aws: Optional[AWSSession] = Depends(deps.get_aws_session),
) -> Response:
    if privacy not in ["public", "private"]:
        return JSONResponse(
            content={
                "success": False,
                "detail": "privacy parameter should be 'public' or 'private'",
            },
            status_code=400,
        )

    public = privacy == "public"
    image_id = str(uuid.uuid4())
    db_image = Image(
        id=image_id,
        public=public,
        owner_id=user.id,
        content_type="image/jpeg",
    )

    if settings.PRODUCTION:
        presigned_post = create_presigned_post(aws, image_id, public)
        db_image.path = presigned_post["s3_uri"]
        create_response = presigned_post["create_response"] | {"id": image_id}
    else:
        db_image.path = os.path.join(settings.LOCAL_UPLOAD_DIR, f"{image_id}.jpg")
        create_response = {
            "url": f"{settings.API_V1_STR}/images/upload/dev/{image_id}",
            "id": image_id,
        }

    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    return JSONResponse({"success": True} | create_response)


@router.post("/upload/{image_id}/confirm")
async def images_confirm_uploaded(
    image_id: UUID4,
    user: UserDetail = Depends(deps.get_current_user),
    db: DBSession = Depends(deps.get_db),
    aws: AWSSession = Depends(deps.get_aws_session),
) -> Response:
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if (not db_image) or ((not db_image.public) and (db_image.owner_id != user.id)):
        return JSONResponse(
            {"success": False, "detail": "Image not found"}, status_code=404
        )

    if db_image.uploaded:
        return JSONResponse(
            {"success": False, "detail": "Image upload already confirmed"},
            status_code=404,
        )

    if not verify_exists(aws, db_image.path):
        return JSONResponse(
            {"success": False, "detail": "Image with that ID doesn't exist in S3"},
            status_code=404,
        )

    db_image.uploaded = True
    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    return JSONResponse({"success": True})


# Image upload route
@router.post("/upload/dev/{image_id}")
async def images_upload_local(
    file: UploadFile,
    image_id: UUID4,
    user: UserDetail = Depends(deps.get_current_user),
    db: DBSession = Depends(deps.get_db),
) -> Response:
    if settings.PRODUCTION:
        return JSONResponse(
            {
                "success": False,
                "detail": "Attempted to access development path in production",
            },
            status_code=400,
        )

    db_image = db.query(Image).filter(Image.id == image_id).first()
    if (not db_image) or (db_image.owner_id != user.id):
        return JSONResponse(
            {"success": False, "detail": "Path not found"}, status_code=404
        )

    if db_image.uploaded:
        return JSONResponse(
            {"success": False, "detail": "Image already uploaded"}, status_code=400
        )

    try:
        first_chunk = await file.read(settings.CHUNK_SIZE)
        # Generate a unique filename
        uploaded_content_type = from_buffer(first_chunk, mime=True)
        if uploaded_content_type not in ["image/jpeg"]:
            return JSONResponse(
                content={
                    "success": False,
                    "detail": "Image should be jpeg",
                },
                status_code=415,
            )

        # Save the uploaded file
        async with aiofiles.open(db_image.path, "wb") as image_file:
            await image_file.write(first_chunk)
            while chunk := await file.read(settings.CHUNK_SIZE):
                await image_file.write(chunk)

        db_image.uploaded = True
        db.commit()
        db.refresh(db_image)

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )


# Image retrieval route
@router.get("/media/{image_id}")
async def images_retrieve(
    image_id: UUID4,
    user: UserDetail | None = Depends(deps.verify_jwt_to_uuid_or_none),
    db: DBSession = Depends(deps.get_db),
    aws: Optional[AWSSession] = Depends(deps.get_aws_session),
) -> Response:
    try:
        user_id = user.id if user is not None else ""
        db_image = db.query(Image).filter(Image.id == image_id).first()
        if (not db_image) or ((not db_image.public) and (db_image.owner_id != user_id)):
            return JSONResponse(
                {"success": False, "detail": "Image not found"}, status_code=404
            )

        if settings.PRODUCTION:
            return JSONResponse(
                {
                    "success": True,
                    "uri": create_presigned_url(
                        aws, db_image.path, db_image.content_type, db_image.public
                    ),
                }
            )
        else:
            return JSONResponse(
                {
                    "success": True,
                    "uri": f"{settings.API_V1_STR}/images/media/dev/{image_id}",
                }
            )

    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )


# Image retrieval route
@router.get("/media/dev/{image_id}")
async def images_retrieve_local(
    image_id: UUID4,
    user: UserDetail | None = Depends(deps.verify_jwt_to_uuid_or_none),
    db: DBSession = Depends(deps.get_db),
) -> Response:
    if settings.PRODUCTION:
        return JSONResponse(
            {
                "success": False,
                "detail": "Attempted to access development path in production",
            },
            status_code=400,
        )

    try:
        user_id = user.id if user is not None else ""
        db_image = db.query(Image).filter(Image.id == image_id).first()
        if (
            (not db_image)
            or ((not db_image.public) and (db_image.owner_id != user_id))
            or (not db_image.uploaded)
        ):
            return JSONResponse(
                {"success": False, "detail": "Image not found"}, status_code=404
            )

        return FileResponse(db_image.path, media_type=db_image.content_type)
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )
