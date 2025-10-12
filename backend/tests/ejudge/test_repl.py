from __future__ import annotations

import httpx
import pytest

from backend.ejudge import (
    GetUserRequest,
    SubmitRunRequest,
    SyncEjudgeClient,
    build_repl_namespace,
    create_mock_transport,
    make_get_user_reply,
    make_submit_run_reply,
)


def test_sync_submit_run_roundtrip() -> None:
    reply = make_submit_run_reply(run_id=777)
    transport, calls = create_mock_transport(submit_run=reply)

    client = SyncEjudgeClient('https://ejudge.local', 'token', transport=transport)
    try:
        request = SubmitRunRequest(
            contest_id=7,
            problem=5,
            lang_id='py3',
            text_form='print("hello")',
        )
        result = client.submit_run(request)
    finally:
        client.close()

    assert result == reply
    assert len(calls) == 1
    call = calls[0]
    assert call.url.path == '/ej/api/v1/master/submit-run'


def test_sync_master_operation_auto_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == '/ej/api/v1/master/list-runs-json'
        assert request.method == 'GET'
        assert request.url.params['contest_id'] == '1'
        assert request.url.params['first_run'] == '0'
        body = {'ok': True, 'result': {'runs': []}}
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)

    with SyncEjudgeClient('https://ejudge.local', 'token', transport=transport, auto_open=False) as client:
        payload = client.master.list_runs_json(contest_id=1, first_run=0)

    assert payload == {'ok': True, 'result': {'runs': []}}


def test_sync_close_blocks_operations() -> None:
    transport, _ = create_mock_transport(get_user=make_get_user_reply())
    client = SyncEjudgeClient('https://ejudge.local', 'token', transport=transport)
    client.close()

    request = GetUserRequest(contest_id=1, other_user_login='john')
    with pytest.raises(RuntimeError):
        client.get_user(request)
    with pytest.raises(RuntimeError):
        _ = client.master


def test_build_repl_namespace_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('EJUDGE_ORIGIN', 'https://ejudge.local')
    monkeypatch.setenv('EJUDGE_TOKEN', 'secret')

    captured: dict[str, object] = {}

    def factory(base_url: str, api_token: str, **kwargs: object) -> object:
        captured['base_url'] = base_url
        captured['api_token'] = api_token
        captured['kwargs'] = kwargs
        return 'client'

    namespace = build_repl_namespace(client_factory=factory, transport='mock-transport')

    assert namespace['client'] == 'client'
    assert captured == {
        'base_url': 'https://ejudge.local',
        'api_token': 'secret',
        'kwargs': {'transport': 'mock-transport'},
    }


def test_build_repl_namespace_skips_client_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('EJUDGE_ORIGIN', raising=False)
    monkeypatch.delenv('EJUDGE_TOKEN', raising=False)

    namespace = build_repl_namespace()

    assert 'client' not in namespace
