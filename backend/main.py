from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import jwt
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from backend.db import Base, Item, User  # <- import models from lightweight module

load_dotenv('../.env')

# ---- settings ----
SECRET_KEY = os.getenv('SECRET_KEY', 'devsecret')
ALGORITHM = os.getenv('ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 120))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv('REFRESH_TOKEN_EXPIRE_MINUTES', 60 * 24 * 90))
BASE_DIR = os.path.dirname(__file__)
DEFAULT_DB_PATH = os.path.join(BASE_DIR, 'ejapp.db')
FRONTEND_ORIGIN = os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')
E2E = os.getenv('E2E') == '1'
if E2E:
    E2E_DB_DIR = os.path.join(BASE_DIR, '.e2e-db')
    os.makedirs(E2E_DB_DIR, exist_ok=True)
    E2E_DB_PATH = os.path.join(E2E_DB_DIR, 'ejapp_e2e.db')
    if os.path.exists(E2E_DB_PATH):
        os.remove(E2E_DB_PATH)
    DATABASE_URL = f'sqlite+aiosqlite:///{E2E_DB_PATH}'
    FRONTEND_ORIGIN = 'http://localhost:63343'
else:
    DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite+aiosqlite:///{DEFAULT_DB_PATH}')


async def lifespan(app: FastAPI):
    # For e2e we want a clean DB each time
    if E2E:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield


base_origin = FRONTEND_ORIGIN.rstrip('/')
aliases_origins = {
    base_origin,
    base_origin.replace('localhost', '127.0.0.1'),
    base_origin.replace('127.0.0.1', 'localhost'),
}
app = FastAPI(title='ejapp API', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(aliases_origins),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ---- DB models and session ----
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# ---- auth helpers ----
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(pw: str) -> str:
    return pwd_context.hash(pw)


def create_access_token(data: dict, expires: timedelta | None = None) -> str:
    to_encode = data.copy()
    exp = datetime.now(tz=UTC) + (expires or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode['exp'] = exp
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    exp = datetime.now(tz=UTC) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode = {'exp': exp, **data}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalars().first()


# ---- pydantic schemas ----
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class UserCreate(BaseModel):
    email: str
    password: str


class ItemCreate(BaseModel):
    title: str


@app.get('/healthz', include_in_schema=False)
async def healthz():
    return {'status': 'ok'}


# ---- routes (now safe: app is defined) ----
@app.post('/auth/register', response_model=Token)
async def register_user(user_in: UserCreate):
    async with AsyncSessionLocal() as session:
        existing = await get_user_by_email(session, user_in.email)
        if existing:
            raise HTTPException(status_code=400, detail='Email already registered')
        user = User(email=user_in.email, hashed_password=get_password_hash(user_in.password))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        payload = {'sub': user.email}
        return {
            'access_token': create_access_token(payload),
            'refresh_token': create_refresh_token(payload),
            'token_type': 'bearer',
        }


@app.post('/auth/login', response_model=Token)
async def login_user(email: str = Body(...), password: str = Body(...)):
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail='Invalid credentials')
        payload = {'sub': user.email}
        return {
            'access_token': create_access_token(payload),
            'refresh_token': create_refresh_token(payload),
            'token_type': 'bearer',
        }


@app.post('/auth/refresh', response_model=Token)
async def refresh_access_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail='Refresh token expired') from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail='Invalid refresh token') from exc
    sub = payload.get('sub')
    if not sub:
        raise HTTPException(status_code=401, detail='Invalid token payload')
    return {
        'access_token': create_access_token({'sub': sub}),
        'refresh_token': create_refresh_token({'sub': sub}),
        'token_type': 'bearer',
    }


@app.get('/auth/google/callback', response_model=Token)
async def google_callback(code: str):
    google_email = 'googleuser@example.com'
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, google_email)
        if not user:
            user = User(email=google_email, hashed_password=get_password_hash(os.urandom(8).hex()))
            session.add(user)
            await session.commit()
            await session.refresh(user)
        payload = {'sub': user.email}
        return {
            'access_token': create_access_token(payload),
            'refresh_token': create_refresh_token(payload),
            'token_type': 'bearer',
        }


@app.get('/items')
async def read_items(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail='Not authenticated') from exc
    email = payload.get('sub')
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, email)
        if not user:
            raise HTTPException(status_code=401, detail='User not found')
        result = await session.execute(select(Item.title).where(Item.owner_id == user.id))
        return [{'title': t} for t in result.scalars().all()]


@app.post('/items')
async def create_item(item: ItemCreate, token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail='Not authenticated') from exc
    email = payload.get('sub')
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, email)
        if not user:
            raise HTTPException(status_code=401, detail='User not found')
        it = Item(title=item.title, owner_id=user.id)
        session.add(it)
        await session.commit()
        return {'id': it.id, 'title': it.title}
