from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


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


class ContestConfigPayload(BaseModel):
    contest_ids: list[Annotated[int, Field(gt=0)]]


class ContestProblem(BaseModel):
    id: int
    short_name: str
    long_name: str | None = None


class ContestRunSummary(BaseModel):
    run_id: int
    status: str
    language: str | None = None
    submitted_at: datetime | None = None


class ContestCell(BaseModel):
    problem_id: int
    best_run: ContestRunSummary | None = None


class ContestRow(BaseModel):
    user_id: int
    user_login: str
    user_name: str | None = None
    cells: list[ContestCell]


class ContestReport(BaseModel):
    contest_id: int
    contest_name: str
    problems: list[ContestProblem]
    rows: list[ContestRow]


class ContestReportsResponse(BaseModel):
    contests: list[ContestReport]
