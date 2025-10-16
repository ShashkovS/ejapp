from __future__ import annotations

import asyncio
import html
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from backend.app.config import settings
from backend.app.report_config import TopicConfig, load_topics
from backend.ejudge.client import EjudgeClient, EjudgeClientError, EjudgeReplyError


class ReportBuildError(RuntimeError):
    """Raised when the ejudge report cannot be generated."""


class ProblemSummary(BaseModel):
    code: str
    name: str
    points: int


class TopicUserRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user: str
    solved: list[bool]
    solved_count: int = Field(alias='solvedCount')
    score: int


class TopicReport(BaseModel):
    name: str
    problems: list[ProblemSummary]
    rows: list[TopicUserRow]


class SummaryCell(BaseModel):
    solved: int
    score: int


class WeeklySummary(BaseModel):
    weeks: list[str]
    data: dict[str, dict[str, int]]


class ReportsResponse(BaseModel):
    users: list[str]
    topics: list[TopicReport]
    summary: dict[str, dict[str, SummaryCell]]
    weekly: WeeklySummary


class RunPayload(Mapping[str, Any]):
    """Typed helper exposing run payload keys with dict-like access."""

    _backing: Mapping[str, Any]

    def __init__(self, backing: Mapping[str, Any]):
        self._backing = backing

    def __getitem__(self, key: str) -> Any:
        return self._backing[key]

    def __iter__(self) -> Iterable[str]:
        return iter(self._backing)

    def __len__(self) -> int:
        return len(self._backing)

    @property
    def status(self) -> str:
        return str(self._backing.get('status_str', ''))

    @property
    def run_id(self) -> int:
        return int(self._backing.get('run_id', 0))

    @property
    def user(self) -> str | None:
        raw = self._backing.get('user_name')
        return str(raw) if raw is not None else None

    @property
    def problem(self) -> str | None:
        raw = self._backing.get('prob_name')
        return str(raw) if raw is not None else None

    @property
    def timestamp(self) -> datetime | None:
        value = self._backing.get('run_time')
        if value is None:
            return None
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(seconds, tz=UTC)


@dataclass(slots=True)
class TopicPayload:
    config: TopicConfig
    problems: list[ProblemSummary]
    runs: list[RunPayload]


_PROBLEM_PATTERN = re.compile(
    r'<h3 class="prob_name"[^>]*>([\w★\*°]+):(?! Title)\s*(.*?)\s*(\(\d+\s*pt\w*\) *)?</h3>',
    re.IGNORECASE | re.DOTALL,
)
_COMMENT_PATTERN = re.compile(r'<!--.*?-->', re.DOTALL)


def _strip_comments(html_text: str) -> str:
    return _COMMENT_PATTERN.sub('', html_text)


def parse_problems(html_text: str) -> list[ProblemSummary]:
    problems: list[ProblemSummary] = []
    cleaned = _strip_comments(html_text)
    for match in _PROBLEM_PATTERN.finditer(cleaned):
        raw_code, raw_name, points_payload = match.groups()
        code = re.sub(r'[★\*°]', '', raw_code or '').strip()
        name = html.unescape((raw_name or '').strip())
        points = 1
        if points_payload:
            digits = re.search(r'(\d+)', points_payload)
            if digits:
                points = int(digits.group(1))
        problems.append(ProblemSummary(code=code, name=name, points=points))
    return problems


def _latest_ok_runs(runs: Iterable[RunPayload]) -> dict[tuple[str, str], RunPayload]:
    latest: dict[tuple[str, str], RunPayload] = {}
    for run in runs:
        if run.status != 'OK':
            continue
        user = run.user
        problem = run.problem
        if not user or not problem:
            continue
        key = (user, problem)
        existing = latest.get(key)
        if existing is None or run.run_id > existing.run_id:
            latest[key] = run
    return latest


def _week_start(timestamp: datetime) -> datetime:
    monday = timestamp - timedelta(days=timestamp.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=UTC)


def _format_week(timestamp: datetime) -> str:
    return timestamp.date().isoformat()


def _collect_users(payloads: Sequence[TopicPayload]) -> list[str]:
    users: set[str] = set()
    for payload in payloads:
        for run in payload.runs:
            if run.user:
                users.add(run.user)
    return sorted(users)


def _build_topic_report(
    payload: TopicPayload,
    users: Sequence[str],
    summary: dict[str, dict[str, SummaryCell]],
    all_ok_runs: list[RunPayload],
) -> TopicReport:
    solved_map = defaultdict(set)
    latest = _latest_ok_runs(payload.runs)
    for run in latest.values():
        solved_map[run.user].add(run.problem)
        all_ok_runs.append(run)

    rows: list[TopicUserRow] = []
    for user in users:
        solved_flags: list[bool] = []
        solved_count = 0
        score = 0
        solved_codes = solved_map.get(user, set())
        for problem in payload.problems:
            solved = problem.code in solved_codes
            solved_flags.append(solved)
            if solved:
                solved_count += 1
                score += problem.points
        rows.append(TopicUserRow(user=user, solved=solved_flags, solved_count=solved_count, score=score))
        summary[user][payload.config.title] = SummaryCell(solved=solved_count, score=score)

    return TopicReport(name=payload.config.title, problems=payload.problems, rows=rows)


