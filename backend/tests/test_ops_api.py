"""
Operator focus API + crons (Phase 4): api/ops.py, crons/daily_focus.py,
crons/weekly_client_shortlist.py.

No real database, no Postmark: get_asyncpg_pool is monkeypatched to a FakePool
backed by an in-memory FakeConn that understands exactly the SQL constants
api/ops.py and the crons issue; the service layer (ops_focus / lead_watch /
client_shortlist) is replaced by small fakes so these tests pin the HTTP
contract (admin gate, send-once, recipient lock, copy check, claim rollback,
GET-never-mutates, shortlist pick rules, cron send-once). The service logic
itself is covered by tests/test_ops_focus.py.

Run:  cd backend && venv/bin/python -m pytest tests/test_ops_api.py -q --noconftest
"""
import asyncio
import os
import sys
import types
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ops-api-tests")
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "crons"))

import db_pool  # noqa: E402,F401  (backend/db_pool before ai/ shadows it)

if "backend" not in sys.modules:
    _stub = types.ModuleType("backend")
    _stub.__file__ = os.path.join(BACKEND, "__init__.py")
    _stub.__path__ = [BACKEND]
    sys.modules["backend"] = _stub

import pytest  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api.auth as api_auth  # noqa: E402
import middleware.rbac as rbac  # noqa: E402
from api import ops as api_ops  # noqa: E402
from services import client_shortlist, lead_watch, ops_copy, ops_focus  # noqa: E402
import daily_focus  # noqa: E402
import weekly_client_shortlist  # noqa: E402

TODAY = ops_copy.today_skopje()
LEAD_EMAIL = "marko@firma.mk"
KEY = "lead:11111111-1111-1111-1111-111111111111"


def _norm(sql: str) -> str:
    return " ".join(sql.split())


# ---------------------------------------------------------------------------
# Fake DB
# ---------------------------------------------------------------------------
class FakeConn:
    def __init__(self):
        self.state = {}            # focus key -> status
        self.sent = []             # ops_sent_emails rows
        self.suppressed = set()
        self.admin_emails = {"atillatkulu@gmail.com"}
        self.shortlists = {}       # id -> row dict
        self.watches = {}          # email -> watch id
        self.digest = {}           # date -> row
        self.cal_tokens = {}       # user_id -> token
        self.admin_ids = set()
        self.writes = 0

    def _is(self, sql, const):
        return _norm(sql) == _norm(const)

    async def fetchval(self, sql, *a):
        if self._is(sql, api_ops.SQL_STATE):
            return self.state.get(a[0])
        if self._is(sql, api_ops.SQL_SUPPRESSED):
            return 1 if a[0] in self.suppressed else None
        if self._is(sql, api_ops.SQL_ADMIN_EMAIL):
            return 1 if a[0] in self.admin_emails else None
        if self._is(sql, api_ops.SQL_CLAIM):
            key, kind, to, subject, body, by = a
            if any(r["dedupe_key"] == key and r["channel"] == "postmark" for r in self.sent):
                return None
            self.writes += 1
            rid = max([r["id"] for r in self.sent] + [0]) + 1
            self.sent.append({"id": rid, "dedupe_key": key, "kind": kind, "to_email": to,
                              "subject": subject, "body_text": body, "channel": "postmark",
                              "message_id": None, "sent_by": by})
            return rid
        if self._is(sql, api_ops.SQL_WATCH_BY_EMAIL):
            return self.watches.get(a[0])
        if self._is(sql, api_ops.SQL_CAL_TOKEN):
            return self.cal_tokens.get(a[0])
        if self._is(sql, api_ops.SQL_CAL_SET):
            self.cal_tokens.setdefault(a[0], a[1])
            return self.cal_tokens[a[0]]
        if self._is(sql, api_ops.SQL_CAL_OWNER):
            for uid, tok in self.cal_tokens.items():
                if tok == a[0] and uid in self.admin_ids:
                    return uid
            return None
        if self._is(sql, daily_focus.SQL_DIGEST_CLAIM):
            if a[0] in self.digest:
                return None
            self.writes += 1
            self.digest[a[0]] = {"item_count": 0, "message_ok": False}
            return a[0]
        raise AssertionError(f"unexpected fetchval: {_norm(sql)[:140]}")

    async def fetchrow(self, sql, *a):
        if self._is(sql, api_ops.SQL_SHORTLIST):
            return self.shortlists.get(str(a[0]))
        raise AssertionError(f"unexpected fetchrow: {_norm(sql)[:140]}")

    async def execute(self, sql, *a):
        self.writes += 1
        if self._is(sql, api_ops.SQL_UNCLAIM):
            self.sent = [r for r in self.sent if r["id"] != a[0]]
            return "DELETE 1"
        if self._is(sql, api_ops.SQL_SET_MSGID):
            for r in self.sent:
                if r["id"] == a[0]:
                    r["message_id"] = a[1]
            return "UPDATE 1"
        if self._is(sql, api_ops.SQL_MANUAL_SENT):
            key, kind, to, subject = a
            self.sent.append({"id": len(self.sent) + 1, "dedupe_key": key, "kind": kind,
                              "to_email": to, "subject": subject, "channel": "manual"})
            return "INSERT 0 1"
        if self._is(sql, daily_focus.SQL_DIGEST_LOG):
            self.digest[a[0]] = {"item_count": a[1], "message_ok": a[2]}
            return "INSERT 0 1"
        if self._is(sql, daily_focus.SQL_DIGEST_UNCLAIM):
            d = self.digest.get(a[0])
            if d and d["item_count"] == 0 and not d["message_ok"]:
                del self.digest[a[0]]
            return "DELETE 1"
        raise AssertionError(f"unexpected execute: {_norm(sql)[:140]}")


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


