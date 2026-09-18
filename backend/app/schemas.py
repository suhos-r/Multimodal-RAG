import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(SignupIn):
    pass


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime
    preview: str | None = None


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list | dict = []
    model: str | None = None
    cached: bool = False
    created_at: datetime
