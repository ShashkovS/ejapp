from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.ejudge import (
    EjudgeClient,
    EjudgeClientError,
    EjudgeReplyError,
    GetSubmitRequest,
    GetUserRequest,
    SubmitRunInputRequest,
    SubmitRunRequest,
    create_mock_transport,
    make_get_submit_reply,
    make_get_user_reply,
    make_submit_details,
    make_submit_run_input_reply,
    make_submit_run_reply,
)


def test_submit_run_text_payload() -> None:
    async def scenario() -> None:
        reply = make_submit_run_reply(run_id=42)
        transport, calls = create_mock_transport(submit_run=reply)

        async with EjudgeClient('https://ejudge.local/cgi-bin/master', 'token', transport=transport) as client:
            request = SubmitRunRequest(
                contest_id=7,
                problem=5,
                lang_id='py3',
                text_form='print("hello")',
                is_visible=True,
            )
            result = await client.submit_run(request)

        assert result == reply
        assert len(calls) == 1
        call = calls[0]
        assert call.headers['Authorization'] == 'Bearer AQAAtoken'
        assert call.url.params['json'] == '1'
        body = httpx.QueryParams(call.content.decode())
        assert body['contest_id'] == '7'
        assert body['lang_id'] == 'py3'
        assert body['problem'] == '5'
        assert body['is_visible'] == '1'
        assert body['text_form'] == 'print("hello")'

    asyncio.run(scenario())


def test_submit_run_binary_payload() -> None:
    async def scenario() -> None:
        reply = make_submit_run_reply(run_id=101)
        transport, calls = create_mock_transport(submit_run=reply)

        async with EjudgeClient('https://ejudge.local/cgi-bin/master', 'secrettoken', transport=transport) as client:
            request = SubmitRunRequest(
                contest_id=2,
                problem=3,
                language_name='cpp',
                file=b'int main(){}',
            )
            await client.submit_run(request)

        call = calls[0]
        assert 'multipart/form-data' in call.headers['content-type']
        assert b'int main(){}' in call.content

    asyncio.run(scenario())


def test_submit_run_input_text_payload() -> None:
    async def scenario() -> None:
        reply = make_submit_run_input_reply(submit_id=314)
        transport, calls = create_mock_transport(submit_run_input=reply)

        async with EjudgeClient('https://ejudge.local/cgi-bin/master', 'abc', transport=transport) as client:
            request = SubmitRunInputRequest(
                contest_id=9,
                prob_id='A',
                lang_id='py3',
                text_form='print("42")',
                text_form_input='1 2 3',
            )
            result = await client.submit_run_input(request)

        assert result == reply
        call = calls[0]
        body = httpx.QueryParams(call.content.decode())
        assert body['contest_id'] == '9'
        assert body['prob_id'] == 'A'
        assert body['lang_id'] == 'py3'
        assert body['text_form'] == 'print("42")'
        assert body['text_form_input'] == '1 2 3'

    asyncio.run(scenario())


def test_get_submit_roundtrip() -> None:
    async def scenario() -> None:
        details = make_submit_details(submit_id=555, status=1, status_str='WA')
        reply = make_get_submit_reply(details)
        transport, calls = create_mock_transport(get_submit=reply)

        async with EjudgeClient('https://ejudge.local/cgi-bin/master', 'zzz', transport=transport) as client:
            request = GetSubmitRequest(contest_id=1, submit_id=555)
            result = await client.get_submit(request)

        assert result == reply
        call = calls[0]
        assert call.url.params['contest_id'] == '1'
        assert call.url.params['submit_id'] == '555'

    asyncio.run(scenario())


def test_get_user_roundtrip() -> None:
    async def scenario() -> None:
        reply = make_get_user_reply()
        transport, calls = create_mock_transport(get_user=reply)

        async with EjudgeClient('https://ejudge.local/cgi-bin/master', 'ttt', transport=transport) as client:
            request = GetUserRequest(contest_id=4, other_user_login='john')
            result = await client.get_user(request)

        assert result == reply
        call = calls[0]
        assert call.url.params['other_user_login'] == 'john'
        assert call.url.params['contest_id'] == '4'

    asyncio.run(scenario())


def test_error_reply_raises() -> None:
    async def scenario() -> None:
        bad_reply = make_submit_run_reply(run_id=1).model_copy(update={'ok': False})
        transport, _ = create_mock_transport(submit_run=bad_reply)

        async with EjudgeClient('https://ejudge.local/cgi-bin/master', 'token', transport=transport) as client:
            request = SubmitRunRequest(contest_id=1, problem=1, lang_id='py', text_form='pass')
            with pytest.raises(EjudgeReplyError):
                await client.submit_run(request)

    asyncio.run(scenario())


def test_http_error_raises_client_error() -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={'detail': 'boom'})

        transport = httpx.MockTransport(handler)

        async with EjudgeClient('https://ejudge.local/cgi-bin/master', 'token', transport=transport) as client:
            request = GetSubmitRequest(contest_id=1, submit_id=10)
            with pytest.raises(EjudgeClientError):
                await client.get_submit(request)

    asyncio.run(scenario())
