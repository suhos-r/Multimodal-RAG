import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..db import get_db
from ..deps import decode_sub, issue_pair
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/signup", response_model=schemas.TokenPair, status_code=201)
async def signup(body: schemas.SignupIn, db: AsyncSession = Depends(get_db)):
    email = body.email.lower().strip()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(email=email, pw_hash=pwd.hash(body.password))
    db.add(user)
    await db.commit()
    access, refresh = issue_pair(str(user.id))
    return schemas.TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=schemas.TokenPair)
async def login(body: schemas.LoginIn, db: AsyncSession = Depends(get_db)):
    email = body.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not pwd.verify(body.password, user.pw_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    access, refresh = issue_pair(str(user.id))
    return schemas.TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=schemas.TokenPair)
async def refresh(body: schemas.RefreshIn):
    sub = decode_sub(body.refresh_token)
    access, refresh_tok = issue_pair(sub)
    return schemas.TokenPair(access_token=access, refresh_token=refresh_tok)
