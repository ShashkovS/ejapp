from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from jwt import PyJWTError

from backend.app import auth
from backend.app.config import settings
from backend.app.database import engine
from backend.app.items import private_router, router as items_router
from backend.db import Base

PROTECTED_PREFIXES = settings.private_path_prefixes


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.e2e:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        await engine.dispose()


def _register_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )


def _register_private_middleware(app: FastAPI) -> None:
    @app.middleware('http')
    async def _guard_private(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path.startswith(PROTECTED_PREFIXES):
            auth_header = request.headers.get('authorization')
            if not auth_header or not auth_header.lower().startswith('bearer '):
                return JSONResponse(status_code=401, content={'detail': 'Not authenticated'})
            token = auth_header.split(' ', 1)[1].strip()
            if not token:
                return JSONResponse(status_code=401, content={'detail': 'Not authenticated'})
            try:
                payload = auth.decode_token(token)
            except PyJWTError:
                return JSONResponse(status_code=401, content={'detail': 'Not authenticated'})
            if 'sub' not in payload:
                return JSONResponse(status_code=401, content={'detail': 'Invalid token payload'})
        return await call_next(request)


def create_app() -> FastAPI:
    application = FastAPI(title='ejapp API', lifespan=lifespan)
    _register_cors(application)
    _register_private_middleware(application)

    application.include_router(auth.router)
    application.include_router(items_router)
    application.include_router(private_router)
    return application


__all__ = ['create_app', 'engine']
