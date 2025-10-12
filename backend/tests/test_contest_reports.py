from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from test_app import _bearer, _register

from backend.app.contest_reports import get_ejudge_client
from backend.app.database import engine
from backend.db import ContestReportConfig
from backend.main import app


class _FakeMaster:
    def __init__(self, payloads: dict[int, dict[str, Any]]) -> None:
        self._payloads = payloads

    async def contest_status_json(self, *, contest_id: int) -> dict[str, Any]:
        return self._payloads[contest_id]['status']

    async def list_runs_json(self, *, contest_id: int, first_run: int = 0, **_: Any) -> dict[str, Any]:
        assert first_run == 0
        return self._payloads[contest_id]['runs']


class _FakeClient:
    def __init__(self, payloads: dict[int, dict[str, Any]]) -> None:
        self.master = _FakeMaster(payloads)

    async def aclose(self) -> None:  # pragma: no cover - required for compatibility
        return None


@pytest.fixture()
def ejudge_override() -> AsyncIterator[None]:
    sample_payloads: dict[int, dict[str, Any]] = {
        301: {
            'status': {
                'ok': True,
                'result': {
                    'contest': {'id': 301, 'name': 'Demo Contest'},
                    'problems': [
                        {'id': 1, 'short_name': 'A', 'long_name': 'Alpha'},
                        {'id': 2, 'short_name': 'B', 'long_name': 'Beta'},
                    ],
                },
            },
            'runs': {
                'ok': True,
                'result': {
                    'runs': [
                        {
                            'run_id': 10,
                            'prob_id': 1,
                            'status_str': 'OK',
                            'user_id': 100,
                            'user_login': 'alice',
                            'user_name': 'Alice',
                            'lang_name': 'Python',
                            'last_change_us': 1_000_000,
                        },
                        {
                            'run_id': 11,
                            'prob_id': 2,
                            'status_str': 'PR',
                            'user_id': 100,
                            'user_login': 'alice',
                            'user_name': 'Alice',
                            'lang_name': 'C++',
                            'last_change_us': 2_000_000,
                        },
                        {
                            'run_id': 12,
                            'prob_id': 1,
                            'status_str': 'WA',
                            'user_id': 101,
                            'user_login': 'bob',
                            'user_name': 'Bob',
                            'lang_name': 'Python',
                            'last_change_us': 3_000_000,
                        },
                    ]
                },
            },
        }
    }

    async def _fake_client() -> AsyncIterator[_FakeClient]:
        yield _FakeClient(sample_payloads)

    app.dependency_overrides[get_ejudge_client] = _fake_client
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_ejudge_client, None)


def test_contest_config_defaults_to_empty(client) -> None:
    tokens = _register(client, 'report@example.com', 'pw')
    access = tokens['access_token']

    response = client.get('/private/contest-config', headers=_bearer(access))
    assert response.status_code == 200
    assert response.json() == {'contest_ids': []}


def test_contest_config_recovers_if_table_missing(client) -> None:
    tokens = _register(client, 'missing-table@example.com', 'pw')
    access = tokens['access_token']

    async def _drop_table() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(ContestReportConfig.__table__.drop, checkfirst=True)

    asyncio.run(_drop_table())

    response = client.get('/private/contest-config', headers=_bearer(access))
    assert response.status_code == 200
    assert response.json() == {'contest_ids': []}


def test_update_contest_config_sorts_and_deduplicates(client) -> None:
    tokens = _register(client, 'config@example.com', 'pw')
    access = tokens['access_token']

    response = client.put(
        '/private/contest-config',
        headers=_bearer(access),
        json={'contest_ids': [302, 301, 302]},
    )
    assert response.status_code == 200
    assert response.json() == {'contest_ids': [301, 302]}

    follow_up = client.get('/private/contest-config', headers=_bearer(access))
    assert follow_up.status_code == 200
    assert follow_up.json() == {'contest_ids': [301, 302]}


def test_contest_reports_return_highlighted_runs(client, ejudge_override) -> None:
    tokens = _register(client, 'reports@example.com', 'pw')
    access = tokens['access_token']

    save = client.put(
        '/private/contest-config',
        headers=_bearer(access),
        json={'contest_ids': [301]},
    )
    assert save.status_code == 200

    response = client.get('/private/contest-reports', headers=_bearer(access))
    assert response.status_code == 200
    payload = response.json()

    contests = payload['contests']
    assert len(contests) == 1
    contest = contests[0]
    assert contest['contest_id'] == 301
    assert contest['contest_name'] == 'Demo Contest'
    assert [problem['short_name'] for problem in contest['problems']] == ['A', 'B']

    rows = contest['rows']
    assert [row['user_login'] for row in rows] == ['alice', 'bob']

    alice = rows[0]
    cell_a = alice['cells'][0]['best_run']
    assert cell_a['status'] == 'OK'
    assert cell_a['language'] == 'Python'
    submitted = cell_a['submitted_at']
    assert isinstance(submitted, str)
    parsed_submitted = datetime.fromisoformat(submitted.replace('Z', '+00:00'))
    assert parsed_submitted == datetime(1970, 1, 1, 0, 0, 1, tzinfo=UTC)

    cell_b = alice['cells'][1]['best_run']
    assert cell_b['status'] == 'PR'
    assert cell_b['language'] == 'C++'

    bob = rows[1]
    assert all(cell['best_run'] is None for cell in bob['cells'])
