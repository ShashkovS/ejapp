from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import decode_token, oauth2_scheme
from backend.app.database import get_session, get_user_by_email
from backend.app.schemas import ItemCreate, ItemOut, ItemRead
from backend.db import Item

router = APIRouter(tags=['items'])
private_router = APIRouter(prefix='/private', tags=['private'])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


@router.get('/healthz', include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {'status': 'ok'}


async def _get_user_from_token(token: str, session: AsyncSession) -> int:
    try:
        payload = decode_token(token)
    except PyJWTError as exc:
        raise HTTPException(status_code=401, detail='Not authenticated') from exc

    email = payload.get('sub')
    if not email:
        raise HTTPException(status_code=401, detail='Invalid token payload')

    user = await get_user_by_email(session, email)
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    return user.id


@router.get('/items', response_model=list[ItemRead])
async def read_items(
    session: SessionDep,
    token: TokenDep,
) -> list[ItemRead]:
    user_id = await _get_user_from_token(token, session)
    result = await session.execute(select(Item.title).where(Item.owner_id == user_id))
    return [ItemRead(title=title) for title in result.scalars().all()]


@router.post('/items', response_model=ItemOut)
async def create_item(
    item_in: ItemCreate,
    session: SessionDep,
    token: TokenDep,
) -> ItemOut:
    user_id = await _get_user_from_token(token, session)

    item = Item(title=item_in.title, owner_id=user_id)
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return ItemOut(id=item.id, title=item.title)


@private_router.get('/ping')
async def private_ping() -> dict[str, str]:
    return {'status': 'private-ok'}


__all__ = ['private_router', 'router']
