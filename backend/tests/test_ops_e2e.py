"""
Operator focus system end-to-end against a REAL throwaway PostgreSQL (Phase 4).

tests/test_ops_focus.py and tests/test_ops_api.py pin the Python logic with fake
connections; this file executes the services' actual SQL. It initdb's a private
cluster in pytest's tmp dir (UTF-8 locale so Cyrillic ~* and [[:alnum:]] behave
as in production), applies migrations 033-037 (037 twice: it must re-run), and
drives services / api.ops / the two crons with Postmark mocked at the HTTP layer.

Skipped automatically when the PostgreSQL server binaries are not installed.
Never touches any real database or mail server.

Run:  cd backend && venv/bin/python -m pytest tests/test_ops_e2e.py -q --noconftest
"""
import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import types
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ops-e2e")
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "crons"))

import db_pool  # noqa: E402,F401  (backend/db_pool before ai/ shadows it)

if "backend" not in sys.modules:
    _stub = types.ModuleType("backend")
    _stub.__file__ = os.path.join(BACKEND, "__init__.py")
    _stub.__path__ = [BACKEND]
    sys.modules["backend"] = _stub

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api.auth as api_auth  # noqa: E402
import middleware.rbac as rbac  # noqa: E402
from api import ops as api_ops  # noqa: E402
from services import client_shortlist, hot_signal, lead_watch, ops_copy, ops_focus  # noqa: E402
from services.ops_copy import check_draft_copy  # noqa: E402
from services.postmark import POSTMARK_API_URL, postmark_service  # noqa: E402
import daily_focus  # noqa: E402
import weekly_client_shortlist  # noqa: E402


def _pg_bin(name):
    found = shutil.which(name)
    if found:
        return found
    for base in ("/opt/homebrew/opt", "/usr/local/opt"):
        for v in ("postgresql@17", "postgresql@16", "postgresql@15", "postgresql@14"):
            p = Path(base, v, "bin", name)
            if p.exists():
                return str(p)
    for p in sorted(Path("/usr/lib/postgresql").glob(f"*/bin/{name}"), reverse=True):
        return str(p)
    return None


INITDB, PG_CTL = _pg_bin("initdb"), _pg_bin("pg_ctl")
pytestmark = pytest.mark.skipif(not (INITDB and PG_CTL), reason="PostgreSQL server binaries not installed")

SKOPJE = ZoneInfo("Europe/Skopje")
MIGRATIONS = Path(BACKEND, "db", "migrations")
ADMIN = ops_copy.ADMIN_EMAIL


def _workday() -> date:
    d = ops_copy.today_skopje()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


TODAY = _workday()              # frozen "today" for every service/API/cron call
MONDAY = ops_copy.week_start(TODAY)

# Columns the earlier (pre-033) schema provides; only what Phase 1-4 code reads.
BASE_SCHEMA = """
CREATE TABLE users (
  user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255), full_name VARCHAR(255), role VARCHAR(20) DEFAULT 'user',
  subscription_tier VARCHAR(50) DEFAULT 'free', stripe_customer_id VARCHAR(255),
  email_verified BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());
CREATE TABLE tenders (
  tender_id VARCHAR(100) PRIMARY KEY, title TEXT, procuring_entity TEXT, closing_date DATE,
  estimated_value_mkd NUMERIC(15,2), status VARCHAR(50) DEFAULT 'open', cpv_code VARCHAR(50),
  procedure_type VARCHAR(200), publication_date DATE, created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE suppression_list (id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL, reason TEXT);
CREATE TABLE user_behavior (
  behavior_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
  tender_id VARCHAR(100), action VARCHAR(50) NOT NULL, created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'UTC'));
CREATE TABLE user_sessions (
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
  last_activity TIMESTAMP DEFAULT NOW());
CREATE TABLE tender_alerts (
  alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL DEFAULT 'a', alert_type VARCHAR(50) NOT NULL DEFAULT 'keyword',
  criteria JSONB NOT NULL DEFAULT '{}', is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW());
CREATE TABLE alert_matches (
  match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id UUID NOT NULL REFERENCES tender_alerts(alert_id) ON DELETE CASCADE,
  tender_id VARCHAR(100) NOT NULL, match_score NUMERIC(5,2) NOT NULL DEFAULT 60);
"""