def lead_item(key=KEY, to=LEAD_EMAIL):
    return {
        "key": key, "kind": "lead_untriaged", "group": "sales", "priority": 50,
        "date": TODAY.isoformat(), "title": "Ново барање: Фирма ДОО", "detail": "Детал",
        "email": to, "tender": None, "links": [],
        "draft": {"to": to, "subject": "Вашето барање за понуда",
                  "body_text": "Добар ден,\n\nВи благодариме за барањето." + ops_copy.SIGNATURE},
        "meta": {},
    }


# ---------------------------------------------------------------------------
# Fixture: app with only ops.router, services faked
# ---------------------------------------------------------------------------
@pytest.fixture
def env(monkeypatch):
    conn = FakeConn()
    pool = FakePool(conn)
    st = SimpleNamespace(conn=conn, user=None, items={KEY: lead_item()}, done_calls=[],
                         sends=[], send_fail=False, shown=[], sl_items={}, stopped=[],
                         marked_sent=[], skipped=[], contacts=[])

    async def get_pool():
        return pool

    monkeypatch.setattr(api_ops, "get_asyncpg_pool", get_pool)

    async def get_item(c, key, today):
        return st.items.get(key)

    async def mark_done(c, key, today, via, actor_user_id=None, *, item=None, sent_manually=False):
        # Mirrors ops_focus.mark_done: atomic claim; only the claiming call
        # records the manual send (link / sent_manually) for an item with an email.
        st.done_calls.append((key, via) if not sent_manually else (key, via, "manual"))
        item = item or st.items.get(key)
        if c.state.get(key) == "done":
            return item
        c.state[key] = "done"
        c.writes += 1
        if item and item.get("email") and (via == "link" or sent_manually):
            await c.execute(api_ops.SQL_MANUAL_SENT, key, item["kind"], item["email"],
                            (item.get("draft") or {}).get("subject"))
        return item

    async def record_contact(c, email, *, skip_watch_id=None, when=None):
        st.contacts.append(email)

    async def build_focus(c, today, *, include_done=False, manual=None):
        items = [i for k, i in st.items.items() if c.state.get(k) != "done"]
        return {"date": today.isoformat(), "off_day": False, "items": items, "done": [], "notes": []}

    async def snooze(c, key, today, days):
        c.state[key] = "snoozed"
        return today + timedelta(days=days)

    async def reopen(c, key):
        c.state.pop(key, None)

    async def sync_watches(c, today):
        return {}

    async def record_shown(c, watch_id, tender_ids):
        st.shown.append((watch_id, list(tender_ids)))

    async def stop_watch(c, watch_id, reason):
        st.stopped.append((str(watch_id), reason))

    async def list_week(c, ws, today):
        out = []
        for sid, row in c.shortlists.items():
            if row["week_start"] == ws:
                out.append({"id": sid, "user_id": row["user_id"], "email": row["email"],
                            "company_name": "Фирма ДОО", "account_type": "managed_client",
                            "status": row["status"], "subject": "Тендери избрани за Фирма ДОО",
                            "intro_text": "Добар ден,", "built_at": None, "sent_at": None,
                            "items": st.sl_items.get(sid, [])})
        return out

    async def get_shortlist(c, sid, today):
        rows = await list_week(c, c.shortlists.get(str(sid), {}).get("week_start"), today)
        return next((r for r in rows if r["id"] == str(sid)), None)

    async def update_shortlist(c, sid, today, subject, intro_text, picked, notes):
        items = st.sl_items[str(sid)]
        if len(picked) > client_shortlist.MAX_PICK:
            raise ValueError("too many")
        by_id = {i["tender_id"]: i for i in items}
        for tid in picked:
            if tid not in by_id or not by_id[tid]["open"]:
                raise ValueError("not pickable")
        for i in items:
            i["picked"] = i["tender_id"] in picked

    def render(sl, items):
        picked = [i for i in items if i["picked"]]
        body = "Добар ден,\n\n" + "\n".join(f"• {i['title']}" for i in picked) + ops_copy.SIGNATURE
        return {"to": sl["email"], "subject": sl["subject"], "body_text": body,
                "body_html": ops_copy.render_html(body)}

    async def mark_sent(c, sid, message_id, sent_by):
        c.shortlists[str(sid)]["status"] = "sent"
        st.marked_sent.append((str(sid), message_id))

    async def skip(c, sid):
        c.shortlists[str(sid)]["status"] = "skipped"
        st.skipped.append(str(sid))

    async def send_one(to, subject, body_text, body_html, tag):
        st.sends.append({"to": to, "subject": subject, "body_text": body_text, "tag": tag})
        return None if st.send_fail else f"pm-{len(st.sends)}"

    for mod, name, fn in [
        (ops_focus, "get_item", get_item), (ops_focus, "mark_done", mark_done),
        (ops_focus, "build_focus", build_focus), (ops_focus, "snooze", snooze),
        (ops_focus, "reopen", reopen), (ops_focus, "record_contact", record_contact),
        (lead_watch, "sync_watches", sync_watches),
        (lead_watch, "record_shown", record_shown), (lead_watch, "stop_watch", stop_watch),
        (client_shortlist, "list_week", list_week),
        (client_shortlist, "get_shortlist", get_shortlist),
        (client_shortlist, "update_shortlist", update_shortlist),
        (client_shortlist, "render_shortlist_email", render),
        (client_shortlist, "mark_sent", mark_sent), (client_shortlist, "skip", skip),
        (api_ops, "send_one", send_one),
    ]:
        monkeypatch.setattr(mod, name, fn)

    app = FastAPI()
    app.include_router(api_ops.router, prefix="/api")

    def current():
        if st.user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return st.user

    for dep in (api_auth.get_current_user, rbac.get_current_user, rbac.get_current_active_user):
        app.dependency_overrides[dep] = current
    st.client = TestClient(app)
    st.admin = SimpleNamespace(user_id=uuid.uuid4(), email="atillatkulu@gmail.com", role="admin",
                               account_type="free", subscription_tier="free",
                               is_active=True, email_verified=True)
    conn.admin_ids.add(st.admin.user_id)
    st.client_user = SimpleNamespace(user_id=uuid.uuid4(), email="c@firma.mk", role="user",
                                     account_type="managed_client", subscription_tier="free",
                                     is_active=True, email_verified=True)
    return st


