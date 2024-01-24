import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserDetail

router = APIRouter()


@router.get("/me", response_model=UserDetail)
async def users_me(current_user: UserDetail = Depends(deps.get_current_user)):
    return current_user


# get user details from id
@router.get("/profile/{user}")
async def users_username_from_id(
    user: uuid.UUID, db: Session = Depends(deps.get_db)
) -> JSONResponse:
    try:
        db_user = db.query(User).filter(User.id == user).first()
        if not db_user:
            return JSONResponse(
                content={"success": False, "detail": "User not found"},
                status_code=404,
            )

        return JSONResponse(
            content={"success": True, "username": db_user.username, "bio": db_user.bio}
        )
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )
