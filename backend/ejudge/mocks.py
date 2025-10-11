"""Light-weight helpers to mock ejudge for unit tests."""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import httpx

from .models import (
    GetSubmitReply,
    GetUserReply,
    SubmitDetails,
    SubmitRunInputReply,
    SubmitRunInputResult,
    SubmitRunReply,
    SubmitRunResult,
    UserProfile,
)


@dataclass(slots=True)
class RecordedCall:
    """Simple container capturing an outgoing request for assertions."""

    method: str
    url: httpx.URL
    headers: httpx.Headers
    content: bytes


def _coerce_payload(value: Any) -> tuple[int, Mapping[str, Any]]:
    status_code = 200
    payload = value
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
        status_code, payload = value

    if hasattr(payload, 'model_dump_json'):
        data = json.loads(payload.model_dump_json(by_alias=True, exclude_none=True))
    elif isinstance(payload, Mapping):
        data = dict(payload)
    else:
        msg = 'Mock payloads must be Pydantic models, dicts or (status, payload) tuples.'
        raise TypeError(msg)

    return status_code, data


def create_mock_transport(
    *,
    submit_run: Any | None = None,
    submit_run_input: Any | None = None,
    get_submit: Any | None = None,
    get_user: Any | None = None,
) -> tuple[httpx.MockTransport, list[RecordedCall]]:
    """Create an :class:`httpx.MockTransport` returning canned ejudge replies."""

    responses: MutableMapping[tuple[str, str], tuple[int, Mapping[str, Any]]] = {}

    def register(method: str, path: str, payload: Any) -> None:
        responses[(method, path)] = _coerce_payload(payload)

    if submit_run is not None:
        register('POST', '/ej/api/v1/master/submit-run', submit_run)
    if submit_run_input is not None:
        register('POST', '/ej/api/v1/master/submit-run-input', submit_run_input)
    if get_submit is not None:
        register('GET', '/ej/api/v1/master/get-submit', get_submit)
    if get_user is not None:
        register('GET', '/ej/api/v1/master/get-user', get_user)

    calls: list[RecordedCall] = []

    def handler(request: httpx.Request) -> httpx.Response:
        content = request.content
        recorded = RecordedCall(method=request.method, url=request.url, headers=httpx.Headers(request.headers), content=content)
        calls.append(recorded)

        status_and_payload = responses.get((request.method, request.url.path))
        if status_and_payload is None:
            return httpx.Response(
                404,
                json={
                    'ok': False,
                    'error': {
                        'symbol': 'unhandled-path',
                        'message': f'{request.method} {request.url.path}',
                    },
                },
            )

        status_code, payload = status_and_payload
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler), calls


def make_submit_run_reply(*, run_id: int = 100, run_uuid: str | None = None) -> SubmitRunReply:
    return SubmitRunReply(ok=True, action='submit-run', result=SubmitRunResult(run_id=run_id, run_uuid=run_uuid))


def make_submit_run_input_reply(*, submit_id: int = 200) -> SubmitRunInputReply:
    return SubmitRunInputReply(ok=True, action='submit-run-input', result=SubmitRunInputResult(submit_id=submit_id))


def make_submit_details(*, submit_id: int = 300, status: int = 0, status_str: str = 'OK') -> SubmitDetails:
    return SubmitDetails(
        submit_id=submit_id,
        user_id=1,
        prob_id=1,
        lang_id=1,
        status=status,
        status_str=status_str,
        exit_code=0,
        term_signal=0,
    )


def make_get_submit_reply(details: SubmitDetails | None = None) -> GetSubmitReply:
    details = details or make_submit_details()
    return GetSubmitReply(ok=True, action='get-submit', result=details)


def make_user_profile(*, user_id: int = 1, user_login: str = 'user') -> UserProfile:
    return UserProfile(user_id=user_id, user_login=user_login)


def make_get_user_reply(profile: UserProfile | None = None) -> GetUserReply:
    profile = profile or make_user_profile()
    return GetUserReply(ok=True, action='get-user', result=profile)


__all__ = [
    'RecordedCall',
    'create_mock_transport',
    'make_get_submit_reply',
    'make_get_user_reply',
    'make_submit_details',
    'make_submit_run_input_reply',
    'make_submit_run_reply',
]
