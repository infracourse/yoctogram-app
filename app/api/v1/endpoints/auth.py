from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin
from app.schemas.token import Token

router = APIRouter()


@router.post("/register/", status_code=201)
async def auth_register(
    user: UserCreate, db: Session = Depends(deps.get_db)
) -> Response:
    try:
        db_user = (
            db.query(User)
            .filter(or_(User.username == user.username, User.email == user.email))
            .first()
        )
        if db_user:
            return JSONResponse(
                content={
                    "success": False,
                    "detail": "Email or username already registered",
                },
                status_code=400,
            )

        hashed_password = get_password_hash(user.password)

        db_user = User(
            **user.model_dump(exclude={"password"}), password_hash=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        return {"success": True}
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )


@router.post("/login/", response_model=Token)
async def auth_login(user: UserLogin, db: Session = Depends(deps.get_db)) -> Token:
    try:
        db_user = db.query(User).filter(User.username == user.username).first()
        if not db_user or not verify_password(user.password, db_user.password_hash):
            return JSONResponse(
                content={"success": False, "detail": "Invalid username or password"},
                status_code=401,
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            str(db_user.id), expires_delta=access_token_expires
        )

        return Token(access_token=access_token, token_type="bearer")
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "detail": str(e) if settings.DEBUG else "Internal server error",
            },
            status_code=500,
        )
