# backend/tests/test_app.py
from __future__ import annotations


def _bearer(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _register(client, email='alice@example.com', password='password123'):
    r = client.post('/auth/register', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'access_token' in data and 'refresh_token' in data
    assert data['token_type'] == 'bearer'
    return data


def test_healthz_ok(client):
    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json() == {'status': 'ok'}


def test_register_returns_tokens_and_allows_login(client):
    _register(client)
    r = client.post('/auth/login', json={'email': 'alice@example.com', 'password': 'password123'})
    assert r.status_code == 200
    assert 'access_token' in r.json()


def test_register_duplicate_email_400(client):
    _register(client, 'dup@example.com', 'secret')
    r = client.post('/auth/register', json={'email': 'dup@example.com', 'password': 'secret'})
    assert r.status_code == 400
    assert r.json()['detail'] == 'Email already registered'


def test_login_wrong_password_401(client):
    _register(client, 'bob@example.com', 'right-password')
    r = client.post('/auth/login', json={'email': 'bob@example.com', 'password': 'wrong'})
    assert r.status_code == 401
    assert r.json()['detail'] == 'Invalid credentials'


def test_items_requires_auth(client):
    r = client.get('/items')
    assert r.status_code in (401, 403)


def test_items_flow_list_empty_then_create_and_list(client):
    tokens = _register(client, 'carol@example.com', 'pw')
    access = tokens['access_token']

    r0 = client.get('/items', headers=_bearer(access))
    assert r0.status_code == 200 and r0.json() == []

    r1 = client.post('/items', json={'title': 'First Item'}, headers=_bearer(access))
    assert r1.status_code == 200 and r1.json()['title'] == 'First Item'

    r2 = client.get('/items', headers=_bearer(access))
    assert r2.status_code == 200
    assert r2.json() == [{'title': 'First Item'}]


def test_refresh_token_issues_new_access_and_allows_call(client):
    tokens = _register(client, 'dave@example.com', 'pw')
    refresh = tokens['refresh_token']

    r = client.post('/auth/refresh', headers=_bearer(refresh))
    assert r.status_code == 200
    new_tokens = r.json()
    r2 = client.get('/items', headers=_bearer(new_tokens['access_token']))
    assert r2.status_code == 200 and r2.json() == []
