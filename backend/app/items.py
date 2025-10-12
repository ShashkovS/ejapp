from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from backend.app.deps import SessionDep, TokenDep, get_current_user_id
from backend.app.schemas import ItemCreate, ItemOut, ItemRead
from backend.db import Item

router = APIRouter(tags=['items'])
private_router = APIRouter(prefix='/private', tags=['private'])


@router.get('/healthz', include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/items', response_model=list[ItemRead])
async def read_items(
    session: SessionDep,
    token: TokenDep,
) -> list[ItemRead]:
    user_id = await get_current_user_id(token, session)
    result = await session.execute(select(Item.title).where(Item.owner_id == user_id))
    return [ItemRead(title=title) for title in result.scalars().all()]


@router.post('/items', response_model=ItemOut)
async def create_item(
    item_in: ItemCreate,
    session: SessionDep,
    token: TokenDep,
) -> ItemOut:
    user_id = await get_current_user_id(token, session)

    item = Item(title=item_in.title, owner_id=user_id)
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return ItemOut(id=item.id, title=item.title)


@private_router.get('/ping')
async def private_ping() -> dict[str, str]:
    return {'status': 'private-ok'}


__all__ = ['private_router', 'router']
