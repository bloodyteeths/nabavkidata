"""
Tests for the done-for-you bid-writing service API (api/bid_service.py).

No real database: the module's get_asyncpg_pool is monkeypatched to a fake pool
whose connection records every SQL call, and postmark_service.send_email is
replaced with an async recorder. The app under test mounts only
bid_service.router under /api (main.py is never imported).

Run:  cd backend && venv/bin/python -m pytest tests/test_bid_service.py -q --noconftest
(--noconftest because tests/conftest.py imports main.py and needs a live Postgres.)
"""
import json
import os
import re
import sys
import types
import uuid
from contextlib import asynccontextmanager
from datetime import date

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-bid-service-tests")

# api/ai.py pushes ../ai onto sys.path[0], which shadows backend/db_pool.py with
# ai/db_pool.py. Import the backend module first so the cached one wins.
import db_pool  # noqa: E402,F401

# backend/__init__.py is a stray copy of api/__init__.py, so pytest's Package
# setup would import it as `backend` and re-run api/tenders.py's Gemini import
# (crashes on Python 3.13 venv). Pre-seed an inert module at the same path so
# pytest's import_path finds it in sys.modules and skips executing that file.
_BACKEND_INIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "__init__.py")
if "backend" not in sys.modules:
    _stub = types.ModuleType("backend")
    _stub.__file__ = _BACKEND_INIT
    _stub.__path__ = [os.path.dirname(_BACKEND_INIT)]
    sys.modules["backend"] = _stub

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import bid_service  # noqa: E402
from middleware.rbac import require_admin  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeConn:
    """Records SQL; answers fetchrow/fetchval/fetch based on the statement text."""

    def __init__(self, existing_user=None, tender=None, history_row=None,
                 updated_lead=None, leads=None, recent_leads=0, race_user=None):
        self.calls: list[tuple[str, str, tuple]] = []
        self.existing_user = existing_user
        self.recent_leads = recent_leads
        # race_user: the user row a concurrent request inserted between our
        # SELECT and INSERT (INSERT ... ON CONFLICT then returns nothing).
        self.race_user = race_user
        self._user_lookups = 0
        self.tender = tender
        self.history_row = history_row
        self.updated_lead = updated_lead
        self.leads = leads or []
        self.lead_id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.transactions = 0

    def _log(self, kind, sql, args):
        self.calls.append((kind, " ".join(sql.split()), args))

    async def fetchrow(self, sql, *args):
        self._log("fetchrow", sql, args)
        if "FROM tenders WHERE tender_id" in sql:
            return self.tender
        if "FROM tender_bidders" in sql:
            return self.history_row
        if "FROM users WHERE LOWER(email)" in sql:
            self._user_lookups += 1
            if self.race_user is not None and self._user_lookups > 1:
                return self.race_user
            return self.existing_user
        if "UPDATE bid_service_leads" in sql:
            return self.updated_lead
        return None

    async def fetchval(self, sql, *args):
        self._log("fetchval", sql, args)
        if "INSERT INTO bid_service_leads" in sql:
            return self.lead_id
        if "INSERT INTO users" in sql:
            return None if self.race_user is not None else self.user_id
        if "COUNT(*) FROM bid_service_leads" in sql:
            return self.recent_leads
        return None

    async def fetch(self, sql, *args):
        self._log("fetch", sql, args)
        if "FROM bid_service_leads" in sql:
            return self.leads
        return []

    async def execute(self, sql, *args):
        self._log("execute", sql, args)
        return "OK"

    @asynccontextmanager
    async def _tx(self):
        self.transactions += 1
        yield

    def transaction(self):
        return self._tx()

    # helpers ---------------------------------------------------------------
    def find(self, needle):
        return [c for c in self.calls if needle in c[1]]


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


class MailRecorder:
    def __init__(self):
        self.sent: list[dict] = []

    async def __call__(self, to, subject, html_content, text_content=None, tag=None,
                       reply_to=None):
        self.sent.append(dict(to=to, subject=subject, html=html_content, tag=tag,
                              reply_to=reply_to))
        return True

    def by_tag(self, tag):
        return [m for m in self.sent if m["tag"] == tag]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    bid_service._qualify_hits.clear()
    yield
    bid_service._qualify_hits.clear()


