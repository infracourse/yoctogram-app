from pydantic import BaseModel, EmailStr, UUID4


class BaseUser(BaseModel):
    username: str


class UserCreate(BaseUser):
    email: EmailStr
    password: str


class UserLogin(BaseUser):
    password: str


class UserDetail(BaseUser):
    id: UUID4
    email: EmailStr
