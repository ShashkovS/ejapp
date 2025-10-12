"""Interactive helpers for exploring the ejudge HTTP API from a Python shell."""

from __future__ import annotations

import asyncio
import code
from collections.abc import Mapping
from functools import partial
from pprint import pprint
from textwrap import dedent
from typing import Any

import httpx

from backend.app.config import settings

from .client import EjudgeClient
from .models import (
    GetSubmitReply,
    GetSubmitRequest,
    GetUserReply,
    GetUserRequest,
    SubmitRunInputReply,
    SubmitRunInputRequest,
    SubmitRunReply,
    SubmitRunRequest,
)

print(f'{settings.ejudge_origin=}')


class _SyncNamespace:
    """Expose async ejudge operations as synchronous callables."""

    def __init__(self, owner: EjudgeSyncClient, operations: Mapping[str, Any]):
        self._owner = owner
        for spec in operations.values():
            setattr(self, spec.name, self._wrap(spec))

    def _wrap(self, spec: Any) -> Any:
        def call(**kwargs: Any) -> Any:
            return self._owner._run(self._owner._client._call_operation(spec, kwargs))

        call.__name__ = spec.name
        if spec.description:
            call.__doc__ = spec.description
        return call


class EjudgeSyncClient:
    """Synchronous façade around :class:`~backend.ejudge.client.EjudgeClient`."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        timeout: float | httpx.Timeout | None = 10.0,
        transport: httpx.BaseTransport | None = None,
        http2: bool = True,
    ) -> None:
        self._runner = asyncio.Runner()
        self._http_client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            http2=http2,
        )
        self._client = EjudgeClient(base_url, api_token, http_client=self._http_client)
        self._closed = False

        operations = self._client._operations
        self.client = _SyncNamespace(self, operations['client'])
        self.master = _SyncNamespace(self, operations['master'])

    def __enter__(self) -> EjudgeSyncClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return

        self._runner.run(self._client.aclose())
        self._runner.run(self._http_client.aclose())
        self._runner.close()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            msg = 'EjudgeSyncClient is closed.'
            raise RuntimeError(msg)

    def _run(self, awaitable: Any) -> Any:
        self._ensure_open()
        return self._runner.run(awaitable)

    # -- Typed convenience wrappers -------------------------------------

    def submit_run(self, request: SubmitRunRequest) -> SubmitRunReply:
        return self._run(self._client.submit_run(request))

    def submit_run_input(self, request: SubmitRunInputRequest) -> SubmitRunInputReply:
        return self._run(self._client.submit_run_input(request))

    def get_submit(self, request: GetSubmitRequest) -> GetSubmitReply:
        return self._run(self._client.get_submit(request))

    def get_user(self, request: GetUserRequest) -> GetUserReply:
        return self._run(self._client.get_user(request))


def _make_namespace(client: EjudgeSyncClient) -> dict[str, Any]:
    pretty = partial(pprint, width=160, sort_dicts=False)
    return {
        'ej': client,
        'EjudgeSyncClient': EjudgeSyncClient,
        'ej_client': client.master,
        'ej_master': client.master,
        'ej_service': client.client,
        'pp': pretty,
        'pretty': pretty,
        'pprint': pprint,
        'SubmitRunRequest': SubmitRunRequest,
        'SubmitRunInputRequest': SubmitRunInputRequest,
        'GetSubmitRequest': GetSubmitRequest,
        'GetUserRequest': GetUserRequest,
    }


def _make_banner(base_url: str) -> str:
    return dedent(
        f"""
        ejudge REPL connected to {base_url}

        Helpful names:
          • ej          - synchronous facade (EjudgeSyncClient)
          • ej_client   - /master namespace shortcuts (e.g. ej_client.list_runs_json(...))
          • pp          - pprint with sensible defaults
          • SubmitRunRequest, GetSubmitRequest, ... - typed payload helpers

        Press Ctrl-D (EOF) to exit the session.
        """
    ).strip()


def start_repl(*, base_url: str | None = None, api_token: str | None = None) -> None:
    base_url = settings.ejudge_origin
    api_token = settings.ejudge_token

    if not base_url or not api_token:
        msg = 'Set EJUDGE_ORIGIN and EJUDGE_TOKEN environment variables before launching the REPL.'
        raise RuntimeError(msg)

    with EjudgeSyncClient(base_url, api_token) as client:
        banner = _make_banner(base_url)
        namespace = _make_namespace(client)
        code.interact(banner=banner, local=namespace)


def main() -> int:
    try:
        start_repl()
    except RuntimeError as exc:
        print(exc)
        return 1
    except KeyboardInterrupt:
        print()
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

__all__ = ['EjudgeSyncClient', 'start_repl']