TABLES = ("users, tenders, suppression_list, user_behavior, user_sessions, tender_alerts, alert_matches, "
          "bid_service_leads, bid_jobs, bid_messages, client_wins, concierge_log, focus_item_state, "
          "ops_sent_emails, ops_digest_log, lead_watches, lead_watch_shown, client_shortlists, "
          "client_shortlist_items")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def dsn(tmp_path_factory):
    root = tmp_path_factory.mktemp("pg")
    data = root / "data"
    r = subprocess.run([INITDB, "-D", str(data), "-U", "postgres", "-A", "trust", "-E", "UTF8",
                        "--locale=en_US.UTF-8"], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"initdb failed: {r.stderr[-300:]}")
    port = _free_port()
    opts = (f"-p {port} -c listen_addresses=127.0.0.1 -c unix_socket_directories= "
            f"-c timezone=UTC -c fsync=off -c full_page_writes=off")
    r = subprocess.run([PG_CTL, "-D", str(data), "-l", str(root / "pg.log"), "-w", "-o", opts, "start"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"pg_ctl start failed: {r.stderr[-300:]} {(root / 'pg.log').read_text()[-300:]}")
    url = f"postgresql://postgres@127.0.0.1:{port}/postgres"

    async def setup():
        c = await asyncpg.connect(url)
        try:
            await c.execute(BASE_SCHEMA)
            for name in ("033_bid_service.sql", "034_bid_jobs.sql", "035_stripe_self_serve.sql",
                         "036_concierge.sql", "037_ops_focus.sql", "037_ops_focus.sql"):
                await c.execute((MIGRATIONS / name).read_text(encoding="utf-8"))
        finally:
            await c.close()

    try:
        asyncio.run(setup())
        yield url
    finally:
        subprocess.run([PG_CTL, "-D", str(data), "-m", "immediate", "-w", "stop"], capture_output=True)


class ConnPool:
    """get_asyncpg_pool() stand-in: a fresh connection per acquire (works across event loops)."""

    def __init__(self, url):
        self.url = url

    @asynccontextmanager
    async def acquire(self):
        c = await asyncpg.connect(self.url)
        try:
            yield c
        finally:
            await c.close()


@pytest.fixture
def db(dsn, monkeypatch, tmp_path):
    missing = str(tmp_path / "no_focus_manual.json")
    monkeypatch.setattr(ops_focus, "FOCUS_MANUAL_PATH", missing)
    monkeypatch.setattr(ops_copy, "FOCUS_MANUAL_PATH", missing)
    monkeypatch.setattr(ops_copy, "today_skopje", lambda: TODAY)

    def q(fn):
        async def go():
            c = await asyncpg.connect(dsn)
            try:
                return await fn(c)
            finally:
                await c.close()
        return asyncio.run(go())

    q(lambda c: c.execute(f"TRUNCATE {TABLES} CASCADE"))
    return SimpleNamespace(url=dsn, q=q, pool=ConnPool(dsn))


# ---------------------------------------------------------------------------
# Seed helpers (async, take a connection)
# ---------------------------------------------------------------------------
async def add_user(c, email, account_type="prospect", *, role="user", full_name=None, company=None,
                   created_days_ago=10, verified=True):
    return await c.fetchval(
        "INSERT INTO users (email, role, account_type, full_name, company_name, email_verified, created_at) "
        "VALUES ($1,$2,$3,$4,$5,$6, NOW() - make_interval(days => $7)) RETURNING user_id",
        email, role, account_type, full_name, company, verified, created_days_ago)


async def add_tender(c, tid, days, title="Одржување на софтверско решение за субвенции", *,
                     status="open", entity="Министерство за економија", value=400000, pub_days_ago=0,
                     today=TODAY):
    await c.execute(
        "INSERT INTO tenders (tender_id, title, procuring_entity, closing_date, estimated_value_mkd, status, "
        "procedure_type, publication_date) VALUES ($1,$2,$3,$4,$5,$6,'Отворена постапка',$7)",
        tid, title, entity, today + timedelta(days=days), value, status, today - timedelta(days=pub_days_ago))


async def add_job(c, user_id, tid, status, *, age_days=0, **cols):
    jid = await c.fetchval(
        "INSERT INTO bid_jobs (user_id, tender_id, status, created_at, updated_at) "
        "VALUES ($1,$2,$3, NOW() - make_interval(days => $4), NOW() - make_interval(days => $4)) RETURNING id",
        user_id, tid, status, age_days)
    for k, v in cols.items():
        await c.execute(f"UPDATE bid_jobs SET {k} = $2 WHERE id = $1", jid, v)
    return jid


async def add_lead(c, email, *, tid=None, status="new", wants="одржување софтвер", company="Градба ДОО",
                   person="Петар Николовски", updated_days_ago=0, user_id=None):
    return await c.fetchval(
        "INSERT INTO bid_service_leads (email, company_name, lead_person, wants_to_win, tender_id, source, "
        "status, user_id, created_at, updated_at) VALUES ($1,$2,$3,$4,$5,'usluga',$6,$7, "
        "NOW() - make_interval(days => $8), NOW() - make_interval(days => $8)) RETURNING id",
        email, company, person, wants, tid, status, user_id, updated_days_ago)


async def view(c, user_id, tid, hours_ago=2):
    await c.execute("INSERT INTO user_behavior (user_id, tender_id, action, created_at) "
                    "VALUES ($1,$2,'view', (NOW() AT TIME ZONE 'UTC') - make_interval(hours => $3))",
                    user_id, tid, hours_ago)


def focus(db, today=TODAY, **kw):
    return db.q(lambda c: ops_focus.build_focus(c, today, manual=kw.pop("manual", []), **kw))


def keys_of(res, kind=None):
    return [i["key"] for i in res["items"] if kind is None or i["kind"] == kind]


def assert_clean_drafts(res):
    for it in res["items"]:
        d = it.get("draft")
        if not d:
            continue
        assert check_draft_copy(d["subject"] + "\n" + d["body_text"]) == [], (it["key"], d)
        assert d["body_text"].rstrip().endswith("+389 70 253 467")
        # never the estimated value (URLs stripped first: a uuid4 in a portal link can contain "400")
        body_no_urls = re.sub(r"https?://\S+", "", d["body_text"])
        assert "400" not in body_no_urls and "400000" not in d["subject"]
        assert d["to"] == d["to"].lower() and d["to"] != ADMIN


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------
def test_migration_reruns_and_postmark_key_is_unique(db):
    async def go(c):
        await c.execute((MIGRATIONS / "037_ops_focus.sql").read_text(encoding="utf-8"))
        ins = ("INSERT INTO ops_sent_emails (dedupe_key, kind, to_email, channel) VALUES ($1,'x',$2,$3) "
               "ON CONFLICT DO NOTHING RETURNING id")
        a = await c.fetchval(ins, "lead:1", "a@b.mk", "postmark")
        b = await c.fetchval(ins, "lead:1", "a@b.mk", "postmark")
        m1 = await c.fetchval(ins, "lead:1", "a@b.mk", "manual")
        m2 = await c.fetchval(ins, "lead:1", "a@b.mk", "manual")
        with pytest.raises(asyncpg.CheckViolationError):
            await c.execute("INSERT INTO ops_sent_emails (dedupe_key, kind, to_email, channel) "
                            "VALUES ('k','x','Upper@B.mk','postmark')")
        return a, b, m1, m2
    a, b, m1, m2 = db.q(go)
    assert a is not None and b is None and m1 is not None and m2 is not None


# ---------------------------------------------------------------------------
# Hot signal: only open tenders closing in 3..45 days
# ---------------------------------------------------------------------------
def test_hot_signal_window_and_suppression(db):
    async def seed(c):
        uid = await add_user(c, "marija@firma.mk", "prospect", full_name="Марија Петровска",
                             company="Софтвер Плус ДООЕЛ")
        for tid, days, st in [("1/2026", 2, "open"), ("2/2026", 3, "open"), ("3/2026", 45, "open"),
                              ("4/2026", 46, "open"), ("5/2026", 10, "closed"), ("6/2026", 10, "awarded"),
                              ("7/2026", -1, "open"), ("8/2026", 10, None)]:
            await add_tender(c, tid, days, status=st)
            await view(c, uid, tid)
        await view(c, uid, "8/2026", hours_ago=24 * 6)          # outside lookback: still counted once
        await c.execute("INSERT INTO concierge_log (user_id, tender_id, question) VALUES ($1,'2/2026','Што бара?')", uid)
        staff = await add_user(c, "ana@nabavkidata.com", "free")
        adm = await add_user(c, "boss@firma.mk", "free", role="admin")
        for u in (staff, adm):
            await view(c, u, "2/2026")
        return uid
    uid = db.q(seed)
    rows = db.q(lambda c: hot_signal.find_hot_signals(c, TODAY, 48))
    assert sorted(r["tender_id"] for r in rows) == ["2/2026", "3/2026", "8/2026"]
    assert {r["email"] for r in rows} == {"marija@firma.mk"}
    r2 = next(r for r in rows if r["tender_id"] == "2/2026")
    assert (r2["n_views"], r2["n_asks"]) == (1, 1)
    assert next(r for r in rows if r["tender_id"] == "8/2026")["n_views"] == 1

    res = focus(db)
    hot = [i for i in res["items"] if i["kind"] == "hot_signal"]
    # one person, one item: the other two signals collapse into the survivor
    assert [i["key"] for i in hot] == [f"hot:{uid}:2-2026"]
    assert sorted(hot[0]["meta"]["collapsed_keys"]) == [f"hot:{uid}:3-2026", f"hot:{uid}:8-2026"]
    assert hot[0]["tender"]["closing_date"] >= TODAY.isoformat()
    assert_clean_drafts(res)

    # a bid job for (user, tender) or any email to them after the first event kills the signal
    db.q(lambda c: add_job(c, uid, "3/2026", "requested"))
    assert sorted(r["tender_id"] for r in db.q(lambda c: hot_signal.find_hot_signals(c, TODAY, 48))) == \
        ["2/2026", "8/2026"]
    db.q(lambda c: c.execute("INSERT INTO ops_sent_emails (dedupe_key, kind, to_email, channel) "
                             "VALUES ('x','hot_signal','marija@firma.mk','manual')"))
    assert db.q(lambda c: hot_signal.find_hot_signals(c, TODAY, 48)) == []


def test_hot_signal_suppressed_user(db):
    async def seed(c):
        uid = await add_user(c, "Vesna@Firma.mk", "free")
        await add_tender(c, "2/2026", 10)
        await view(c, uid, "2/2026")
        await c.execute("INSERT INTO suppression_list (email) VALUES ('vesna@firma.mk')")
    db.q(seed)
    assert db.q(lambda c: hot_signal.find_hot_signals(c, TODAY, 48)) == []


def test_hot_signal_sql_without_user_behavior_branch(db):
    """Contract: drop the view branch when user_behavior is missing. The remaining
    UNION must still expose the at/src columns the agg CTE reads."""
    async def go(c):
        uid = await add_user(c, "asker@firma.mk", "prospect")
        await add_tender(c, "2/2026", 10)
        await c.execute("INSERT INTO concierge_log (user_id, tender_id, question) VALUES ($1,'2/2026','?')", uid)
        since = datetime.now(timezone.utc) - timedelta(hours=48)
        return [dict(r) for r in await c.fetch(hot_signal.SQL_SIGNALS_NO_VIEWS, since, TODAY)]
    rows = db.q(go)
    assert [(r["tender_id"], r["n_views"], r["n_asks"]) for r in rows] == [("2/2026", 0, 1)]


# ---------------------------------------------------------------------------
# Every kind appears under its trigger and disappears once resolved
# ---------------------------------------------------------------------------
def test_job_kinds_appear_and_resolve(db):
    async def seed(c):
        u = await add_user(c, "klient@firma.mk", "managed_client", full_name="Ана Стојанова", company="Фирма ДООЕЛ")
        for tid, days in [("10/2026", 2), ("11/2026", 20), ("12/2026", 4), ("13/2026", 20), ("14/2026", 20),
                          ("15/2026", 20), ("16/2026", 20)]:
            await add_tender(c, tid, days)
        await add_tender(c, "19/2026", -1)                       # closed
        now = datetime.now(timezone.utc)
        j = {
            "approved": await add_job(c, u, "10/2026", "approved"),
            "requested": await add_job(c, u, "11/2026", "requested"),
            "prep": await add_job(c, u, "12/2026", "preparing", age_days=5),
            "changes": await add_job(c, u, "13/2026", "changes_requested", reopen_count=2),
            "invoice": await add_job(c, u, "14/2026", "payment_required", invoice_requested_at=now),
            "paycheck": await add_job(c, u, "15/2026", "payment_required", invoice_requested_at=now,
                                      invoice_issued_at=now - timedelta(days=3), invoice_number="12/2026"),
            "checkout": await add_job(c, u, "16/2026", "payment_required", age_days=2,
                                      stripe_checkout_session_id="cs_test_1"),
            "closed": await add_job(c, u, "19/2026", "approved"),
        }
        return j
    j = db.q(seed)
    res = focus(db)
    ks = keys_of(res)
    expect = {
        f"job:{j['approved']}:approved", f"job:{j['requested']}:requested",
        f"job:{j['prep']}:preparing", f"job:{j['prep']}:preparing-deadline",
        f"job:{j['changes']}:changes:2", f"job:{j['invoice']}:invoice",
        f"job:{j['paycheck']}:paycheck", f"job:{j['checkout']}:checkout",
    }
    assert expect <= set(ks)
    assert not any(str(j["closed"]) in k for k in ks)            # closed tender never surfaces
    assert_clean_drafts(res)
    pay = next(i for i in res["items"] if i["kind"] == "job_payment_check")
    assert "12/2026" in pay["draft"]["body_text"] and pay["draft"]["to"] == "klient@firma.mk"

    async def resolve(c):
        now = datetime.now(timezone.utc)
        await c.execute("UPDATE bid_jobs SET status='submitted' WHERE id=$1", j["approved"])
        await c.execute("UPDATE bid_jobs SET status='payment_required' WHERE id=$1", j["requested"])
        await c.execute("UPDATE bid_jobs SET published_at=NOW(), updated_at=NOW() WHERE id=$1", j["prep"])
        await c.execute("UPDATE bid_jobs SET status='ready' WHERE id=$1", j["changes"])
        await c.execute("UPDATE bid_jobs SET invoice_issued_at=NOW() WHERE id=$1", j["invoice"])
        await c.execute("UPDATE bid_jobs SET paid_at=$2, status='preparing', updated_at=NOW() WHERE id=$1",
                        j["paycheck"], now)
        await c.execute("UPDATE bid_jobs SET invoice_requested_at=NOW() WHERE id=$1", j["checkout"])
    db.q(resolve)
    ks2 = set(keys_of(focus(db)))
    assert not (expect - {f"job:{j['checkout']}:invoice"}) & ks2
    assert f"job:{j['checkout']}:invoice" in ks2                 # card abandoned -> invoice chosen


def test_message_win_lead_shortlist_and_touch_kinds(db):
    async def seed(c):
        u = await add_user(c, "klient@firma.mk", "managed_client", company="Фирма ДООЕЛ")
        await add_tender(c, "20/2026", 10)
        jid = await add_job(c, u, "20/2026", "preparing")
        m1 = await c.fetchval("INSERT INTO bid_messages (user_id, job_id, sender_role, body) "
                              "VALUES ($1,$2,'client','Дали е готово?') RETURNING id", u, jid)
        w = await c.fetchval("INSERT INTO client_wins (user_id, tender_id, tender_title, matched_name, match_score) "
                             "VALUES ($1,'9/2026','Т','Фирма',0.9) RETURNING id", u)
        lead_open = await add_lead(c, "info@gradba.mk", tid="20/2026")
        await add_tender(c, "21/2026", -2)
        lead_closed = await add_lead(c, "drug@gradba.mk", tid="21/2026", company="Друга ДОО")
        old = await add_lead(c, "star@gradba.mk", updated_days_ago=61)
        sl = await c.fetchval("INSERT INTO client_shortlists (user_id, week_start, subject, intro_text) "
                              "VALUES ($1,$2,'С','И') RETURNING id", u, MONDAY)
        return SimpleNamespace(u=u, jid=jid, m1=m1, w=w, lead_open=lead_open, lead_closed=lead_closed,
                               old=old, sl=sl)
    s = db.q(seed)
    res = focus(db)
    ks = keys_of(res)
    msg_key = f"msg:{s.u}:{s.jid}:{s.m1}"
    week_key = f"shortlist:{ops_copy.iso_week(TODAY)}"
    assert {msg_key, f"win:{s.w}", f"lead:{s.lead_open}", f"lead:{s.lead_closed}", week_key} <= set(ks)
    assert f"lead:{s.old}" not in ks
    closed = next(i for i in res["items"] if i["key"] == f"lead:{s.lead_closed}")
    assert closed["tender"] is None and "21/2026" not in closed["draft"]["body_text"]
    opened = next(i for i in res["items"] if i["key"] == f"lead:{s.lead_open}")
    assert opened["tender"]["tender_id"] == "20/2026" and "„Одржување" in opened["draft"]["body_text"]
    assert_clean_drafts(res)

    # Monday client touch: present until we wrote to them this week
    touch_key = f"touch:{s.u}:{ops_copy.iso_week(MONDAY)}"
    assert touch_key in keys_of(focus(db, MONDAY))

    async def resolve(c):
        await c.execute("UPDATE bid_messages SET read_by_admin_at=NOW() WHERE id=$1", s.m1)
        await c.execute("UPDATE client_wins SET status='confirmed' WHERE id=$1", s.w)
        await c.execute("UPDATE client_shortlists SET status='sent' WHERE id=$1", s.sl)
        return await c.fetchval("INSERT INTO bid_messages (user_id, sender_role, body) "
                                "VALUES ($1,'client','Ново прашање') RETURNING id", s.u)
    m2 = db.q(resolve)
    db.q(lambda c: ops_focus.mark_done(c, f"lead:{s.lead_open}", TODAY, "send"))
    ks2 = keys_of(focus(db))
    assert msg_key not in ks2 and f"msg:{s.u}:general:{m2}" in ks2   # new message, new key
    assert f"win:{s.w}" not in ks2 and week_key not in ks2
    assert f"lead:{s.lead_open}" not in ks2
    assert db.q(lambda c: c.fetchval("SELECT status FROM bid_service_leads WHERE id=$1", s.lead_open)) == "contacted"

    assert touch_key not in keys_of(focus(db, MONDAY))            # shortlist sent this week
    db.q(lambda c: c.execute("UPDATE client_shortlists SET status='draft' WHERE id=$1", s.sl))
    assert touch_key in keys_of(focus(db, MONDAY))
    db.q(lambda c: c.execute("INSERT INTO bid_messages (user_id, sender_role, body) VALUES ($1,'admin','Здраво')", s.u))
    assert touch_key not in keys_of(focus(db, MONDAY))            # admin message this week


def test_done_snooze_reopen_and_internal_recipients(db):
    async def seed(c):
        await add_lead(c, "ops@nabavkidata.com")
        await add_lead(c, "x@facturino.mk")
        await add_lead(c, "Suppressed@Firma.mk")
        await c.execute("INSERT INTO suppression_list (email) VALUES ('suppressed@firma.mk')")
        await add_user(c, "atillatkulu@gmail.com", "free", role="admin")
        await add_lead(c, "Atillatkulu@gmail.com")                     # admin is internal too
        return await add_lead(c, "real@firma.mk")
    lid = db.q(seed)
    key = f"lead:{lid}"
    res = focus(db)
    assert keys_of(res, "lead_untriaged") == [key]

    db.q(lambda c: ops_focus.mark_done(c, key, TODAY, "ui"))
    r = focus(db, include_done=True)
    assert key not in keys_of(r) and [i["key"] for i in r["done"]] == [key]
    # 'ui' done (e.g. after sending from Gmail) also moves the lead to 'contacted',
    # so it is not stranded as 'new' with no go-back cadence
    assert db.q(lambda c: c.fetchval("SELECT status FROM bid_service_leads WHERE id=$1", lid)) == "contacted"
    db.q(lambda c: c.execute("UPDATE bid_service_leads SET status='new' WHERE id=$1", lid))
    db.q(lambda c: ops_focus.reopen(c, key))
    assert key in keys_of(focus(db))
    db.q(lambda c: ops_focus.snooze(c, key, TODAY, 3))
    assert key not in keys_of(focus(db))
    back = TODAY + timedelta(days=3)
    while back.weekday() >= 5:
        back += timedelta(days=1)
    assert key in keys_of(focus(db, back))


# ---------------------------------------------------------------------------
# lead_watch: cadence 3/7/14/21 and a shown tender is never offered again
# ---------------------------------------------------------------------------
def test_goback_cadence_and_never_repeats(db):
    async def seed(c):
        lid = await add_lead(c, "Petar@Gradba.mk", status="contacted", wants="одржување софтвер, ГИС",
                             updated_days_ago=5)
        await add_tender(c, "30/2026", 20, "Набавка на софтверски решенија за ГИС")
        await add_tender(c, "31/2026", 3, "Одржување софтвер")                       # < min_days_to_close
        await add_tender(c, "32/2026", 20, "Одржување софтвер", status="closed")
        await add_tender(c, "33/2026", 20, "Хардвер и мрежна опрема")                 # no keyword
        await add_tender(c, "34/2026", 20, "Одржување софтвер", pub_days_ago=30)     # old news
        return lid
    db.q(seed)
    stats = db.q(lambda c: lead_watch.sync_watches(c, TODAY, lambda d: False))
    assert stats["created"] == 1
    assert db.q(lambda c: lead_watch.sync_watches(c, TODAY, lambda d: False))["created"] == 0   # idempotent
    w = db.q(lambda c: c.fetchrow("SELECT * FROM lead_watches"))
    assert w["email"] == "petar@gradba.mk" and w["source"] == "lead"
    assert list(w["keywords"]) == ["одржување софтвер"]           # 'ГИС' (3 chars) dropped by split_keywords
    assert w["follow_up_due"] == (w["anchor_at"] + timedelta(days=3)).date()
    db.q(lambda c: c.execute("UPDATE lead_watches SET keywords = '{софтвер,гис}', follow_up_due=$1", TODAY))

    res = focus(db)
    gb = [i for i in res["items"] if i["kind"] == "goback"]
    assert len(gb) == 1 and gb[0]["key"] == f"goback:{w['id']}:0"
    assert gb[0]["meta"]["tender_ids"] == ["30/2026"]
    assert_clean_drafts(res)
    assert "„Набавка на софтверски решенија за ГИС“" in gb[0]["draft"]["body_text"]

    db.q(lambda c: ops_focus.mark_done(c, gb[0]["key"], TODAY, "ui"))
    w1 = db.q(lambda c: c.fetchrow("SELECT * FROM lead_watches"))
    assert w1["touch_count"] == 1
    assert w1["follow_up_due"] == lead_watch.shift_to_working_day(
        w1["anchor_at"].date() + timedelta(days=7), lambda d: ops_copy.off_day(d, []))
    assert db.q(lambda c: c.fetch("SELECT tender_id FROM lead_watch_shown"))[0]["tender_id"] == "30/2026"

    # due again, nothing new: no item, a note, and 30/2026 is NOT re-offered
    db.q(lambda c: c.execute("UPDATE lead_watches SET follow_up_due=$1", TODAY))
    r2 = focus(db)
    assert keys_of(r2, "goback") == [] and any("го-бек" in n for n in r2["notes"])
    db.q(lambda c: add_tender(c, "35/2026", 15, "Надградба на софтвер за плати"))
    lead_watch.clear_match_cache()   # "nothing new" is cached for NO_MATCH_TTL_S per process
    r3 = focus(db)
    gb3 = [i for i in r3["items"] if i["kind"] == "goback"]
    assert [i["key"] for i in gb3] == [f"goback:{w['id']}:1"] and gb3[0]["meta"]["tender_ids"] == ["35/2026"]

    # cadence after the 2nd, 3rd, 4th touch: +14, +21, +21 (anchor moves with each touch)
    when = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)
    dues = [db.q(lambda c, n=n: lead_watch.mark_touched(c, w["id"], lambda d: False,
                                                        when=when + timedelta(days=n)))
            for n in range(3)]
    assert dues == [date(2026, 1, 19), date(2026, 1, 27), date(2026, 1, 28)]
    assert lead_watch.next_due(when, (3, 7, 14), 21, 0) == date(2026, 1, 8)


