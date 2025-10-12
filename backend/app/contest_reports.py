from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.deps import SessionDep, TokenDep, get_current_user_id
from backend.app.schemas import (
    ContestCell,
    ContestConfigPayload,
    ContestProblem,
    ContestReport,
    ContestReportsResponse,
    ContestRow,
    ContestRunSummary,
)
from backend.db import ContestReportConfig
from backend.ejudge import EjudgeClient, EjudgeClientError

router = APIRouter(prefix='/private', tags=['private'])

_HIGHLIGHT_PRIORITY = {'OK': 0, 'AC': 1, 'PR': 2, 'SM': 3}
_HIGHLIGHT_STATUSES = set(_HIGHLIGHT_PRIORITY)


async def _get_or_create_config(session: AsyncSession, user_id: int) -> ContestReportConfig:
    result = await session.execute(select(ContestReportConfig).where(ContestReportConfig.user_id == user_id))
    config = result.scalars().first()
    if config is None:
        config = ContestReportConfig(user_id=user_id, contest_ids='')
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return config


def _parse_contest_ids(raw: str) -> list[int]:
    if not raw:
        return []
    ids: set[int] = set()
    for part in raw.split(','):
        item = part.strip()
        if not item:
            continue
        try:
            value = int(item)
        except ValueError:
            continue
        if value > 0:
            ids.add(value)
    return sorted(ids)


def _serialize_contest_ids(values: list[int]) -> str:
    deduped = sorted({value for value in values if value > 0})
    return ','.join(str(value) for value in deduped)


async def get_ejudge_client() -> AsyncIterator[EjudgeClient]:
    if not settings.ejudge_origin or not settings.ejudge_token:
        raise HTTPException(status_code=503, detail='Ejudge integration is not configured')

    origin = settings.ejudge_origin.rstrip('/')
    async with EjudgeClient(origin, settings.ejudge_token) as client:
        yield client


EjudgeClientDep = Annotated[EjudgeClient, Depends(get_ejudge_client)]


def _extract_submission_time(run: dict[str, Any]) -> datetime | None:
    candidates: list[tuple[str, float]] = [
        ('last_change_us', 1_000_000),
        ('time_us', 1_000_000),
        ('time_ms', 1_000),
        ('time', 1),
    ]
    for key, divisor in candidates:
        value = run.get(key)
        if isinstance(value, int | float):
            seconds = value / divisor
            try:
                return datetime.fromtimestamp(seconds, tz=UTC)
            except (OverflowError, OSError):
                continue
    return None


def _build_run_summary(run: dict[str, Any]) -> ContestRunSummary:
    status = str(run.get('status_str') or '').strip().upper()
    language = run.get('lang_name') or run.get('language')
    if language is None and run.get('lang_id') is not None:
        language = str(run['lang_id'])
    submitted_at = _extract_submission_time(run)
    return ContestRunSummary(
        run_id=int(run['run_id']),
        status=status,
        language=language,
        submitted_at=submitted_at,
    )


def _is_better_run(candidate: ContestRunSummary, current: ContestRunSummary) -> bool:
    cand_priority = _HIGHLIGHT_PRIORITY.get(candidate.status, float('inf'))
    current_priority = _HIGHLIGHT_PRIORITY.get(current.status, float('inf'))
    if cand_priority != current_priority:
        return cand_priority < current_priority

    cand_time = candidate.submitted_at
    current_time = current.submitted_at
    if cand_time and current_time:
        if cand_time != current_time:
            return cand_time < current_time
    elif cand_time and not current_time:
        return True
    elif current_time and not cand_time:
        return False

    return candidate.run_id < current.run_id