def _send(st, key=KEY, **body):
    payload = {"subject": "Вашето барање за понуда",
               "body_text": "Добар ден,\n\nВи благодариме за барањето." + ops_copy.SIGNATURE}
    payload.update(body)
    return st.client.post(f"/api/ops/drafts/{key}/send", json=payload)


# ---------------------------------------------------------------------------
# Admin gate
# ---------------------------------------------------------------------------
class TestAdminRequired:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/ops/focus"),
        ("post", f"/api/ops/focus/{KEY}/done"),
        ("post", f"/api/ops/focus/{KEY}/snooze"),
        ("post", f"/api/ops/focus/{KEY}/reopen"),
        ("post", f"/api/ops/drafts/{KEY}/send"),
        ("get", "/api/ops/shortlists"),
        ("post", "/api/ops/shortlists/build"),
        ("get", "/api/ops/calendar-url"),
        ("post", f"/api/ops/watches/{uuid.uuid4()}/stop"),
    ])
    def test_non_admin_and_anonymous_rejected(self, env, method, path):
        r = getattr(env.client, method)(path) if method == "get" else env.client.post(path, json={})
        assert r.status_code == 401
        env.user = env.client_user
        r = getattr(env.client, method)(path) if method == "get" else env.client.post(path, json={})
        assert r.status_code == 403
        assert env.sends == [] and env.done_calls == []

    def test_admin_gets_focus_with_counts(self, env):
        env.user = env.admin
        r = env.client.get("/api/ops/focus")
        assert r.status_code == 200
        d = r.json()
        assert d["counts"]["total"] == 1
        assert d["counts"]["by_group"] == {"clients": 0, "sales": 1, "money": 0, "reminders": 0}

    def test_bad_key_is_400(self, env):
        env.user = env.admin
        assert env.client.post("/api/ops/focus/BAD KEY!/done").status_code == 400

    def test_snooze_bounds(self, env):
        env.user = env.admin
        assert env.client.post(f"/api/ops/focus/{KEY}/snooze", json={"days": 31}).status_code == 422
        r = env.client.post(f"/api/ops/focus/{KEY}/snooze", json={"days": 3})
        assert r.status_code == 200
        assert r.json()["snoozed_until"] == (TODAY + timedelta(days=3)).isoformat()


