from __future__ import annotations

import httpx

from backend.ejudge import (
    EjudgeSyncClient,
    SubmitRunReply,
    SubmitRunRequest,
    create_mock_transport,
    make_submit_run_reply,
)


def test_master_namespace_exposes_sync_operations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == 'GET'
        assert request.url.path == '/ej/api/v1/master/list-runs-json'
        assert request.headers['Authorization'] == 'Bearer AQAAtoken'
        assert request.url.params['contest_id'] == '302'
        assert request.url.params['first_run'] == '0'
        assert request.url.params['last_run'] == '5'
        payload = {
            'ok': True,
            'result': {
                'runs': [],
                'first_run': 0,
                'last_run': 5,
            },
        }
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)

    with EjudgeSyncClient('https://ejudge.local', 'token', transport=transport, http2=False) as client:
        payload = client.master.list_runs_json(contest_id=302, first_run=0, last_run=5)

    assert payload['ok'] is True
    assert payload['result']['runs'] == []


def test_typed_wrappers_run_synchronously() -> None:
    reply = make_submit_run_reply(run_id=77)
    transport, calls = create_mock_transport(submit_run=reply)

    with EjudgeSyncClient('https://ejudge.local', 'secrettoken', transport=transport, http2=False) as client:
        request = SubmitRunRequest(contest_id=9, problem=1, lang_id='py3', text_form='print(42)')
        result = client.submit_run(request)

    assert isinstance(result, SubmitRunReply)
    assert result.result.run_id == 77
    assert len(calls) == 1
    call = calls[0]
    assert call.headers['Authorization'] == 'Bearer AQAAsecrettoken'


def test_close_is_idempotent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='<ok/>')

    client = EjudgeSyncClient('https://ejudge.local', 'token', transport=httpx.MockTransport(handler), http2=False)

    try:
        client.master.raw_report(contest_id=1, run_id=2)
    finally:
        client.close()
        client.close()
