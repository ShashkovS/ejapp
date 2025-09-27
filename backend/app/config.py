from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / '.env'
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)


@dataclass(slots=True)
class Settings:
    secret_key: str = field(default_factory=lambda: os.getenv('SECRET_KEY', 'devsecret'))
    algorithm: str = field(default_factory=lambda: os.getenv('ALGORITHM', 'HS256'))
    access_token_expire_minutes: int = field(default_factory=lambda: int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 120)))
    refresh_token_expire_minutes: int = field(default_factory=lambda: int(os.getenv('REFRESH_TOKEN_EXPIRE_MINUTES', 60 * 24 * 90)))
    frontend_origin: str = field(default_factory=lambda: os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173'))
    database_url: str = field(init=False)
    allowed_origins: list[str] = field(init=False)
    e2e: bool = field(default_factory=lambda: os.getenv('E2E') == '1')
    private_path_prefixes: tuple[str, ...] = ('/private',)

    _backend_dir: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._backend_dir = Path(__file__).resolve().parents[1]
        default_db_path = self._backend_dir / 'ejapp.db'

        if self.e2e:
            e2e_dir = self._backend_dir / '.e2e-db'
            e2e_dir.mkdir(exist_ok=True)
            e2e_db_path = e2e_dir / 'ejapp_e2e.db'
            if e2e_db_path.exists():
                e2e_db_path.unlink()
            self.database_url = f'sqlite+aiosqlite:///{e2e_db_path}'
            self.frontend_origin = 'http://localhost:63343'
        else:
            self.database_url = os.getenv('DATABASE_URL', f'sqlite+aiosqlite:///{default_db_path}')

        base_origin = self.frontend_origin.rstrip('/')
        aliases = {
            base_origin,
            base_origin.replace('localhost', '127.0.0.1'),
            base_origin.replace('127.0.0.1', 'localhost'),
        }
        self.allowed_origins = sorted(aliases)


settings = Settings()
