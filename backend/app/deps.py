from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import decode_token, oauth2_scheme
from backend.app.database import get_session, get_user_by_email

SessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user_id(token: TokenDep, session: SessionDep) -> int:
    try:
        payload = decode_token(token)
    except PyJWTError as exc:  # pragma: no cover - propagated via HTTPException below
        raise HTTPException(status_code=401, detail='Not authenticated') from exc

    email = payload.get('sub')
    if not email:
        raise HTTPException(status_code=401, detail='Invalid token payload')

    user = await get_user_by_email(session, email)
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    return user.id


__all__ = ['SessionDep', 'TokenDep', 'get_current_user_id']
