"""Synchronous helpers for exploring the ejudge HTTP API from a REPL."""

from __future__ import annotations

import asyncio
import code
import os
from collections.abc import Awaitable, Callable
from textwrap import dedent
from typing import Any, TypeVar

import httpx

from .client import EjudgeClient, EjudgeClientError, EjudgeReplyError
from .models import (
    GetSubmitRequest,
    GetUserRequest,
    SubmitRunInputRequest,
    SubmitRunRequest,
)

_T = TypeVar('_T')


class _SyncNamespace:
    """Expose async ejudge operations as blocking callables."""

    def __init__(self, caller: Callable[..., Any], namespace: Any) -> None:
        self._caller = caller
        for name, attr in vars(namespace).items():
            if name.startswith('_') or not callable(attr):
                continue
            setattr(self, name, self._wrap(attr))

    def _wrap(self, async_callable: Callable[..., Awaitable[Any]]) -> Callable[..., Any]:
        def method(**kwargs: Any) -> Any:
            return self._caller(async_callable, **kwargs)

        method.__name__ = getattr(async_callable, '__name__', 'ejudge_call')
        if async_callable.__doc__:
            method.__doc__ = async_callable.__doc__
        return method


class SyncEjudgeClient:
    """Synchronous façade that drives :class:`EjudgeClient` behind the scenes."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        timeout: float | httpx.Timeout | None = 10.0,
        transport: httpx.BaseTransport | None = None,
        http_client: httpx.AsyncClient | None = None,
        auto_open: bool = True,
    ) -> None:
        self._client = EjudgeClient(
            base_url,
            api_token,
            timeout=timeout,
            transport=transport,
            http_client=http_client,
        )
        self._runner: asyncio.Runner | None = None
        self._client_namespace: _SyncNamespace | None = None
        self._master_namespace: _SyncNamespace | None = None
        if auto_open:
            self.open()

    def __enter__(self) -> SyncEjudgeClient:
        if not self.is_open:
            self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def is_open(self) -> bool:
        return self._runner is not None

    def open(self) -> None:
        if self._runner is not None:
            return
        runner = asyncio.Runner()
        self._runner = runner
        runner.run(self._client.__aenter__())
        self._client_namespace = _SyncNamespace(self._call_coroutine, self._client.client)
        self._master_namespace = _SyncNamespace(self._call_coroutine, self._client.master)

    def close(self) -> None:
        runner = self._runner
        if runner is None:
            return
        try:
            runner.run(self._client.aclose())
        finally:
            runner.close()
            self._runner = None
            self._client_namespace = None
            self._master_namespace = None

    def submit_run(self, request: SubmitRunRequest) -> Any:
        return self._call_coroutine(self._client.submit_run, request)

    def submit_run_input(self, request: SubmitRunInputRequest) -> Any:
        return self._call_coroutine(self._client.submit_run_input, request)

    def get_submit(self, request: GetSubmitRequest) -> Any:
        return self._call_coroutine(self._client.get_submit, request)

    def get_user(self, request: GetUserRequest) -> Any:
        return self._call_coroutine(self._client.get_user, request)

    @property
    def client(self) -> _SyncNamespace:
        if self._client_namespace is None:
            msg = 'SyncEjudgeClient is not open; call open() first.'
            raise RuntimeError(msg)
        return self._client_namespace

    @property
    def master(self) -> _SyncNamespace:
        if self._master_namespace is None:
            msg = 'SyncEjudgeClient is not open; call open() first.'
            raise RuntimeError(msg)
        return self._master_namespace

    def _call_coroutine(self, async_callable: Callable[..., Awaitable[_T]], /, *args: Any, **kwargs: Any) -> _T:
        runner = self._runner
        if runner is None:
            msg = 'SyncEjudgeClient is not open; call open() first.'
            raise RuntimeError(msg)
        return runner.run(async_callable(*args, **kwargs))


def build_repl_namespace(
    *,
    client_factory: Callable[..., SyncEjudgeClient] = SyncEjudgeClient,
    **client_kwargs: Any,
) -> dict[str, Any]:
    """Compose the globals dictionary fed into :func:`code.interact`."""

    namespace: dict[str, Any] = {
        'SyncEjudgeClient': SyncEjudgeClient,
        'EjudgeClientError': EjudgeClientError,
        'EjudgeReplyError': EjudgeReplyError,
        'SubmitRunRequest': SubmitRunRequest,
        'SubmitRunInputRequest': SubmitRunInputRequest,
        'GetSubmitRequest': GetSubmitRequest,
        'GetUserRequest': GetUserRequest,
    }

    origin = os.environ.get('EJUDGE_ORIGIN')
    token = os.environ.get('EJUDGE_TOKEN')
    if origin and token:
        namespace['client'] = client_factory(origin, token, **client_kwargs)
    return namespace


def main() -> None:
    """Launch an interactive console primed with ejudge helpers."""

    namespace = build_repl_namespace()
    origin = os.environ.get('EJUDGE_ORIGIN', '<unset>')
    token_hint = 'set' if os.environ.get('EJUDGE_TOKEN') else 'unset'
    banner = dedent(
        f"""
        ejudge REPL helpers
        -------------------
        EJUDGE_ORIGIN: {origin}
        EJUDGE_TOKEN: {token_hint}

        Objects in scope:
          - SyncEjudgeClient (class)
          - EjudgeClientError / EjudgeReplyError
          - SubmitRunRequest / SubmitRunInputRequest / GetSubmitRequest / GetUserRequest
          - client (pre-connected instance) if EJUDGE_* env vars are provided
        """,
    )
    code.interact(banner=banner, local=namespace)


if __name__ == '__main__':  # pragma: no cover - CLI escape hatch
    main()
