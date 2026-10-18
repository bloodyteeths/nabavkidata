"""Upwork OAuth callback: reachable, signed state, admin-only start/status."""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db_pool  # noqa: E402,F401  (backend/db_pool before ai/ shadows it)
import types  # noqa: E402

if "backend" not in sys.modules:  # same package stub as tests/test_ops_api.py
    _stub = types.ModuleType("backend")
    _stub.__file__ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "__init__.py")
    _stub.__path__ = [os.path.dirname(_stub.__file__)]
    sys.modules["backend"] = _stub

import api.auth  # noqa: E402,F401  (import order as in test_ops_api)

from api import upwork_oauth  # noqa: E402
from middleware.rbac import require_admin  # noqa: E402


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(upwork_oauth.router, prefix="/api")
    return app


def test_callback_without_code_explains_not_404(client):
    r = TestClient(client).get("/api/upwork/oauth/callback")
    assert r.status_code == 200
    assert "Fakturino" in r.text and "OAuth" in r.text


def test_callback_rejects_bad_state(client, monkeypatch):
    monkeypatch.setenv("UPWORK_CLIENT_ID", "id")
    monkeypatch.setenv("UPWORK_CLIENT_SECRET", "secret")
    r = TestClient(client).get("/api/upwork/oauth/callback?code=abc&state=1.2.forged")
    assert r.status_code == 400


def test_state_roundtrip_and_expiry():
    s = upwork_oauth.make_state(now=1_000_000)
    assert upwork_oauth.verify_state(s, now=1_000_000 + 60)
    assert not upwork_oauth.verify_state(s, now=1_000_000 + upwork_oauth.STATE_TTL_S + 1)
    ts, nonce, sig = s.split(".")
    assert not upwork_oauth.verify_state(f"{ts}.{nonce}.{'0' * len(sig)}", now=1_000_000)


def test_start_and_status_require_admin(client):
    tc = TestClient(client)
    assert tc.get("/api/upwork/oauth/start", follow_redirects=False).status_code in (401, 403)
    assert tc.get("/api/upwork/oauth/status").status_code in (401, 403)


def test_start_redirects_to_upwork_for_admin(client, monkeypatch):
    monkeypatch.setenv("UPWORK_CLIENT_ID", "id123")
    client.dependency_overrides[require_admin] = lambda: object()
    r = TestClient(client).get("/api/upwork/oauth/start", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith(upwork_oauth.AUTHORIZE_URL) and "client_id=id123" in loc and "state=" in loc
