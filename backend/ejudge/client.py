"""Async access helpers for the public ejudge HTTP API."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from functools import cached_property
from importlib import resources
from typing import Any, TypedDict, TypeVar

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


class _ParameterSpec(TypedDict):
    name: str
    location: str
    required: bool
    type: str | None


@dataclass(slots=True, frozen=True)
class _EndpointSpec:
    """Runtime description of an ejudge endpoint loaded from the OpenAPI spec."""

    method: str
    path: str
    name: str
    description: str
    params: tuple[_ParameterSpec, ...]
    response_kind: str  # ``json`` | ``text`` | ``bytes``


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


def _load_operations() -> dict[str, dict[str, _EndpointSpec]]:
    doc_path = resources.files(__package__).joinpath('ejudge_doc.json')
    with doc_path.open('r', encoding='utf-8') as fh:
        spec = json.load(fh)

    operations: dict[str, dict[str, _EndpointSpec]] = {'client': {}, 'master': {}}

    for path, methods in spec['paths'].items():
        try:
            scope = path.split('/')[4]
        except IndexError as exc:  # pragma: no cover - sanity guard
            raise RuntimeError(f'Unable to determine ejudge scope for path {path!r}') from exc

        if scope not in operations:
            continue

        for method, payload in methods.items():
            name = path.rsplit('/', 1)[-1].replace('-', '_')
            produces: Iterable[str] = payload.get('produces') or ()
            responses = payload.get('responses', {})
            has_schema = any(response.get('schema') for response in responses.values())
            if produces:
                if any('json' in item for item in produces):
                    response_kind = 'json'
                elif any('text' in item for item in produces):
                    response_kind = 'text'
                else:
                    response_kind = 'bytes'
            elif has_schema:
                # Most endpoints declare JSON schema without ``produces``.
                response_kind = 'json'
            else:
                response_kind = 'text'

            params: list[_ParameterSpec] = []
            for parameter in payload.get('parameters', []):
                params.append(
                    {
                        'name': parameter['name'],
                        'location': parameter['in'],
                        'required': bool(parameter.get('required', False)),
                        'type': parameter.get('type'),
                    }
                )

            description = payload.get('summary') or payload.get('description') or ''

            operations[scope][name] = _EndpointSpec(
                method=method.upper(),
                path=path,
                name=name,
                description=description,
                params=tuple(params),
                response_kind=response_kind,
            )

    return operations


class _Namespace:
    """Call-through helper exposing operations as async methods."""

    def __init__(self, owner: EjudgeClient, operations: Mapping[str, _EndpointSpec]):
        self._owner = owner
        for spec in operations.values():
            setattr(self, spec.name, self._wrap(spec))

    def _wrap(self, spec: _EndpointSpec) -> Callable[..., Any]:
        async def method(**kwargs: Any) -> Any:
            return await self._owner._call_operation(spec, kwargs)

        method.__name__ = spec.name
        if spec.description:
            method.__doc__ = spec.description
        return method


class EjudgeClient:
    """High-level helper for calling the ejudge HTTP API documented in ``ejudge_doc.json``."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        timeout: float | httpx.Timeout | None = 10.0,
        transport: httpx.BaseTransport | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is not None and transport is not None:
            msg = 'Pass either `transport` or a pre-configured `http_client`, not both.'
            raise ValueError(msg)

        self._authorization = f'Bearer AQAA{api_token}'
        self._own_client = http_client is None
        if http_client is None:
            self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)
        else:
            self._client = http_client

        operations = self._operations
        self.client = _Namespace(self, operations['client'])
        self.master = _Namespace(self, operations['master'])

    async def __aenter__(self) -> EjudgeClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._own_client:
            await self._client.aclose()

    # -- Typed convenience wrappers -------------------------------------

    async def submit_run(self, request: SubmitRunRequest) -> SubmitRunReply:
        payload = _prepare_submit_run_payload(request)
        response = await self._request('POST', '/ej/api/v1/master/submit-run', data=payload.data, files=payload.files)
        return self._parse_reply(response, SubmitRunReply)

    async def submit_run_input(self, request: SubmitRunInputRequest) -> SubmitRunInputReply:
        payload = _prepare_submit_run_input_payload(request)
        response = await self._request(
            'POST',
            '/ej/api/v1/master/submit-run-input',
            data=payload.data,
            files=payload.files,
        )
        return self._parse_reply(response, SubmitRunInputReply)

    async def get_submit(self, request: GetSubmitRequest) -> GetSubmitReply:
        params = request.model_dump(mode='json', by_alias=True, exclude_none=True)
        response = await self._request('GET', '/ej/api/v1/master/get-submit', params=params)
        return self._parse_reply(response, GetSubmitReply)

    async def get_user(self, request: GetUserRequest) -> GetUserReply:
        params = request.model_dump(mode='json', by_alias=True, exclude_none=True)
        response = await self._request('GET', '/ej/api/v1/master/get-user', params=params)
        return self._parse_reply(response, GetUserReply)

    # -- Internal helpers -----------------------------------------------

    @cached_property
    def _operations(self) -> dict[str, dict[str, _EndpointSpec]]:
        return _load_operations()

    async def _call_operation(self, spec: _EndpointSpec, params: dict[str, Any]) -> Any:
        query, form, files = self._partition_parameters(spec, params)
        response = await self._request(spec.method, spec.path, params=query, data=form, files=files or None)
        if spec.response_kind == 'json':
            try:
                return response.json()
            except ValueError as exc:
                msg = f'ejudge response for {spec.name!r} was not valid JSON.'
                raise EjudgeClientError(msg) from exc
        if spec.response_kind == 'text':
            return response.text
        return response.content

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, tuple[str, bytes | str]] | None = None,
    ) -> httpx.Response:
        headers = {'Authorization': self._authorization}

        params_payload = {key: value for key, value in (params or {}).items() if value is not None}
        data_payload = {key: value for key, value in (data or {}).items() if value is not None}

        try:
            response = await self._client.request(
                method,
                path,
                params=params_payload or None,
                data=data_payload or None,
                files=files or None,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            msg = f'ejudge returned unexpected HTTP status {exc.response.status_code} for path {path!r}'
            raise EjudgeClientError(msg) from exc
        except httpx.HTTPError as exc:  # Network / protocol problems
            msg = f'Error communicating with ejudge while performing request to {path!r}'
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

    def _partition_parameters(
        self, spec: _EndpointSpec, raw_params: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, tuple[str, bytes | str]]]:
        params = dict(raw_params)
        query: dict[str, Any] = {}
        form: dict[str, Any] = {}
        files: dict[str, tuple[str, bytes | str]] = {}

        for param in spec.params:
            name = param['name']
            required = param['required']
            if name not in params:
                if required:
                    msg = f'Missing required parameter {name!r} for endpoint {spec.name!r}'
                    raise TypeError(msg)
                continue

            value = params.pop(name)
            if value is None:
                continue

            location = param['location']
            if param['type'] == 'file':
                files[name] = self._coerce_file_payload(name, value)
                continue

            serialized = self._coerce_scalar(value)
            if location == 'query' or (location == 'formData' and spec.method == 'GET'):
                query[name] = serialized
            elif location == 'formData':
                form[name] = serialized
            else:  # pragma: no cover - unsupported parameter location
                raise NotImplementedError(f'Unsupported parameter location {location!r} for {name!r}')

        if params:
            unexpected = ', '.join(sorted(params))
            msg = f'Unexpected parameters for endpoint {spec.name!r}: {unexpected}'
            raise TypeError(msg)

        return query, form, files

    @staticmethod
    def _coerce_file_payload(name: str, value: Any) -> tuple[str, bytes | str]:
        if isinstance(value, tuple) and len(value) >= 2:
            filename, content = value[0], value[1]
            return str(filename), content
        return name, value

    @staticmethod
    def _coerce_scalar(value: Any) -> Any:
        if isinstance(value, list | tuple):
            return [_stringify(item) for item in value]
        return _stringify(value)


__all__ = ['EjudgeClient', 'EjudgeClientError', 'EjudgeReplyError']
