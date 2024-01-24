from typing import Generator
from boto3 import Session as AWSSession
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.user import UserDetail

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_db() -> Generator[DBSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_aws_session() -> Generator[AWSSession, None, None]:
    session = AWSSession()
    yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: DBSession = Depends(get_db)
) -> UserDetail:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        uid: str = payload.get("sub")
        if uid is None:
            raise HTTPException(status_code=400, detail="Invalid token")

        db_user = db.query(User).filter(User.id == uid).first()
        if db_user is None:
            raise HTTPException(status_code=401, detail="User not found")

        return UserDetail(id=uid, username=db_user.username, email=db_user.email)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


async def verify_jwt_to_uuid_or_none(
    token: str = Depends(oauth2_scheme), db: DBSession = Depends(get_db)
) -> UserDetail | None:
    try:
        user = await get_current_user(token, db)
        return user
    except HTTPException:
        return None
