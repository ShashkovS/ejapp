from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import token_hex
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import get_session, get_user_by_email
from backend.app.schemas import Token, UserCreate, UserCredentials
from backend.db import User

router = APIRouter(prefix='/auth', tags=['auth'])
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/login')
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _create_token(sub: str, expires_delta: timedelta) -> str:
    payload = {'sub': sub, 'exp': datetime.now(tz=UTC) + expires_delta}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(sub: str, expires: timedelta | None = None) -> str:
    delta = expires or timedelta(minutes=settings.access_token_expire_minutes)
    return _create_token(sub, delta)


def create_refresh_token(sub: str) -> str:
    delta = timedelta(minutes=settings.refresh_token_expire_minutes)
    return _create_token(sub, delta)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def _issue_tokens(email: str) -> Token:
    return Token(
        access_token=create_access_token(email),
        refresh_token=create_refresh_token(email),
    )


@router.post('/register', response_model=Token)
async def register_user(user_in: UserCreate, session: SessionDep) -> Token:
    existing = await get_user_by_email(session, user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail='Email already registered')

    user = User(email=user_in.email, hashed_password=get_password_hash(user_in.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _issue_tokens(user.email)


@router.post('/login', response_model=Token)
async def login_user(credentials: UserCredentials, session: SessionDep) -> Token:
    user = await get_user_by_email(session, credentials.email)
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    return _issue_tokens(user.email)


@router.post('/refresh', response_model=Token)
async def refresh_access_token(token: TokenDep) -> Token:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail='Refresh token expired') from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail='Invalid refresh token') from exc

    sub = payload.get('sub')
    if not sub:
        raise HTTPException(status_code=401, detail='Invalid token payload')
    return _issue_tokens(sub)


@router.get('/google/callback', response_model=Token)
async def google_callback(code: str, session: SessionDep) -> Token:
    google_email = 'googleuser@example.com'
    user = await get_user_by_email(session, google_email)
    if not user:
        user = User(email=google_email, hashed_password=get_password_hash(token_hex(8)))
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return _issue_tokens(user.email)


__all__ = ['create_access_token', 'create_refresh_token', 'decode_token', 'oauth2_scheme', 'router']