@pytest.fixture
def mail(monkeypatch):
    rec = MailRecorder()
    monkeypatch.setattr(bid_service.postmark_service, "send_email", rec)
    return rec


@pytest.fixture
def make_client(monkeypatch, mail):
    """Factory: make_client(conn, admin=False) -> (TestClient, conn)."""

    def _make(conn=None, admin=False):
        conn = conn or FakeConn()

        async def fake_get_pool():
            return FakePool(conn)

        monkeypatch.setattr(bid_service, "get_asyncpg_pool", fake_get_pool)
        app = FastAPI()
        app.include_router(bid_service.router, prefix="/api")
        if admin:
            app.dependency_overrides[require_admin] = lambda: object()
        return TestClient(app), conn

    return _make


def _payload(**kw):
    base = {
        "company": "Тест Компанија ДООЕЛ",
        "email": "Lead@Example.MK",
        "lead_person": "Марко Петровски",
        "phone": "070123456",
        "wants_to_win": "одржување на софтвер",
        "source": "usluga",
    }
    base.update(kw)
    return base


PRICE_RE = re.compile(r"МКД|MKD|денар|%|\b30[.,]?000\b|\d+\s*ден", re.IGNORECASE)


# ---------------------------------------------------------------------------
# POST /api/bid-service/qualify
# ---------------------------------------------------------------------------
class TestQualifyValidation:
    def test_invalid_email_returns_400(self, make_client, mail):
        client, conn = make_client()
        r = client.post("/api/bid-service/qualify", json=_payload(email="not-an-email"))
        assert r.status_code == 400
        assert conn.calls == []  # rejected before touching the DB
        assert mail.sent == []

    def test_company_too_short_is_422(self, make_client):
        client, _ = make_client()
        r = client.post("/api/bid-service/qualify", json=_payload(company="A"))
        assert r.status_code == 422