# ---------------------------------------------------------------------------
# Draft send
# ---------------------------------------------------------------------------
class TestDraftSend:
    def test_send_once_then_409(self, env):
        env.user = env.admin
        r = _send(env)
        assert r.status_code == 200, r.text
        assert r.json() == {"key": KEY, "sent": True, "message_id": "pm-1", "to": LEAD_EMAIL}
        assert env.done_calls == [(KEY, "send")]
        assert [s["message_id"] for s in env.conn.sent] == ["pm-1"]
        r2 = _send(env)
        assert r2.status_code == 409
        assert len(env.sends) == 1

    def test_claim_blocks_even_when_state_not_done(self, env):
        # A concurrent second click: state not yet done, but the claim row exists.
        env.user = env.admin
        assert _send(env).status_code == 200
        env.conn.state.pop(KEY)
        assert _send(env).status_code == 409
        assert len(env.sends) == 1

    def test_recipient_is_locked(self, env):
        env.user = env.admin
        r = _send(env, to="attacker@evil.example")
        assert r.status_code == 200
        assert env.sends[0]["to"] == LEAD_EMAIL
        assert r.json()["to"] == LEAD_EMAIL

    @pytest.mark.parametrize("to", ["hello@nabavkidata.com", "x@facturino.mk",
                                    "atillatkulu@gmail.com", "gone@firma.mk"])
    def test_internal_or_suppressed_recipient_409(self, env, to):
        env.user = env.admin
        env.conn.suppressed.add("gone@firma.mk")
        env.items[KEY] = lead_item(to=to)
        assert _send(env).status_code == 409
        assert env.sends == [] and env.conn.sent == []

    def test_violations_422_then_force_200(self, env):
        env.user = env.admin
        bad = "Добар ден,\n\nПонудата е бесплатна и чини 5000 денари." + ops_copy.SIGNATURE
        r = _send(env, body_text=bad)
        assert r.status_code == 422
        v = r.json()["detail"]["violations"]
        assert "free" in v and "price" in v
        assert env.sends == [] and env.conn.sent == []
        r = _send(env, body_text=bad, force=True)
        assert r.status_code == 200
        assert len(env.sends) == 1

    def test_postmark_failure_rolls_back_claim(self, env):
        env.user = env.admin
        env.send_fail = True
        assert _send(env).status_code == 502
        assert env.conn.sent == []
        assert env.done_calls == []
        env.send_fail = False
        assert _send(env).status_code == 200
        assert len([r for r in env.conn.sent if r["channel"] == "postmark"]) == 1

    def test_uncertain_postmark_outcome_keeps_claim(self, env, monkeypatch):
        # Timeout after the request may have reached Postmark: no unclaim, so a
        # second click cannot deliver a duplicate.
        env.user = env.admin

        async def uncertain(to, subject, body_text, body_html, tag):
            env.sends.append({"to": to})
            raise api_ops.SendUncertain("read timeout")

        monkeypatch.setattr(api_ops, "send_one", uncertain)
        r = _send(env)
        assert r.status_code == 502 and "Postmark" in r.json()["detail"]
        claims = [x for x in env.conn.sent if x["channel"] == "postmark"]
        assert len(claims) == 1 and claims[0]["message_id"] == "unknown"
        assert _send(env).status_code == 409
        assert len(env.sends) == 1 and env.done_calls == []

    def test_done_sent_manually_records_manual_send(self, env):
        env.user = env.admin
        r = env.client.post(f"/api/ops/focus/{KEY}/done", json={"sent_manually": True})
        assert r.status_code == 200
        assert env.done_calls == [(KEY, "ui", "manual")]
        manual = [s for s in env.conn.sent if s["channel"] == "manual"]
        assert len(manual) == 1 and manual[0]["to_email"] == LEAD_EMAIL
        # plain „Готово“ without a body still works and records no send
        env.items["win:1"] = dict(lead_item(key="win:1"), email=None, draft=None)
        assert env.client.post("/api/ops/focus/win:1/done").status_code == 200
        assert len([s for s in env.conn.sent if s["channel"] == "manual"]) == 1

    def test_missing_item_or_draft_404(self, env):
        env.user = env.admin
        assert _send(env, key="lead:nope").status_code == 404
        env.items["win:1"] = dict(lead_item(key="win:1"), draft=None)
        assert _send(env, key="win:1").status_code == 404


