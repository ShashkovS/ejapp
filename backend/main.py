from __future__ import annotations

from backend.app import create_app, engine

app = create_app()

__all__ = ['app', 'engine']