class TestQualifyNewEmail:
    def test_provisions_unverified_prospect_and_auto_logs_in(self, make_client, mail):
        client, conn = make_client()
        r = client.post("/api/bid-service/qualify", json=_payload())
        assert r.status_code == 200, r.text
        data = r.json()

        # Lead captured, email normalised, linked to the new user
        lead_ins = conn.find("INSERT INTO bid_service_leads")
        assert len(lead_ins) == 1
        assert lead_ins[0][2][0] == "lead@example.mk"
        assert lead_ins[0][2][7] == conn.user_id
        assert data["lead_id"] == str(conn.lead_id)

        # New user as UNVERIFIED prospect, race-safe insert
        user_ins = conn.find("INSERT INTO users")
        assert len(user_ins) == 1
        sql = user_ins[0][1]
        assert "'prospect'" in sql
        assert "FALSE,$4,$5" in sql and "TRUE" not in sql
        assert "ON CONFLICT (email) DO NOTHING" in sql

        # Auto-login for the brand-new identity only (BidFinder §4.2):
        # tokens for OUR inserted user id + exactly one session row.
        from jose import jwt as _jwt
        from api.auth import SECRET_KEY, ALGORITHM, hash_token
        auth = data["auth"]
        assert auth and auth["token_type"] == "bearer"
        access = _jwt.decode(auth["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        assert access["sub"] == str(conn.user_id) and access["type"] == "access"
        # Never a long-lived refresh token: the typist may not own the mailbox.
        assert auth["refresh_token"] is None
        sessions = conn.find("INSERT INTO user_sessions")
        assert len(sessions) == 1
        assert sessions[0][2][0] == conn.user_id
        assert sessions[0][2][1] == hash_token(auth["access_token"])
        assert sessions[0][2][2].endswith("|qualify")
        # No tender given -> portal
        assert data["next"] == "portal" and data["tender_id"] is None

        # Keyword alert from wants_to_win
        alerts = conn.find("INSERT INTO tender_alerts")
        assert len(alerts) == 1
        assert json.loads(alerts[0][2][2]) == {"keywords": ["одржување на софтвер"]}

        # Both emails sent; the set-password link doubles as the verification link
        admin = mail.by_tag("bid-service-lead")
        confirm = mail.by_tag("qualify-confirm")
        assert len(admin) == 1 and admin[0]["to"] == bid_service.ADMIN_EMAIL
        assert len(confirm) == 1 and confirm[0]["to"] == "lead@example.mk"
        assert "reset-password?token=" in confirm[0]["html"]
        assert "Веќе сте најавени на овој уред" in confirm[0]["html"]
        assert "лозинка" in data["message"]

    def test_confirmation_email_contains_no_pricing(self, make_client, mail):
        client, _ = make_client()
        client.post("/api/bid-service/qualify", json=_payload())
        confirm = mail.by_tag("qualify-confirm")[0]
        text = confirm["subject"] + " " + confirm["html"]
        assert not PRICE_RE.search(text), PRICE_RE.search(text)

    def test_no_alert_when_wants_to_win_empty(self, make_client):
        client, conn = make_client()
        r = client.post("/api/bid-service/qualify", json=_payload(wants_to_win=""))
        assert r.status_code == 200
        assert conn.find("INSERT INTO tender_alerts") == []
        assert r.json()["auth"] is not None  # new identity: still auto-logged-in

    def test_free_text_is_split_into_keywords(self, make_client):
        client, conn = make_client()
        text = ("одржување на софтвер, градежни работи; медицински материјал "
                "или опрема\n17400/2026, ИТ, градежни работи")
        client.post("/api/bid-service/qualify", json=_payload(wants_to_win=text))
        kws = json.loads(conn.find("INSERT INTO tender_alerts")[0][2][2])["keywords"]
        assert kws == ["одржување на софтвер", "градежни работи",
                       "медицински материјал", "опрема"]

    def test_only_tender_numbers_creates_no_alert(self, make_client):
        client, conn = make_client()
        client.post("/api/bid-service/qualify", json=_payload(wants_to_win="17400/2026"))
        assert conn.find("INSERT INTO tender_alerts") == []

    def test_concurrent_insert_falls_back_to_existing_user(self, make_client, mail):
        uid = uuid.uuid4()
        conn = FakeConn(race_user={"user_id": uid, "account_type": "prospect"})
        client, conn = make_client(conn)
        r = client.post("/api/bid-service/qualify", json=_payload())
        assert r.status_code == 200, r.text
        assert r.json()["auth"] is None
        assert r.json()["next"] is None
        assert conn.find("INSERT INTO user_sessions") == []
        assert conn.find("INSERT INTO bid_service_leads")[0][2][7] == uid
        assert conn.find("INSERT INTO tender_alerts") == []
        assert "reset-password" not in mail.by_tag("qualify-confirm")[0]["html"]

    def test_lead_insert_is_inside_transaction(self, make_client):
        client, conn = make_client()
        client.post("/api/bid-service/qualify", json=_payload())
        # one transaction for the history lookup, one for user+lead
        assert conn.transactions == 2

    def test_html_in_inputs_is_escaped_in_admin_alert(self, make_client, mail):
        client, _ = make_client()
        client.post("/api/bid-service/qualify",
                    json=_payload(company="<script>x</script> ДОО"))
        admin_html = mail.by_tag("bid-service-lead")[0]["html"]
        assert "<script>" not in admin_html
        assert "&lt;script&gt;" in admin_html


class TestQualifyExistingEmail:
    def test_anonymous_submit_does_not_modify_existing_user(self, make_client, mail):
        uid = uuid.uuid4()
        conn = FakeConn(existing_user={"user_id": uid, "account_type": "free"})
        client, conn = make_client(conn)
        r = client.post("/api/bid-service/qualify", json=_payload())
        assert r.status_code == 200
        data = r.json()

        assert data["auth"] is None  # account-takeover guard
        assert data["next"] is None
        assert conn.find("INSERT INTO users") == []
        assert conn.find("INSERT INTO user_sessions") == []
        assert conn.find("UPDATE users") == []

        # lead linked to existing user
        lead_args = conn.find("INSERT INTO bid_service_leads")[0][2]
        assert lead_args[7] == uid

        confirm = mail.by_tag("qualify-confirm")[0]
        assert "reset-password" not in confirm["html"]

    def test_signed_in_owner_is_moved_to_prospect(self, make_client):
        from api.auth import create_access_token
        uid = uuid.uuid4()
        conn = FakeConn(existing_user={"user_id": uid, "account_type": "free"})
        client, conn = make_client(conn)
        token = create_access_token(data={"sub": str(uid)})
        r = client.post("/api/bid-service/qualify", json=_payload(),
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        upd = conn.find("UPDATE users SET account_type='prospect'")
        assert len(upd) == 1 and upd[0][2][0] == uid

    def test_token_of_another_user_does_not_modify(self, make_client):
        from api.auth import create_access_token
        conn = FakeConn(existing_user={"user_id": uuid.uuid4(), "account_type": "free"})
        client, conn = make_client(conn)
        token = create_access_token(data={"sub": str(uuid.uuid4())})
        client.post("/api/bid-service/qualify", json=_payload(),
                    headers={"Authorization": f"Bearer {token}"})
        assert conn.find("UPDATE users") == []

    def test_existing_managed_client_is_not_downgraded(self, make_client):
        conn = FakeConn(existing_user={"user_id": uuid.uuid4(), "account_type": "managed_client"})
        client, conn = make_client(conn)
        r = client.post("/api/bid-service/qualify", json=_payload())
        assert r.status_code == 200
        assert r.json()["auth"] is None
        assert conn.find("UPDATE users") == []

    def test_per_email_daily_limit(self, make_client, mail):
        client, conn = make_client(FakeConn(recent_leads=3))
        r = client.post("/api/bid-service/qualify", json=_payload())
        assert r.status_code == 429
        assert conn.find("INSERT INTO bid_service_leads") == []
        assert mail.sent == []


class TestQualifyTenderAndHistory:
    def test_tender_id_lookup_passes_through(self, make_client, mail):
        tender = {
            "tender_id": "17400/2026",
            "title": "Одржување на софтвер за субвенции",
            "procuring_entity": "МЕРМС",
            "closing_date": date(2099, 10, 22),
            "estimated_value_mkd": 400000,
            "status": "open",
        }
        client, conn = make_client(FakeConn(tender=tender))
        r = client.post("/api/bid-service/qualify",
                        json=_payload(tender_id="17400/2026", source="tender-card"))
        assert r.status_code == 200

        lookup = conn.find("FROM tenders WHERE tender_id")
        assert len(lookup) == 1 and lookup[0][2] == ("17400/2026",)

        lead_args = conn.find("INSERT INTO bid_service_leads")[0][2]
        assert lead_args[5] == "17400/2026"
        assert lead_args[6] == "tender-card"

        admin_html = mail.by_tag("bid-service-lead")[0]["html"]
        assert "17400/2026" in admin_html and "2099-10-22" in admin_html
        confirm_html = mail.by_tag("qualify-confirm")[0]["html"]
        assert "Одржување на софтвер за субвенции" in confirm_html
        assert r.json()["next"] == "tender"
        assert r.json()["tender_id"] == "17400/2026"

    def test_closed_tender_routes_new_identity_to_portal(self, make_client):
        tender = {"tender_id": "1/2020", "title": "Стар", "procuring_entity": "X",
                  "closing_date": date(2020, 1, 1), "estimated_value_mkd": None,
                  "status": "open"}
        client, _ = make_client(FakeConn(tender=tender))
        r = client.post("/api/bid-service/qualify", json=_payload(tender_id="1/2020"))
        assert r.status_code == 200
        assert r.json()["auth"] is not None
        assert r.json()["next"] == "portal"

    def test_existing_email_with_open_tender_gets_no_tokens(self, make_client):
        tender = {"tender_id": "17400/2026", "title": "T", "procuring_entity": "X",
                  "closing_date": date(2099, 1, 1), "estimated_value_mkd": None,
                  "status": "open"}
        conn = FakeConn(tender=tender,
                        existing_user={"user_id": uuid.uuid4(), "account_type": "prospect"})
        client, conn = make_client(conn)
        r = client.post("/api/bid-service/qualify", json=_payload(tender_id="17400/2026"))
        assert r.status_code == 200
        assert r.json()["auth"] is None and r.json()["next"] is None
        assert conn.find("INSERT INTO user_sessions") == []

    def test_unknown_tender_id_stores_null(self, make_client):
        client, conn = make_client(FakeConn(tender=None))
        r = client.post("/api/bid-service/qualify", json=_payload(tender_id="99999/2026"))
        assert r.status_code == 200
        assert conn.find("INSERT INTO bid_service_leads")[0][2][5] is None
        assert r.json()["next"] == "portal" and r.json()["tender_id"] is None

    def test_like_wildcards_are_escaped(self, make_client):
        client, conn = make_client(FakeConn(history_row={"bids": 0}))
        client.post("/api/bid-service/qualify", json=_payload(company="50%_Firma"))
        q = conn.find("FROM tender_bidders")[0]
        assert "ESCAPE" in q[1]
        assert q[2] == ("%50\\%\\_Firma%",)
        assert conn.find("statement_timeout")

    def test_wildcard_only_company_skips_lookup(self, make_client):
        client, conn = make_client()
        r = client.post("/api/bid-service/qualify", json=_payload(company="%%%%__"))
        assert r.status_code == 200
        assert conn.find("FROM tender_bidders") == []

    def test_award_history_recorded_on_lead(self, make_client, mail):
        hist_row = {"bids": 0}  # no bids -> {"bids":0,"wins":0}
        client, conn = make_client(FakeConn(history_row=hist_row))
        client.post("/api/bid-service/qualify", json=_payload())
        lead_args = conn.find("INSERT INTO bid_service_leads")[0][2]
        assert '"bids": 0' in lead_args[8]
        assert "0 победи / 0 понуди" in mail.by_tag("bid-service-lead")[0]["html"]


class TestRateLimit:
    def test_ninth_request_from_same_ip_is_429(self, make_client):
        client, _ = make_client()
        headers = {"x-real-ip": "203.0.113.7"}
        for i in range(8):
            r = client.post("/api/bid-service/qualify",
                            json=_payload(email=f"u{i}@example.mk"), headers=headers)
            assert r.status_code == 200, (i, r.text)
        r = client.post("/api/bid-service/qualify", json=_payload(), headers=headers)
        assert r.status_code == 429

        # A different IP is unaffected
        r = client.post("/api/bid-service/qualify", json=_payload(),
                        headers={"x-real-ip": "198.51.100.1"})
        assert r.status_code == 200

    def test_spoofed_left_xff_does_not_bypass(self, make_client):
        client, _ = make_client()
        for i in range(8):
            r = client.post("/api/bid-service/qualify", json=_payload(email=f"s{i}@example.mk"),
                            headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.9"})
            assert r.status_code == 200
        r = client.post("/api/bid-service/qualify", json=_payload(),
                        headers={"x-forwarded-for": "10.9.9.9, 203.0.113.9"})
        assert r.status_code == 429

    def test_client_ip_helper(self):
        from starlette.requests import Request as SReq

        def req(headers, host="127.0.0.1"):
            return SReq({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
                         "client": (host, 1234)})

        assert bid_service._client_ip(req({"x-real-ip": "1.2.3.4",
                                           "x-forwarded-for": "9.9.9.9"})) == "1.2.3.4"
        assert bid_service._client_ip(req({"x-forwarded-for": "evil, 5.6.7.8"})) == "5.6.7.8"
        assert bid_service._client_ip(req({"x-real-ip": "not-an-ip"})) == "127.0.0.1"

    def test_expired_keys_are_swept(self, monkeypatch):
        monkeypatch.setattr(bid_service, "_MAX_TRACKED_IPS", 5)
        for i in range(10):
            bid_service._qualify_hits[f"old{i}"] = [0.0]
        assert bid_service._rate_limit_ok("fresh")
        assert set(bid_service._qualify_hits) == {"fresh"}


# ---------------------------------------------------------------------------
# GET /api/bid-service/terms
# ---------------------------------------------------------------------------
def test_terms_are_public_and_match_business_rules(make_client):
    client, _ = make_client()
    r = client.get("/api/bid-service/terms")
    assert r.status_code == 200
    assert r.json() == {"prep_fee_mkd": 30000, "success_fee_pct": 5}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------
class TestAdmin:
    def test_list_leads_requires_auth(self, make_client):
        client, conn = make_client(admin=False)
        r = client.get("/api/bid-service/admin/leads")
        assert r.status_code in (401, 403)  # HTTPBearer: no credentials -> 403
        assert conn.calls == []

    def test_patch_requires_auth(self, make_client):
        client, conn = make_client(admin=False)
        r = client.patch(f"/api/bid-service/admin/leads/{uuid.uuid4()}",
                         json={"status": "contacted"})
        assert r.status_code in (401, 403)  # HTTPBearer: no credentials -> 403
        assert conn.calls == []

    def test_list_leads_as_admin(self, make_client):
        lid, uid = uuid.uuid4(), uuid.uuid4()
        leads = [{"id": lid, "user_id": uid, "status": "new",
                  "history": '{"bids": 3, "wins": 1}', "tender_title": None,
                  "closing_date": None}]
        client, conn = make_client(FakeConn(leads=leads), admin=True)
        r = client.get("/api/bid-service/admin/leads?status=new&limit=10")
        assert r.status_code == 200, r.text
        out = r.json()["leads"]
        assert out[0]["id"] == str(lid)
        assert out[0]["user_id"] == str(uid)
        assert out[0]["history"] == {"bids": 3, "wins": 1}
        assert conn.find("FROM bid_service_leads")[0][2] == ("new", 10)

    def test_list_leads_limit_capped(self, make_client):
        client, _ = make_client(admin=True)
        assert client.get("/api/bid-service/admin/leads?limit=501").status_code == 422

    def test_patch_client_promotes_user_to_managed_client(self, make_client):
        lid, uid = uuid.uuid4(), uuid.uuid4()
        conn = FakeConn(updated_lead={"id": lid, "status": "client", "user_id": uid})
        client, conn = make_client(conn, admin=True)
        r = client.patch(f"/api/bid-service/admin/leads/{lid}",
                         json={"status": "client", "admin_notes": "фактура платена"})
        assert r.status_code == 200, r.text
        assert r.json() == {"id": str(lid), "status": "client"}
        promo = conn.find("UPDATE users SET account_type='managed_client'")
        assert len(promo) == 1 and promo[0][2] == (uid,)

    def test_patch_other_status_does_not_promote(self, make_client):
        lid = uuid.uuid4()
        conn = FakeConn(updated_lead={"id": lid, "status": "contacted", "user_id": uuid.uuid4()})
        client, conn = make_client(conn, admin=True)
        r = client.patch(f"/api/bid-service/admin/leads/{lid}", json={"status": "contacted"})
        assert r.status_code == 200
        assert conn.find("UPDATE users") == []

    def test_patch_invalid_status_is_422(self, make_client):
        client, conn = make_client(admin=True)
        r = client.patch(f"/api/bid-service/admin/leads/{uuid.uuid4()}",
                         json={"status": "paid"})
        assert r.status_code == 422
        assert conn.calls == []

    def test_patch_malformed_id_is_422(self, make_client):
        client, conn = make_client(admin=True)
        r = client.patch("/api/bid-service/admin/leads/not-a-uuid", json={"status": "contacted"})
        assert r.status_code == 422
        assert conn.calls == []

    def test_patch_client_without_user_warns(self, make_client):
        lid = uuid.uuid4()
        conn = FakeConn(updated_lead={"id": lid, "status": "client", "user_id": None})
        client, conn = make_client(conn, admin=True)
        r = client.patch(f"/api/bid-service/admin/leads/{lid}", json={"status": "client"})
        assert r.status_code == 200
        assert "warning" in r.json()
        assert conn.find("UPDATE users") == []

    def test_patch_missing_lead_is_404(self, make_client):
        client, _ = make_client(FakeConn(updated_lead=None), admin=True)
        r = client.patch(f"/api/bid-service/admin/leads/{uuid.uuid4()}",
                         json={"status": "contacted"})
        assert r.status_code == 404