# ---------------------------------------------------------------------------
# Signed one-click link
# ---------------------------------------------------------------------------
class TestSignedLink:
    def _qs(self, key=KEY, now=None):
        link = ops_copy.ops_done_link(key, now)
        return link.split("/api/ops/sent?", 1)[1]

    def test_get_does_not_mutate(self, env):
        r = env.client.get("/api/ops/sent?" + self._qs())
        assert r.status_code == 200
        assert "Потврди: завршено" in r.text and 'method="post"' in r.text
        assert env.done_calls == [] and env.conn.writes == 0 and env.conn.sent == []

    def test_post_marks_done_and_records_manual_send(self, env):
        from urllib.parse import parse_qs
        q = {k: v[0] for k, v in parse_qs(self._qs()).items()}
        r = env.client.post("/api/ops/sent", data=q)
        assert r.status_code == 200
        assert env.done_calls == [(KEY, "link")]
        manual = [s for s in env.conn.sent if s["channel"] == "manual"]
        assert len(manual) == 1 and manual[0]["to_email"] == LEAD_EMAIL
        # second click: idempotent (mark_done's claim fails, no second manual row)
        r = env.client.post("/api/ops/sent", data=q)
        assert r.status_code == 200
        assert "Веќе беше означено" in r.text
        assert len([s for s in env.conn.sent if s["channel"] == "manual"]) == 1

    def test_bad_or_expired_sig_403(self, env):
        from urllib.parse import parse_qs
        q = {k: v[0] for k, v in parse_qs(self._qs()).items()}
        assert env.client.get(f"/api/ops/sent?k={KEY}&e={q['e']}&sig=deadbeef").status_code == 403
        old = self._qs(now=datetime.now(timezone.utc) - timedelta(days=4))
        assert env.client.get("/api/ops/sent?" + old).status_code == 403
        oq = {k: v[0] for k, v in parse_qs(old).items()}
        assert env.client.post("/api/ops/sent", data=oq).status_code == 403
        assert env.done_calls == []


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------
class TestCalendar:
    def test_url_and_feed(self, env):
        env.user = env.admin
        r = env.client.get("/api/ops/calendar-url")
        assert r.status_code == 200
        d = r.json()
        assert d["webcal_url"].startswith("webcal://") and d["https_url"].endswith(".ics")
        token = d["https_url"].rsplit("/", 1)[1][:-4]
        assert len(token) >= 16
        assert env.client.get("/api/ops/calendar-url").json() == d  # stable
        env.user = None
        f = env.client.get(f"/api/ops/calendar/{token}.ics")
        assert f.status_code == 200
        assert f.headers["content-type"].startswith("text/calendar")
        assert "charset=utf-8" in f.headers["content-type"]
        assert f.headers["cache-control"] == "no-cache"
        assert "BEGIN:VEVENT" in f.text and "@nabavkidata.com" in f.text

    def test_unknown_or_short_token_404(self, env):
        assert env.client.get("/api/ops/calendar/short.ics").status_code == 404
        assert env.client.get("/api/ops/calendar/" + "x" * 32 + ".ics").status_code == 404

    def test_ics_escaping(self):
        assert api_ops._ics_escape("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
        long = api_ops._ics_fold("SUMMARY:" + "ж" * 100)
        assert all(len(part.encode()) <= 75 for part in long.split("\r\n"))


# ---------------------------------------------------------------------------
# Shortlists
# ---------------------------------------------------------------------------
def _seed_shortlist(env, n_items=5, closed=()):
    sid = str(uuid.uuid4())
    uid = env.client_user.user_id
    env.conn.shortlists[sid] = {"id": sid, "user_id": uid, "week_start": ops_copy.week_start(TODAY),
                                "status": "draft", "email": "c@firma.mk"}
    env.sl_items[sid] = [{"tender_id": f"{100 + i}/2026", "title": f"Тендер {i}",
                          "procuring_entity": "Општина", "closing_date": (TODAY + timedelta(days=10)).isoformat(),
                          "estimated_value_mkd": 100000, "reason": "Клучен збор: софтвер", "rank": i,
                          "picked": False, "note": None, "open": f"{100 + i}/2026" not in closed}
                         for i in range(n_items)]
    return sid


class TestShortlists:
    def test_pick_count_validated(self, env):
        env.user = env.admin
        sid = _seed_shortlist(env)
        five = [f"{100 + i}/2026" for i in range(5)]
        assert env.client.put(f"/api/ops/shortlists/{sid}", json={"picked": five}).status_code == 422
        r = env.client.put(f"/api/ops/shortlists/{sid}", json={"picked": five[:1]})
        assert r.status_code == 200
        r = env.client.post(f"/api/ops/shortlists/{sid}/send", json={})
        assert r.status_code == 422  # fewer than 2
        assert env.sends == []

    def test_closed_pick_rejected(self, env):
        env.user = env.admin
        sid = _seed_shortlist(env, closed=("100/2026",))
        r = env.client.put(f"/api/ops/shortlists/{sid}", json={"picked": ["100/2026", "101/2026"]})
        assert r.status_code == 422

    def test_send_once_marks_sent_shown_and_touch(self, env):
        env.user = env.admin
        sid = _seed_shortlist(env)
        env.conn.watches["c@firma.mk"] = "w1"
        assert env.client.put(f"/api/ops/shortlists/{sid}",
                              json={"picked": ["100/2026", "101/2026"]}).status_code == 200
        pv = env.client.get(f"/api/ops/shortlists/{sid}/preview").json()
        assert pv["violations"] == [] and pv["to"] == "c@firma.mk"
        r = env.client.post(f"/api/ops/shortlists/{sid}/send", json={})
        assert r.status_code == 200, r.text
        assert env.marked_sent == [(sid, "pm-1")]
        assert env.shown == [("w1", ["100/2026", "101/2026"])]
        assert env.contacts == ["c@firma.mk"]   # leads -> contacted, go-back cadence restarts
        touch = f"touch:{env.client_user.user_id}:{ops_copy.iso_week(TODAY)}"
        assert (touch, "send") in env.done_calls
        # no longer a draft -> 409, and no second email
        assert env.client.post(f"/api/ops/shortlists/{sid}/send", json={}).status_code == 409
        assert env.client.put(f"/api/ops/shortlists/{sid}", json={"picked": []}).status_code == 409
        assert len(env.sends) == 1

    def test_send_rollback_on_failure(self, env):
        env.user = env.admin
        sid = _seed_shortlist(env)
        env.client.put(f"/api/ops/shortlists/{sid}", json={"picked": ["100/2026", "101/2026"]})
        env.send_fail = True
        assert env.client.post(f"/api/ops/shortlists/{sid}/send", json={}).status_code == 502
        assert env.conn.sent == [] and env.marked_sent == []
        assert env.conn.shortlists[sid]["status"] == "draft"

    def test_skip(self, env):
        env.user = env.admin
        sid = _seed_shortlist(env)
        assert env.client.post(f"/api/ops/shortlists/{sid}/skip").status_code == 200
        assert env.client.post(f"/api/ops/shortlists/{sid}/skip").status_code == 409

    def test_list_week(self, env):
        env.user = env.admin
        _seed_shortlist(env)
        d = env.client.get("/api/ops/shortlists").json()
        assert d["week_start"] == ops_copy.week_start(TODAY).isoformat()
        assert len(d["shortlists"]) == 1
        assert env.client.get("/api/ops/shortlists?week=bad").status_code == 400


# ---------------------------------------------------------------------------
# Crons
# ---------------------------------------------------------------------------
class TestDailyFocusCron:
    @pytest.fixture
    def cron(self, env, monkeypatch):
        mails = []

        async def send_email(**kw):
            mails.append(kw)
            return True

        monkeypatch.setattr(daily_focus.postmark_service, "send_email", send_email)
        return SimpleNamespace(env=env, mails=mails, pool=FakePool(env.conn))

    def _run(self, cron, **kw):
        return asyncio.run(daily_focus.run(now_flag=True, pool=cron.pool, **kw))

    def test_empty_list_sends_nothing(self, cron):
        cron.env.items.clear()
        assert self._run(cron)["status"] == "empty"
        assert cron.mails == [] and cron.env.conn.digest == {}

    def test_sends_once_per_day_to_admin_only(self, cron):
        assert self._run(cron)["status"] == "sent"
        assert len(cron.mails) == 1
        m = cron.mails[0]
        assert m["to"] == ops_copy.ADMIN_EMAIL and m["tag"] == "daily_focus"
        assert m["subject"] == "НабавкиДата фокус: 1 ставка денес"
        assert "--- нацрт ---" in m["text_content"] and "/api/ops/sent?k=" in m["text_content"]
        assert self._run(cron)["status"] == "already_sent"
        assert len(cron.mails) == 1
        assert self._run(cron, force=True)["status"] == "sent"
        assert len(cron.mails) == 2

    def test_wrong_hour_and_dry_run(self, cron):
        seven = datetime(2026, 10, 16, 5, 30, tzinfo=timezone.utc)  # 07:30 Skopje (CEST)
        r = asyncio.run(daily_focus.run(pool=cron.pool, now=seven))
        assert r["status"] == "wrong_hour" and cron.mails == []
        six = datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)   # 06:30 Skopje
        assert daily_focus.skopje_hour(six) == 6
        assert self._run(cron, dry_run=True)["status"] == "dry_run"
        assert cron.mails == [] and cron.env.conn.digest == {}


    def test_weekend_sends_nothing(self, cron, monkeypatch):
        from datetime import date
        monkeypatch.setattr(daily_focus.ops_copy, "today_skopje", lambda: date(2026, 10, 17))  # Saturday
        sat_six = datetime(2026, 10, 17, 4, 30, tzinfo=timezone.utc)  # 06:30 Skopje
        r = asyncio.run(daily_focus.run(pool=cron.pool, now=sat_six))
        assert r["status"] == "weekend" and cron.mails == []


class TestWeeklyShortlistCron:
    def test_builds_and_never_emails(self, env, monkeypatch):
        calls = []

        async def build_week(c, today, user_id=None):
            calls.append(today)
            return {"built": 2, "existing": 0, "no_candidates": 1}

        async def boom(**kw):
            raise AssertionError("weekly shortlist cron must not send email")

        monkeypatch.setattr(client_shortlist, "build_week", build_week)
        monkeypatch.setattr(api_ops, "send_one", boom)
        monkeypatch.setattr(daily_focus.postmark_service, "send_email", boom)
        r = asyncio.run(weekly_client_shortlist.run(pool=FakePool(env.conn)))
        assert r == {"built": 2, "existing": 0, "no_candidates": 1}
        assert calls == [TODAY]