def _build_weekly_summary(all_ok_runs: Sequence[RunPayload], users: Sequence[str]) -> WeeklySummary:
    week_candidates = [_week_start(run.timestamp) for run in all_ok_runs if run.timestamp is not None]
    if not week_candidates:
        return WeeklySummary(weeks=[], data={user: {} for user in users})

    min_week = min(week_candidates)
    max_week = max(week_candidates)
    week_headers: list[str] = []
    current = min_week
    while current <= max_week:
        week_headers.append(_format_week(current))
        current += timedelta(days=7)

    weekly_data: dict[str, dict[str, int]] = {user: {week: 0 for week in week_headers} for user in users}
    for run in all_ok_runs:
        if run.timestamp is None:
            continue
        week = _format_week(_week_start(run.timestamp))
        user_data = weekly_data.setdefault(run.user, {week_name: 0 for week_name in week_headers})
        user_data[week] = user_data.get(week, 0) + 1

    return WeeklySummary(weeks=week_headers, data=weekly_data)


def _build_topics_report(payloads: Sequence[TopicPayload]) -> ReportsResponse:
    users = _collect_users(payloads)
    summary: dict[str, dict[str, SummaryCell]] = {user: {} for user in users}
    all_ok_runs: list[RunPayload] = []

    topic_reports = [_build_topic_report(payload, users, summary, all_ok_runs) for payload in payloads]

    weekly_summary = _build_weekly_summary(all_ok_runs, users)

    return ReportsResponse(users=users, topics=topic_reports, summary=summary, weekly=weekly_summary)


async def _fetch_runs_for_topic(client: EjudgeClient, topic: TopicConfig) -> list[RunPayload]:
    requests = [
        client.master.list_runs_json(
            contest_id=contest_id,
            filter_expr='status==OK or status==PR',
            first_run=0,
            last_run=9999,
        )
        for contest_id in topic.contest_ids
    ]
    payloads = await asyncio.gather(*requests)

    runs: list[RunPayload] = []
    for payload in payloads:
        if not isinstance(payload, Mapping) or not payload.get('ok'):
            msg = payload.get('error') if isinstance(payload, Mapping) else 'Invalid ejudge payload.'
            raise ReportBuildError(str(msg or 'Unknown ejudge error'))
        result = payload.get('result')
        if not isinstance(result, Mapping):
            continue
        for run in result.get('runs', []):
            if isinstance(run, Mapping):
                runs.append(RunPayload(run))
    return runs


async def _fetch_topic_payload(
    http_client: httpx.AsyncClient,
    ejudge_client: EjudgeClient,
    topic: TopicConfig,
) -> TopicPayload:
    problems_task = http_client.get(topic.problems_url)
    runs_task = _fetch_runs_for_topic(ejudge_client, topic)

    try:
        response, runs = await asyncio.gather(problems_task, runs_task)
    except (httpx.HTTPError, EjudgeClientError, EjudgeReplyError) as exc:
        msg = f'Failed to fetch data for topic {topic.title}: {exc}'
        raise ReportBuildError(msg) from exc

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        msg = f'Failed to load problems for topic {topic.title}: {exc.response.status_code}'
        raise ReportBuildError(msg) from exc
    problems = parse_problems(response.text)
    return TopicPayload(config=topic, problems=problems, runs=runs)


async def build_reports() -> ReportsResponse:
    topics = load_topics()
    if not topics:
        raise ReportBuildError('No ejudge topics configured.')

    if settings.e2e:
        from backend.app.report_samples import build_sample_report

        return build_sample_report()

    if not settings.ejudge_origin or not settings.ejudge_token:
        raise ReportBuildError('Ejudge integration is not configured.')

    base_url = settings.ejudge_origin.rstrip('/')
    timeout = httpx.Timeout(20.0)
    async with (
        httpx.AsyncClient(timeout=timeout) as http_client,
        EjudgeClient(
            base_url,
            settings.ejudge_token,
        ) as ejudge_client,
    ):
        payloads = await asyncio.gather(*[_fetch_topic_payload(http_client, ejudge_client, topic) for topic in topics])

    return _build_topics_report(payloads)


__all__ = [
    'ProblemSummary',
    'ReportBuildError',
    'ReportsResponse',
    'TopicReport',
    'TopicUserRow',
    'WeeklySummary',
    'build_reports',
    'parse_problems',
]