def _build_report(
    contest_id: int,
    contest_payload: dict[str, Any],
    problems_payload: list[dict[str, Any]],
    runs_payload: list[dict[str, Any]],
) -> ContestReport:
    contest_name = contest_payload.get('name') or contest_payload.get('name_en') or f'Contest {contest_id}'

    problems: list[ContestProblem] = []
    for problem in problems_payload:
        try:
            pid = int(problem['id'])
        except (KeyError, TypeError, ValueError):
            continue
        problems.append(
            ContestProblem(
                id=pid,
                short_name=str(problem.get('short_name') or pid),
                long_name=problem.get('long_name'),
            )
        )
    problems.sort(key=lambda item: (item.short_name, item.id))

    rows: dict[int, dict[str, Any]] = {}
    cells_by_user: dict[int, dict[int, ContestRunSummary]] = defaultdict(dict)

    for run in runs_payload:
        try:
            user_id = int(run['user_id'])
            problem_id = int(run['prob_id'])
            int(run['run_id'])
        except (KeyError, TypeError, ValueError):
            continue

        rows.setdefault(
            user_id,
            {
                'user_id': user_id,
                'user_login': str(run.get('user_login') or f'user-{user_id}'),
                'user_name': run.get('user_name'),
            },
        )
        status = str(run.get('status_str') or '').strip().upper()
        if status not in _HIGHLIGHT_STATUSES:
            continue

        summary = _build_run_summary(run)
        current = cells_by_user[user_id].get(problem_id)
        if current is None or _is_better_run(summary, current):
            cells_by_user[user_id][problem_id] = summary

    contest_rows: list[ContestRow] = []
    for user_id, row_payload in rows.items():
        ordered_cells: list[ContestCell] = []
        for problem in problems:
            ordered_cells.append(
                ContestCell(
                    problem_id=problem.id,
                    best_run=cells_by_user[user_id].get(problem.id),
                )
            )
        contest_rows.append(
            ContestRow(
                user_id=user_id,
                user_login=row_payload['user_login'],
                user_name=row_payload.get('user_name'),
                cells=ordered_cells,
            )
        )

    contest_rows.sort(key=lambda row: (row.user_name or row.user_login, row.user_id))

    return ContestReport(
        contest_id=contest_id,
        contest_name=str(contest_name),
        problems=problems,
        rows=contest_rows,
    )


@router.get('/contest-config', response_model=ContestConfigPayload)
async def get_contest_config(session: SessionDep, token: TokenDep) -> ContestConfigPayload:
    user_id = await get_current_user_id(token, session)
    config = await _get_or_create_config(session, user_id)
    ids = _parse_contest_ids(config.contest_ids)
    return ContestConfigPayload(contest_ids=ids)


@router.put('/contest-config', response_model=ContestConfigPayload)
async def update_contest_config(
    payload: ContestConfigPayload,
    session: SessionDep,
    token: TokenDep,
) -> ContestConfigPayload:
    user_id = await get_current_user_id(token, session)
    config = await _get_or_create_config(session, user_id)
    serialised = _serialize_contest_ids(payload.contest_ids)
    config.contest_ids = serialised
    await session.commit()
    ids = _parse_contest_ids(config.contest_ids)
    return ContestConfigPayload(contest_ids=ids)


@router.get('/contest-reports', response_model=ContestReportsResponse)
async def get_contest_reports(
    session: SessionDep,
    token: TokenDep,
    ejudge_client: EjudgeClientDep,
) -> ContestReportsResponse:
    user_id = await get_current_user_id(token, session)
    config = await _get_or_create_config(session, user_id)
    contest_ids = _parse_contest_ids(config.contest_ids)
    if not contest_ids:
        return ContestReportsResponse(contests=[])

    reports: list[ContestReport] = []
    for contest_id in contest_ids:
        try:
            contest_payload = await ejudge_client.master.contest_status_json(contest_id=contest_id)
            if not contest_payload.get('ok'):
                raise HTTPException(status_code=502, detail=f'Failed to fetch contest {contest_id} metadata')
            contest_result = contest_payload.get('result') or {}
            contest_info = contest_result.get('contest') or {}
            problems_payload = contest_result.get('problems') or []

            runs_payload = await ejudge_client.master.list_runs_json(contest_id=contest_id, first_run=0)
            if not runs_payload.get('ok'):
                raise HTTPException(status_code=502, detail=f'Failed to fetch contest {contest_id} runs')
            runs_result = runs_payload.get('result') or {}
            runs = runs_result.get('runs') or []
        except EjudgeClientError as exc:
            raise HTTPException(status_code=502, detail=f'Error talking to ejudge for contest {contest_id}') from exc

        report = _build_report(contest_id, contest_info, list(problems_payload), list(runs))
        reports.append(report)

    return ContestReportsResponse(contests=reports)


__all__ = ['get_ejudge_client', 'router']
