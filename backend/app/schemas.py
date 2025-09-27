from __future__ import annotations

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class UserCredentials(BaseModel):
    email: str
    password: str


class UserCreate(UserCredentials):
    """Alias for clarity when creating users."""


class ItemCreate(BaseModel):
    title: str


class ItemRead(BaseModel):
    title: str


class ItemOut(ItemRead):
    id: int
