"""Async HTTP client wrappers around the ejudge API.

The module exposes :class:`EjudgeClient` - a thin but fully typed facade that
translates our Pydantic request models into ``httpx`` calls and validates the
JSON replies documented in ``backend/ejudge/doc.json``.  It intentionally
keeps the I/O surface extremely small (one POST endpoint and two GET
endpoints) so that service code can reason about ejudge interactions without
sprinkling low-level HTTP glue everywhere.

The helpers defined here are deliberately chatty in their docstrings to serve
as inline documentation for future autonomous agents.  When the integration
grows beyond a single file, these notes should migrate to ``ARCHITECTURE.md``.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from pydantic import ValidationError

from .models import (
    EjudgeError,
    EjudgeReply,
    GetSubmitReply,
    GetSubmitRequest,
    GetUserReply,
    GetUserRequest,
    SubmitRunInputReply,
    SubmitRunInputRequest,
    SubmitRunReply,
    SubmitRunRequest,
)

ReplyT = TypeVar('ReplyT', bound=EjudgeReply[Any])


class EjudgeClientError(RuntimeError):
    """Base error raised for transport or validation failures."""


class EjudgeReplyError(EjudgeClientError):
    """Wrap an ``ok = false`` ejudge reply to provide better context upstream."""

    def __init__(self, reply: EjudgeReply[Any]):
        self.reply = reply
        error = reply.error or EjudgeError(num=-1, symbol='unknown', message='No error payload provided by ejudge.')
        message = f'ejudge reported error {error.symbol} ({error.num}): {error.message or "no message"}'
        super().__init__(message)


@dataclass(slots=True)
class _FormPayload:
    """Internal representation of multipart/x-www-form-urlencoded payloads."""

    data: MutableMapping[str, str]
    files: MutableMapping[str, tuple[str, bytes | str]]


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return '1' if value else '0'
    return str(value)


def _prepare_submit_run_payload(request: SubmitRunRequest) -> _FormPayload:
    payload = request.model_dump(mode='json', by_alias=True, exclude_none=True)
    payload.pop('action', None)

    data: MutableMapping[str, str] = {}
    files: MutableMapping[str, tuple[str, bytes | str]] = {}

    source_bytes = payload.pop('file', None)
    source_text = payload.pop('text_form', None)
    if source_bytes is not None:
        files['file'] = ('solution', source_bytes)
    if source_text is not None:
        data['text_form'] = source_text

    for key, value in payload.items():
        data[key] = _stringify(value)

    return _FormPayload(data=data, files=files)


def _prepare_submit_run_input_payload(request: SubmitRunInputRequest) -> _FormPayload:
    payload = request.model_dump(mode='json', by_alias=True, exclude_none=True)
    payload.pop('action', None)

    data: MutableMapping[str, str] = {}
    files: MutableMapping[str, tuple[str, bytes | str]] = {}

    source_bytes = payload.pop('file', None)
    source_text = payload.pop('text_form', None)
    if source_bytes is not None:
        files['file'] = ('solution', source_bytes)
    if source_text is not None:
        data['text_form'] = source_text

    stdin_bytes = payload.pop('file_input', None)
    stdin_text = payload.pop('text_form_input', None)
    if stdin_bytes is not None:
        files['file_input'] = ('stdin', stdin_bytes)
    if stdin_text is not None:
        data['text_form_input'] = stdin_text

    for key, value in payload.items():
        data[key] = _stringify(value)

    return _FormPayload(data=data, files=files)


class EjudgeClient:
    """High-level helper for calling the subset of ejudge HTTP API we rely on."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        endpoint: str = '',
        timeout: float | httpx.Timeout | None = 10.0,
        transport: httpx.BaseTransport | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is not None and transport is not None:
            msg = 'Pass either `transport` or a pre-configured `http_client`, not both.'
            raise ValueError(msg)

        self._authorization = f'Bearer AQAA{api_token}'
        self._endpoint = endpoint
        self._own_client = http_client is None
        if http_client is None:
            self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)
        else:
            self._client = http_client

    async def __aenter__(self) -> EjudgeClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._own_client:
            await self._client.aclose()

    # -- Public API -----------------------------------------------------

    async def submit_run(self, request: SubmitRunRequest) -> SubmitRunReply:
        payload = _prepare_submit_run_payload(request)
        response = await self._request('POST', request.action, data=payload.data, files=payload.files)
        return self._parse_reply(response, SubmitRunReply)

    async def submit_run_input(self, request: SubmitRunInputRequest) -> SubmitRunInputReply:
        payload = _prepare_submit_run_input_payload(request)
        response = await self._request('POST', request.action, data=payload.data, files=payload.files)
        return self._parse_reply(response, SubmitRunInputReply)

    async def get_submit(self, request: GetSubmitRequest) -> GetSubmitReply:
        params = request.model_dump(mode='json', by_alias=True, exclude_none=True)
        return self._parse_reply(await self._request('GET', request.action, params=params), GetSubmitReply)

    async def get_user(self, request: GetUserRequest) -> GetUserReply:
        params = request.model_dump(mode='json', by_alias=True, exclude_none=True)
        return self._parse_reply(await self._request('GET', request.action, params=params), GetUserReply)

    # -- Internal helpers -----------------------------------------------

    async def _request(
        self,
        method: str,
        action: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, bytes | str]] | None = None,
    ) -> httpx.Response:
        request_params = {'json': '1', 'action': action}
        if params:
            request_params.update({key: _stringify(value) for key, value in params.items() if value is not None})

        headers = {'Authorization': self._authorization}

        try:
            response = await self._client.request(
                method,
                self._endpoint,
                params=request_params,
                data=data,
                files=files if files else None,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            msg = f'ejudge returned unexpected HTTP status {exc.response.status_code} for action {action!r}'
            raise EjudgeClientError(msg) from exc
        except httpx.HTTPError as exc:  # Network / protocol problems
            msg = f'Error communicating with ejudge while performing action {action!r}'
            raise EjudgeClientError(msg) from exc

        return response

    def _parse_reply(self, response: httpx.Response, model: type[ReplyT]) -> ReplyT:
        try:
            payload = response.json()
        except ValueError as exc:
            msg = 'ejudge response did not contain valid JSON payload.'
            raise EjudgeClientError(msg) from exc

        try:
            parsed = model.model_validate(payload)
        except ValidationError as exc:
            msg = f'Unable to validate ejudge response as {model.__name__}.'
            raise EjudgeClientError(msg) from exc

        if not parsed.ok:
            raise EjudgeReplyError(parsed)

        return parsed


__all__ = ['EjudgeClient', 'EjudgeClientError', 'EjudgeReplyError']