def test_watch_deactivates_and_replied(db):
    async def seed(c):
        await add_lead(c, "a@firma.mk", status="contacted", updated_days_ago=5)
        await add_lead(c, "b@firma.mk", status="contacted", updated_days_ago=5)
        ub = await add_user(c, "b@firma.mk", "prospect")
        await add_lead(c, "c@firma.mk", status="qualified", updated_days_ago=5)
        await add_user(c, "c@firma.mk", "managed_client")
        return ub
    ub = db.q(seed)
    db.q(lambda c: lead_watch.sync_watches(c, TODAY, lambda d: False))
    db.q(lambda c: c.execute("INSERT INTO bid_messages (user_id, sender_role, body) VALUES ($1,'client','Да')", ub))
    db.q(lambda c: lead_watch.sync_watches(c, TODAY, lambda d: False))
    rows = {r["email"]: r for r in db.q(lambda c: c.fetch("SELECT * FROM lead_watches"))}
    assert rows["a@firma.mk"]["active"] and rows["a@firma.mk"]["replied_at"] is None
    assert rows["b@firma.mk"]["replied_at"] is not None
    assert not rows["c@firma.mk"]["active"] and "managed_client" in rows["c@firma.mk"]["notes"]
    db.q(lambda c: c.execute("UPDATE lead_watches SET follow_up_due=$1", TODAY))
    assert [w["email"] for w in db.q(lambda c: lead_watch.due_watches(c, TODAY))] == ["a@firma.mk"]


# ---------------------------------------------------------------------------
# API with the real services: admin gate, one email to the draft recipient, signed link
# ---------------------------------------------------------------------------
class Postmark:
    def __init__(self):
        self.calls = []
        self.fail = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert str(request.url) == POSTMARK_API_URL
        self.calls.append(json.loads(request.content))
        if self.fail:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"MessageID": f"pm-{len(self.calls)}", "ErrorCode": 0})


@pytest.fixture
def api(db, monkeypatch):
    pm = Postmark()
    real_client = httpx.AsyncClient

    def client_factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(pm.handler)
        return real_client(*a, **kw)

    async def get_pool():
        return db.pool

    async def no_bulk_send(**kw):
        raise AssertionError("api.ops must not use postmark_service.send_email")

    monkeypatch.setattr(api_ops.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(api_ops, "get_asyncpg_pool", get_pool)
    monkeypatch.setattr(postmark_service, "_get_headers",
                        lambda: {"Accept": "application/json", "Content-Type": "application/json",
                                 "X-Postmark-Server-Token": "test-token"})
    monkeypatch.setattr(postmark_service, "send_email", no_bulk_send)

    admin_id = db.q(lambda c: add_user(c, ADMIN, "free", role="admin"))
    user_id = db.q(lambda c: add_user(c, "client@firma.mk", "managed_client"))
    st = SimpleNamespace(pm=pm, db=db, user=None)
    st.admin = SimpleNamespace(user_id=admin_id, email=ADMIN, role="admin", account_type="free",
                               subscription_tier="free", is_active=True, email_verified=True)
    st.nonadmin = SimpleNamespace(user_id=user_id, email="client@firma.mk", role="user",
                                  account_type="managed_client", subscription_tier="free",
                                  is_active=True, email_verified=True)
    app = FastAPI()
    app.include_router(api_ops.router, prefix="/api")

    def current():
        if st.user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return st.user

    for dep in (api_auth.get_current_user, rbac.get_current_user, rbac.get_current_active_user):
        app.dependency_overrides[dep] = current
    st.client = TestClient(app)
    return st


ADMIN_ROUTES = [
    ("get", "/api/ops/focus"), ("post", "/api/ops/focus/lead:x/done"),
    ("post", "/api/ops/focus/lead:x/snooze"), ("post", "/api/ops/focus/lead:x/reopen"),
    ("post", "/api/ops/drafts/lead:x/send"), ("get", "/api/ops/calendar-url"),
    ("get", "/api/ops/shortlists"), ("post", "/api/ops/shortlists/build"),
    ("post", f"/api/ops/watches/{uuid.uuid4()}/stop"),
    ("put", f"/api/ops/shortlists/{uuid.uuid4()}"), ("get", f"/api/ops/shortlists/{uuid.uuid4()}/preview"),
    ("post", f"/api/ops/shortlists/{uuid.uuid4()}/send"), ("post", f"/api/ops/shortlists/{uuid.uuid4()}/skip"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_only_routes_reject_non_admins(api, method, path):
    body = {"subject": "Тема", "body_text": "Текст", "picked": [], "reason": "replied"}
    api.user = None
    assert api.client.request(method.upper(), path, json=body).status_code == 401
    api.user = api.nonadmin
    assert api.client.request(method.upper(), path, json=body).status_code == 403
    assert api.pm.calls == []


def test_draft_send_one_email_to_draft_recipient_then_done(api):
    lid = api.db.q(lambda c: add_lead(c, "Marko@Firma.mk", person="Марко Марковски"))
    key = f"lead:{lid}"
    api.user = api.admin
    focus_res = api.client.get("/api/ops/focus").json()
    item = next(i for i in focus_res["items"] if i["key"] == key)
    payload = {"subject": item["draft"]["subject"], "body_text": item["draft"]["body_text"],
               "to": "attacker@evil.example"}                     # extra field must be ignored

    r = api.client.post(f"/api/ops/drafts/{key}/send", json=payload)
    assert r.status_code == 200, r.text
    assert r.json() == {"key": key, "sent": True, "message_id": "pm-1", "to": "marko@firma.mk"}
    assert len(api.pm.calls) == 1
    sent = api.pm.calls[0]
    assert sent["To"] == "marko@firma.mk" and sent["Cc"] == ADMIN and sent["MessageStream"] == "outbound"
    assert sent["ReplyTo"] == os.getenv("OPS_REPLY_TO", ADMIN) and "hello@nabavkidata.com" in sent["From"]
    assert sent["Subject"] == item["draft"]["subject"] and sent["TextBody"] == item["draft"]["body_text"]

    async def state(c):
        return (await c.fetch("SELECT * FROM ops_sent_emails"),
                await c.fetchrow("SELECT * FROM focus_item_state WHERE key=$1", key),
                await c.fetchval("SELECT status FROM bid_service_leads WHERE id=$1", lid))
    rows, fs, lead_status = api.db.q(state)
    assert [(x["to_email"], x["channel"], x["message_id"]) for x in rows] == [("marko@firma.mk", "postmark", "pm-1")]
    assert fs["status"] == "done" and fs["done_via"] == "send" and fs["done_by"] == api.admin.user_id
    assert lead_status == "contacted"
    assert key not in [i["key"] for i in api.client.get("/api/ops/focus").json()["items"]]

    # second press: 404 (item resolved) or 409 (done) - never a second email
    again = api.client.post(f"/api/ops/drafts/{key}/send", json=payload)
    assert again.status_code in (404, 409)
    assert len(api.pm.calls) == 1


def test_draft_send_409_when_done_and_claim_blocks_resend(api):
    async def seed(c):
        uid = await add_user(c, "vesna@firma.mk", "prospect")
        await add_tender(c, "40/2026", 10)
        await view(c, uid, "40/2026")
        return uid
    uid = api.db.q(seed)
    key = f"hot:{uid}:40-2026"
    api.user = api.admin
    body = {"subject": "Тендер", "body_text": "Добар ден,\n\nВидовме дека Ве интересира тендерот." + ops_copy.SIGNATURE}
    api.db.q(lambda c: ops_focus.mark_done(c, key, TODAY, "ui"))
    assert api.client.post(f"/api/ops/drafts/{key}/send", json=body).status_code == 409
    api.db.q(lambda c: ops_focus.reopen(c, key))
    assert api.client.post(f"/api/ops/drafts/{key}/send", json=body).status_code == 200
    assert len(api.pm.calls) == 1
    # sent: hot signal for that person drops off by itself
    assert not [i for i in api.client.get("/api/ops/focus").json()["items"] if i["kind"] == "hot_signal"]


def test_draft_send_422_force_and_rollback_on_postmark_failure(api):
    lid = api.db.q(lambda c: add_lead(c, "ana@firma.mk"))
    key = f"lead:{lid}"
    api.user = api.admin
    bad = {"subject": "Понуда", "body_text": "Цената е 30.000 денари, бесплатно советување."}
    r = api.client.post(f"/api/ops/drafts/{key}/send", json=bad)
    assert r.status_code == 422 and set(r.json()["detail"]["violations"]) >= {"price", "free"}
    assert api.pm.calls == []

    api.pm.fail = True
    r = api.client.post(f"/api/ops/drafts/{key}/send", json=dict(bad, force=True))
    assert r.status_code == 502 and len(api.pm.calls) == 1
    assert api.db.q(lambda c: c.fetchval("SELECT count(*) FROM ops_sent_emails")) == 0     # claim rolled back
    assert api.db.q(lambda c: c.fetchval("SELECT count(*) FROM focus_item_state")) == 0

    api.pm.fail = False
    r = api.client.post(f"/api/ops/drafts/{key}/send", json=dict(bad, force=True))
    assert r.status_code == 200 and len(api.pm.calls) == 2


def test_draft_send_blocked_for_suppressed_recipient(api):
    async def seed(c):
        lid = await add_lead(c, "gone@firma.mk")
        return lid
    lid = api.db.q(seed)
    key = f"lead:{lid}"
    api.user = api.admin
    item = next(i for i in api.client.get("/api/ops/focus").json()["items"] if i["key"] == key)
    api.db.q(lambda c: c.execute("INSERT INTO suppression_list (email) VALUES ('GONE@firma.mk')"))
    r = api.client.post(f"/api/ops/drafts/{key}/send",
                        json={"subject": item["draft"]["subject"], "body_text": item["draft"]["body_text"]})
    assert r.status_code in (404, 409) and api.pm.calls == []


def test_signed_sent_link_valid_tampered_expired(api):
    lid = api.db.q(lambda c: add_lead(c, "link@firma.mk"))
    key = f"lead:{lid}"
    link = ops_copy.ops_done_link(key)
    qs = httpx.URL(link).params
    k, e, sig = qs["k"], qs["e"], qs["sig"]
    assert k == key

    g = api.client.get("/api/ops/sent", params={"k": k, "e": e, "sig": sig})
    assert g.status_code == 200 and "<form method=\"post\"" in g.text and "Потврди: завршено" in g.text
    assert api.db.q(lambda c: c.fetchval("SELECT count(*) FROM focus_item_state")) == 0     # GET never mutates

    for bad in ({"k": k, "e": e, "sig": "0" * 40},
                {"k": f"lead:{uuid.uuid4()}", "e": e, "sig": sig},
                {"k": k, "e": str(int(e) + 60), "sig": sig}):
        assert api.client.get("/api/ops/sent", params=bad).status_code == 403
        assert api.client.post("/api/ops/sent", data=bad).status_code == 403
    old = ops_copy.ops_done_link(key, now=datetime.now(timezone.utc) - timedelta(days=4))
    oq = httpx.URL(old).params
    assert api.client.post("/api/ops/sent", data={"k": oq["k"], "e": oq["e"], "sig": oq["sig"]}).status_code == 403
    assert api.db.q(lambda c: c.fetchval("SELECT count(*) FROM focus_item_state")) == 0

    p = api.client.post("/api/ops/sent", data={"k": k, "e": e, "sig": sig})
    assert p.status_code == 200 and "Означено како завршено" in p.text

    async def after(c):
        return (await c.fetchrow("SELECT status, done_via FROM focus_item_state WHERE key=$1", key),
                await c.fetch("SELECT to_email, channel, dedupe_key FROM ops_sent_emails"),
                await c.fetchval("SELECT status FROM bid_service_leads WHERE id=$1", lid))
    fs, sent, lead_status = api.db.q(after)
    assert (fs["status"], fs["done_via"]) == ("done", "link")
    assert [tuple(r) for r in sent] == [("link@firma.mk", "manual", key)]
    assert lead_status == "contacted"
    p2 = api.client.post("/api/ops/sent", data={"k": k, "e": e, "sig": sig})
    assert "Веќе беше означено" in p2.text
    assert api.db.q(lambda c: c.fetchval("SELECT count(*) FROM ops_sent_emails")) == 1
    assert api.pm.calls == []                                     # the link never sends anything


# ---------------------------------------------------------------------------
# Crons: 06:30 focus email only to Atilla, once a day; weekly shortlist never emails
# ---------------------------------------------------------------------------
@pytest.fixture
def mails(db, monkeypatch):
    out = []

    async def send_email(**kw):
        out.append(kw)
        return True

    monkeypatch.setattr(postmark_service, "send_email", send_email)
    return out


def test_daily_focus_hour_guard_covers_dst():
    six_cest = datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)
    six_cet = datetime(2026, 11, 16, 5, 30, tzinfo=timezone.utc)
    assert daily_focus.skopje_hour(six_cest) == 6 and daily_focus.skopje_hour(six_cet) == 6
    assert daily_focus.skopje_hour(datetime(2026, 11, 16, 4, 30, tzinfo=timezone.utc)) == 5
    assert daily_focus.skopje_hour(datetime(2026, 10, 16, 5, 30, tzinfo=timezone.utc)) == 7


def test_daily_focus_empty_then_once_to_admin_only(db, mails):
    run = lambda **kw: asyncio.run(daily_focus.run(pool=db.pool, **kw))  # noqa: E731
    six = datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)
    assert run(now=six)["status"] == "empty"
    assert mails == [] and db.q(lambda c: c.fetchval("SELECT count(*) FROM ops_digest_log")) == 0

    assert run(now=datetime(2026, 10, 16, 5, 30, tzinfo=timezone.utc))["status"] == "wrong_hour"

    lid = db.q(lambda c: add_lead(c, "lead@firma.mk"))
    assert run(now=six)["status"] == "sent"
    assert len(mails) == 1
    m = mails[0]
    assert m["to"] == ADMIN and m["tag"] == "daily_focus"
    assert m["subject"] == "НабавкиДата фокус: 1 ставка денес"
    body = m["text_content"]
    assert f"lead:{lid}" in body.replace("%3A", ":") and "--- нацрт ---" in body and "До: lead@firma.mk" in body
    assert db.q(lambda c: c.fetchval("SELECT item_count FROM ops_digest_log WHERE digest_date=$1", TODAY)) == 1

    assert run(now=six)["status"] == "already_sent"
    assert run(now_flag=True)["status"] == "already_sent"
    assert len(mails) == 1
    assert db.q(lambda c: c.fetchval("SELECT count(*) FROM ops_sent_emails")) == 0   # nothing to the lead


def test_weekly_shortlist_builds_drafts_never_emails_then_manual_send(db, mails, api):
    async def seed(c):
        u = await add_user(c, "klient2@firma.mk", "managed_client", full_name="Ана Стојанова",
                           company="Фирма ДООЕЛ")
        await c.execute("INSERT INTO tender_alerts (user_id, criteria) VALUES ($1, $2::jsonb)",
                        u, json.dumps({"keywords": ["софтвер"]}))
        await add_tender(c, "50/2026", 10, "Одржување на софтвер за плати")
        await add_tender(c, "51/2026", 12, "Набавка на СОФТВЕРСКИ лиценци")
        await add_tender(c, "52/2026", 20, "Развој на софтвер за архива")
        await add_tender(c, "53/2026", 3, "Одржување софтвер")                   # closes too soon
        await add_tender(c, "54/2026", 15, "Одржување софтвер", status="closed")
        await add_tender(c, "55/2026", 15, "Хардвер")
        await c.execute("INSERT INTO users (email, account_type) VALUES ('cold@firma.mk','prospect')")
        return u
    uid = db.q(seed)
    pm_calls_before = len(api.pm.calls)
    counts = asyncio.run(weekly_client_shortlist.run(pool=db.pool))
    assert counts == {"built": 1, "existing": 0, "no_candidates": 1}   # client@firma.mk: no alerts
    assert asyncio.run(weekly_client_shortlist.run(pool=db.pool))["existing"] == 1
    assert mails == [] and len(api.pm.calls) == pm_calls_before
    assert db.q(lambda c: c.fetchval("SELECT count(*) FROM ops_sent_emails")) == 0

    api.user = api.admin
    week = api.client.get("/api/ops/shortlists").json()
    assert week["week_start"] == MONDAY.isoformat()
    (sl,) = [s for s in week["shortlists"] if s["user_id"] == str(uid)]
    assert sl["status"] == "draft"
    assert sorted(i["tender_id"] for i in sl["items"]) == ["50/2026", "51/2026", "52/2026"]
    assert all(i["open"] for i in sl["items"])
    assert f"shortlist:{ops_copy.iso_week(TODAY)}" in keys_of(focus(db))

    sid = sl["id"]
    assert api.client.put(f"/api/ops/shortlists/{sid}", json={"picked": ["50/2026"]}).status_code == 200
    assert api.client.post(f"/api/ops/shortlists/{sid}/send", json={}).status_code == 422     # < 2 picks
    assert api.client.put(f"/api/ops/shortlists/{sid}",
                          json={"picked": ["50/2026", "54/2026"]}).status_code == 422     # not a candidate
    assert api.client.put(f"/api/ops/shortlists/{sid}",
                          json={"picked": ["a", "b", "c", "d", "e"]}).status_code == 422
    r = api.client.put(f"/api/ops/shortlists/{sid}",
                       json={"picked": ["50/2026", "52/2026"],
                             "notes": {"50/2026": "Ова е токму Вашата дејност."}})
    assert r.status_code == 200
    prev = api.client.get(f"/api/ops/shortlists/{sid}/preview").json()
    assert prev["violations"] == [] and prev["to"] == "klient2@firma.mk"
    assert "51-2026" not in prev["body_text"] and "лиценци" not in prev["body_text"]
    assert "Добар ден, Ана," in prev["body_text"] and "400" not in prev["body_text"]

    s1 = api.client.post(f"/api/ops/shortlists/{sid}/send", json={})
    assert s1.status_code == 200, s1.text
    assert len(api.pm.calls) == pm_calls_before + 1 and api.pm.calls[-1]["To"] == "klient2@firma.mk"
    assert api.client.post(f"/api/ops/shortlists/{sid}/send", json={}).status_code == 409
    assert len(api.pm.calls) == pm_calls_before + 1
    assert f"shortlist:{ops_copy.iso_week(TODAY)}" not in keys_of(focus(db))
    assert mails == []

    # next week's candidates never repeat what was sent
    nxt = db.q(lambda c: client_shortlist.candidates_for(c, uid, "klient2@firma.mk", TODAY))
    assert sorted(x["tender_id"] for x in nxt) == ["51/2026"]


# ---------------------------------------------------------------------------
# Review fixes (16 Oct 2026), against real SQL
# ---------------------------------------------------------------------------
def test_one_send_resolves_every_kind_for_that_person(api):
    """BidFinder spam pattern: a hot-signal e-mail today must not be followed by the
    same person's lead reply and go-back tomorrow."""
    lead_watch.clear_match_cache()

    async def seed(c):
        uid = await add_user(c, "dragan@firma.mk", "prospect", full_name="Драган Илиевски")
        lid = await add_lead(c, "dragan@firma.mk", user_id=uid, wants="софтвер")
        await add_tender(c, "60/2026", 10, "Одржување на софтвер за плати")
        await add_tender(c, "61/2026", 20, "Развој на софтвер за архива")
        await view(c, uid, "60/2026")
        wid = await c.fetchval(
            "INSERT INTO lead_watches (email, source, keywords, anchor_at, follow_up_due) "
            "VALUES ('dragan@firma.mk','manual','{софтвер}', NOW() - interval '10 days', $1) RETURNING id", TODAY)
        return uid, lid, wid
    uid, lid, wid = api.db.q(seed)
    api.user = api.admin
    items = [i for i in api.client.get("/api/ops/focus").json()["items"] if i["email"] == "dragan@firma.mk"]
    assert [i["kind"] for i in items] == ["hot_signal"]
    assert {k.split(":")[0] for k in items[0]["meta"]["collapsed_keys"]} == {"lead", "goback"}
    d = items[0]["draft"]
    r = api.client.post(f"/api/ops/drafts/{items[0]['key']}/send",
                        json={"subject": d["subject"], "body_text": d["body_text"]})
    assert r.status_code == 200, r.text

    async def after(c):
        return (await c.fetchval("SELECT status FROM bid_service_leads WHERE id=$1", lid),
                await c.fetchrow("SELECT touch_count, follow_up_due FROM lead_watches WHERE id=$1", wid))
    status, w = api.db.q(after)
    assert status == "contacted"
    assert w["touch_count"] == 1 and w["follow_up_due"] > TODAY
    lead_watch.clear_match_cache()
    left = [i for i in api.client.get("/api/ops/focus").json()["items"] if i["email"] == "dragan@firma.mk"]
    assert left == []
    # even with the watch forced due again, the 3-day contact cooldown holds the go-back
    api.db.q(lambda c: c.execute("UPDATE lead_watches SET follow_up_due=$1", TODAY))
    gb, _ = api.db.q(lambda c: lead_watch.build_follow_ups(c, TODAY, False))
    assert gb == []
    assert len(api.pm.calls) == 1


def test_jobs_closed_tender_keeps_item_without_draft_and_ready_deadline(db):
    async def seed(c):
        u = await add_user(c, "klient3@firma.mk", "managed_client", full_name="Ана Стојанова")
        await add_tender(c, "70/2026", 2, status="cancelled")
        await add_tender(c, "71/2026", 2)
        return (await add_job(c, u, "70/2026", "approved"), await add_job(c, u, "71/2026", "ready"),
                await add_job(c, u, "72/2026", "approved"))          # tender row missing
    a, rdy, missing = db.q(seed)
    res = focus(db)
    by_key = {i["key"]: i for i in res["items"]}
    assert by_key[f"job:{a}:approved"]["draft"] is None
    assert "поништен" in by_key[f"job:{a}:approved"]["detail"]
    ready = by_key[f"job:{rdy}:ready-deadline"]
    assert ready["kind"] == "job_ready_deadline" and ready["draft"]["to"] == "klient3@firma.mk"
    assert f"/portal/bid/{rdy}" in ready["draft"]["body_text"]
    assert not any(str(missing) in k and by_key[k]["draft"] for k in by_key)
    assert_clean_drafts(res)


def test_shortlist_candidates_skip_old_news_and_last_weeks_candidates(db):
    async def seed(c):
        u = await add_user(c, "klient4@firma.mk", "managed_client", company="Фирма ДООЕЛ")
        await c.execute("INSERT INTO tender_alerts (user_id, criteria) VALUES ($1, $2::jsonb)",
                        u, json.dumps({"keywords": ["софтвер"]}))
        await add_tender(c, "80/2026", 20, "Одржување на софтвер")
        await add_tender(c, "81/2026", 20, "Набавка на софтвер", pub_days_ago=30)   # old news
        await add_tender(c, "82/2026", 20, "Развој на софтвер")
        sid = await c.fetchval("INSERT INTO client_shortlists (user_id, week_start, subject, intro_text) "
                               "VALUES ($1, $2, 's', 'i') RETURNING id", u, MONDAY - timedelta(days=7))
        await c.execute("INSERT INTO client_shortlist_items (shortlist_id, tender_id, rank) "
                        "VALUES ($1, '82/2026', 1)", sid)                          # seen last week
        return u
    uid = db.q(seed)
    got = db.q(lambda c: client_shortlist.candidates_for(c, uid, "klient4@firma.mk", TODAY))
    assert [x["tender_id"] for x in got] == ["80/2026"]


def test_daily_focus_claim_blocks_an_overlapping_run(db, mails):
    db.q(lambda c: add_lead(c, "lead2@firma.mk"))
    db.q(lambda c: c.execute("INSERT INTO ops_digest_log (digest_date, item_count, message_ok) "
                             "VALUES ($1, 0, false)", TODAY))          # another run holds the claim
    assert asyncio.run(daily_focus.run(pool=db.pool, now_flag=True))["status"] == "already_sent"
    assert mails == []
    assert asyncio.run(daily_focus.run(pool=db.pool, now_flag=True, force=True))["status"] == "sent"
    assert len(mails) == 1


# ---------------------------------------------------------------------------
# main.py tolerates a missing api.chat_v2 (production-only module)
# ---------------------------------------------------------------------------
def test_main_imports_without_chat_v2():
    code = ("import sys; sys.modules['api.chat_v2'] = None\n"
            "import main\n"
            "paths = {getattr(r, 'path', '') for r in main.app.routes}\n"
            "assert main.chat_v2 is None\n"
            "assert '/api/ops/focus' in paths and '/api/ops/drafts/{key}/send' in paths\n"
            "print('OK')\n")
    env = dict(os.environ, SECRET_KEY=os.environ.get("SECRET_KEY", "x"))
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True,
                       timeout=180, env=env)
    assert r.returncode == 0 and r.stdout.strip().endswith("OK"), r.stderr[-2000:]
