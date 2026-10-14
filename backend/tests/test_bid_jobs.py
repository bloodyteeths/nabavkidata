"""
Tests for Phase 2 of the done-for-you bid service: bid jobs, client portal and
admin console (api/bid_jobs.py) plus the email layer (services/bid_notifications.py).

No real database: get_asyncpg_pool in both modules is monkeypatched to a fake
pool backed by a small in-memory store (FakeDB) that understands exactly the
statements these modules issue — including the guarded status UPDATE, so the
transition rules are exercised for real. postmark_service.send_email is
replaced with a recorder. The app under test mounts only bid_jobs.router under
/api (main.py is never imported). Files land in tmp_path via BID_FILES_DIR.

Run:  cd backend && venv/bin/python -m pytest tests/test_bid_jobs.py -q --noconftest
"""
import asyncio
import json
import os
import re
import sys
import types
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-bid-jobs-tests")

# api/ai.py pushes ../ai onto sys.path[0], which shadows backend/db_pool.py with
# ai/db_pool.py. Import the backend module first so the cached one wins.
import db_pool  # noqa: E402,F401

# backend/__init__.py is a stray copy of api/__init__.py; pre-seed an inert module
# so pytest does not execute it (see tests/test_bid_service.py).
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

import middleware.rbac as rbac  # noqa: E402
from api import bid_jobs  # noqa: E402
from api.auth import get_current_user  # noqa: E402
from middleware.rbac import require_admin  # noqa: E402
from services import bid_notifications  # noqa: E402

TODAY = bid_jobs.today_skopje()


# ---------------------------------------------------------------------------
# In-memory fake database
# ---------------------------------------------------------------------------
def _norm(sql: str) -> str:
    return " ".join(sql.split())


def _split_top(s: str, sep: str = ",") -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


class FakeDB:
    def __init__(self):
        self.users: dict = {}
        self.tenders: dict = {}
        self.jobs: dict = {}
        self.files: dict = {}
        self.docs: dict = {}
        self.messages: dict = {}
        self.events: list = []
        self.alerts: list = []
        self.calls: list = []
        self.transactions = 0

    # seeding ---------------------------------------------------------------
    def add_user(self, **kw):
        uid = kw.pop("user_id", None) or uuid.uuid4()
        u = dict(user_id=uid, email=f"{uid.hex[:8]}@example.mk", full_name="Тест Корисник",
                 company_name="Тест ДООЕЛ", account_type="prospect", role="user",
                 free_drafting=False, prep_fee_mkd=30000, success_fee_pct=5.0,
                 calendar_token=None, terms_agreed_at=datetime.now(timezone.utc),
                 agreement_version=bid_jobs.AGREEMENT_VERSION)
        u.update(kw)
        self.users[uid] = u
        return u

    def add_tender(self, tender_id="17400/2026", status="open", closing_date="default", **kw):
        t = dict(tender_id=tender_id, title="Одржување на софтвер", procuring_entity="Министерство",
                 status=status, estimated_value_mkd=1000000,
                 closing_date=(TODAY + timedelta(days=10)) if closing_date == "default" else closing_date)
        t.update(kw)
        self.tenders[tender_id] = t
        return t

    def add_job(self, user_id, tender_id="17400/2026", status="requested", **kw):
        jid = uuid.uuid4()
        now = datetime.now()
        j = dict(id=jid, user_id=user_id, tender_id=tender_id, status=status, prep_fee_mkd=30000,
                 success_fee_pct=5.0, free=False, invoice_number=None, invoice_issued_at=None,
                 paid_at=None, assigned_to=None, admin_notes=None, client_note=None,
                 published_at=None, publish_count=0, reopen_count=0, approved_at=None,
                 submitted_at=None, outcome=None, outcome_at=None, cancelled_at=None,
                 cancelled_by=None, cancel_reason=None, created_at=now, updated_at=now,
                 invoice_file_path=None, invoice_file_name=None)
        j.update(kw)
        self.jobs[jid] = j
        return j

    def add_file(self, job_id, client_visible=True, approval_status="pending", **kw):
        fid = uuid.uuid4()
        f = dict(id=fid, job_id=job_id, kind="tehnicka", title="Техничка понуда",
                 storage_path=f"jobs/{job_id}/{uuid.uuid4().hex}.pdf",
                 original_name="tehnicka.pdf", mime="application/pdf", size_bytes=10,
                 client_visible=client_visible, approval_status=approval_status,
                 client_comment=None, reviewed_at=None, uploaded_by=None,
                 created_at=datetime.now(), updated_at=datetime.now())
        f.update(kw)
        self.files[fid] = f
        return f

    # helpers ---------------------------------------------------------------
    def _job_row(self, j, admin=False):
        t = self.tenders.get(j["tender_id"], {})
        row = dict(j)
        row.update(tender_title=t.get("title"), procuring_entity=t.get("procuring_entity"),
                   closing_date=t.get("closing_date"),
                   estimated_value_mkd=t.get("estimated_value_mkd"), tender_status=t.get("status"))
        vis = [f for f in self.files.values() if f["job_id"] == j["id"] and f["client_visible"]]
        row["files_visible"] = len(vis)
        row["files_pending_review"] = len([f for f in vis if f["approval_status"] == "pending"])
        row["unread_messages"] = 0
        if admin:
            u = self.users.get(j["user_id"], {})
            row.update(user_email=u.get("email"), company_name=u.get("company_name"),
                       assigned_to_email=None, total_count=1)
        return row

    def _eval(self, expr, job, params):
        expr = expr.strip()
        if expr == "NOW()":
            return datetime.now()
        if expr == "NULL":
            return None
        if expr == "TRUE":
            return True
        m = re.fullmatch(r"\$(\d+)(::\w+)?", expr)
        if m:
            return params[int(m.group(1)) - 1]
        m = re.fullmatch(r"'([^']*)'", expr)
        if m:
            return m.group(1)
        m = re.fullmatch(r"(\w+) \+ 1", expr)
        if m:
            return job[m.group(1)] + 1
        m = re.fullmatch(r"COALESCE\((.*)\)", expr)
        if m:
            for part in _split_top(m.group(1)):
                v = self._eval(part, job, params)
                if v is not None:
                    return v
            return None
        if re.fullmatch(r"\w+", expr):
            return job[expr]
        raise AssertionError(f"FakeDB cannot evaluate {expr!r}")

    def _transition(self, sql, params):
        m = re.match(r"UPDATE bid_jobs SET (.*?) WHERE id = \$1 AND status = ANY\(\$2::text\[\]\)(.*?)"
                     r" RETURNING \*", sql)
        assert m, sql
        set_part, where_rest = m.group(1), m.group(2)
        j = self.jobs.get(params[0])
        if not j or j["status"] not in params[1]:
            return None
        om = re.search(r"AND user_id = \$(\d+)", where_rest)
        if om and j["user_id"] != params[int(om.group(1)) - 1]:
            return None
        if "published_at IS NOT NULL" in where_rest and j["published_at"] is None:
            return None
        if re.search(r"AND outcome IS NULL", where_rest) and j["outcome"] is not None:
            return None
        if "cancelled_by = 'client'" in where_rest and j["cancelled_by"] != "client":
            return None
        if "(status <> 'cancelled' OR outcome IS NOT NULL)" in where_rest:
            if j["status"] == "cancelled" and j["outcome"] is None:
                return None
        new = dict(j)
        for assign in _split_top(set_part):
            col, expr = assign.split("=", 1)
            new[col.strip()] = self._eval(expr, j, params)
        j.update(new)
        return dict(j)

    # asyncpg surface ---------------------------------------------------------
    async def fetchrow(self, sql, *a):
        s = _norm(sql)
        self.calls.append(("fetchrow", s, a))
        if "FROM tenders WHERE tender_id = $1" in s:
            t = self.tenders.get(a[0])
            return dict(t) if t else None
        if s.startswith("SELECT id, status, outcome, cancelled_by, reopen_count,"):
            j = self._find_job(a[0], a[1])
            if not j:
                return None
            ca = j["cancelled_at"]
            if ca is not None and ca.tzinfo is None:
                ca = ca.astimezone()
            recent = ca is not None and ca > datetime.now(timezone.utc) - timedelta(minutes=a[2])
            return dict(j, recently_cancelled=recent)
        if "SELECT j.*" in s and "FROM bid_jobs j" in s:
            admin = "u.email AS user_email" in s
            if s.endswith("WHERE j.id = $1 AND j.user_id = $2"):
                j = self.jobs.get(a[0])
                return self._job_row(j) if j and j["user_id"] == a[1] else None
            if s.endswith("WHERE j.user_id = $1 AND j.tender_id = $2"):
                j = self._find_job(a[0], a[1])
                return self._job_row(j) if j else None
            if s.endswith("WHERE j.id = $1"):
                j = self.jobs.get(a[0])
                return self._job_row(j, admin=admin) if j else None
        if s.startswith("SELECT prep_fee_mkd, success_fee_pct, free_drafting"):
            return self.users.get(a[0])
        if s.startswith("SELECT user_id, account_type, role FROM users WHERE calendar_token = $1"):
            for u in self.users.values():
                if u["calendar_token"] and u["calendar_token"] == a[0]:
                    return u
            return None
        if s.startswith("SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS bytes FROM client_documents"):
            mine = [d for d in self.docs.values() if d["user_id"] == a[0]]
            return dict(n=len(mine), bytes=sum(d["size_bytes"] for d in mine))
        if s.startswith("SELECT invoice_number, invoice_file_path FROM bid_jobs WHERE id = $1"):
            j = self.jobs.get(a[0])
            return dict(j) if j else None
        if s.startswith("SELECT invoice_file_path, invoice_file_name FROM bid_jobs WHERE id = $1"):
            j = self.jobs.get(a[0])
            if j and len(a) > 1 and j["user_id"] != a[1]:
                return None
            return j
        if s.startswith("SELECT alert_id, criteria FROM tender_alerts"):
            alerts = [x for x in self.alerts if x["user_id"] == a[0]]
            return alerts[0] if alerts else None
        if s.startswith("SELECT paid_at, free FROM bid_jobs"):
            return dict(self.jobs[a[0]])
        if s.startswith("UPDATE bid_jobs SET status = $3"):
            return self._transition(s, a)
        if s.startswith("SELECT id, status FROM bid_jobs WHERE id = $1 AND user_id = $2"):
            j = self.jobs.get(a[0])
            return dict(j) if j and j["user_id"] == a[1] else None
        if s.startswith("SELECT id FROM bid_job_files WHERE id = $1 AND job_id = $2 AND client_visible"):
            f = self.files.get(a[0])
            return f if f and f["job_id"] == a[1] and f["client_visible"] else None
        if s.startswith("UPDATE bid_job_files SET approval_status = 'approved'"):
            f = self.files[a[0]]
            f.update(approval_status="approved", reviewed_at=datetime.now())
            return dict(f)
        if s.startswith("UPDATE bid_job_files SET approval_status = 'changes_requested'"):
            f = self.files[a[0]]
            f.update(approval_status="changes_requested", client_comment=a[1],
                     reviewed_at=datetime.now())
            return dict(f)
        if s.startswith("SELECT f.storage_path, f.mime, f.original_name FROM bid_job_files f"):
            f = self.files.get(a[0])
            j = self.jobs.get(a[1])
            if f and j and f["job_id"] == a[1] and j["user_id"] == a[2] and f["client_visible"]:
                return f
            return None
        if s.startswith("SELECT storage_path, mime, original_name FROM bid_job_files"):
            f = self.files.get(a[0])
            return f if f and f["job_id"] == a[1] else None
        if s.startswith("INSERT INTO bid_job_files"):
            fid = uuid.uuid4()
            f = dict(id=fid, job_id=a[0], kind=a[1], title=a[2], storage_path=a[3],
                     original_name=a[4], mime=a[5], size_bytes=a[6], uploaded_by=a[7],
                     client_visible=False, approval_status="pending", client_comment=None,
                     reviewed_at=None, created_at=datetime.now(), updated_at=datetime.now())
            self.files[fid] = f
            return dict(f)
        if s.startswith("INSERT INTO client_documents"):
            did = uuid.uuid4()
            d = dict(id=did, user_id=a[0], category=a[1], title=a[2], storage_path=a[3],
                     original_name=a[4], mime=a[5], size_bytes=a[6], expires_on=a[7],
                     uploaded_by_role="client", created_at=datetime.now(),
                     updated_at=datetime.now())
            self.docs[did] = d
            return dict(d)
        if s.startswith("SELECT storage_path, mime, original_name FROM client_documents"):
            d = self.docs.get(a[0])
            return d if d and d["user_id"] == a[1] else None
        if s.startswith("SELECT id, paid_at, prep_fee_mkd"):
            j = self.jobs.get(a[0])
            return dict(j) if j else None
        if s.startswith("SELECT user_id, email, full_name, company_name, account_type"):
            return self.users.get(a[0])
        if s.startswith("SELECT COUNT(*) AS total, COUNT(*) FILTER"):
            return dict(total=0, general=0)
        if s.startswith("SELECT account_type, company_name FROM users"):
            return self.users.get(a[0])
        # bid_notifications.load_context
        if s.startswith("SELECT j.id AS job_id, j.status"):
            j = self.jobs.get(a[0])
            if not j:
                return None
            t = self.tenders.get(j["tender_id"], {})
            u = self.users[j["user_id"]]
            comments = [{"title": f["title"], "comment": f["client_comment"]}
                        for f in self.files.values()
                        if f["job_id"] == j["id"] and f["approval_status"] == "changes_requested"]
            cycles = lambda ev: len([e for e in self.events  # noqa: E731
                                     if e["job_id"] == j["id"] and e["kind"] == "audit"
                                     and e["event"] == ev])
            return dict(job_id=j["id"], status=j["status"], outcome=j["outcome"],
                        changes_cycles=cycles("changes_requested"),
                        approved_cycles=cycles("approved"),
                        reopen_count=j["reopen_count"], publish_count=j["publish_count"],
                        tender_id=j["tender_id"], tender_title=t.get("title"),
                        procuring_entity=t.get("procuring_entity"),
                        closing_date=t.get("closing_date"), invoice_number=j["invoice_number"],
                        client_email=u["email"], client_name=u["full_name"],
                        company_name=u["company_name"], change_comments=json.dumps(comments))
        raise AssertionError(f"FakeDB.fetchrow: unhandled SQL: {s[:160]}")

    def _find_job(self, user_id, tender_id):
        for j in self.jobs.values():
            if j["user_id"] == user_id and j["tender_id"] == tender_id:
                return j
        return None

    async def fetchval(self, sql, *a):
        s = _norm(sql)
        self.calls.append(("fetchval", s, a))
        if s.startswith("SELECT COUNT(*) FROM bid_jobs j JOIN tenders t"):
            return 0
        if s.startswith("SELECT COUNT(*) FROM bid_job_events e JOIN bid_jobs j"):
            mine = {j["id"] for j in self.jobs.values() if j["user_id"] == a[0]}
            return len([e for e in self.events if e["job_id"] in mine and e["kind"] == "audit"
                        and e.get("actor_role") == "client"
                        and (e.get("detail") or {}).get("action") in ("begin", "reopen")])
        if s.startswith("SELECT invoice_file_path FROM bid_jobs WHERE id = $1"):
            return self.jobs[a[0]]["invoice_file_path"]
        if s.startswith("SELECT COUNT(*) FROM bid_messages WHERE sender_role = 'client'"):
            return 0
        if s.startswith("SELECT 1 FROM bid_jobs WHERE id = $1"):
            j = self.jobs.get(a[0])
            if not j:
                return None
            if len(a) > 1 and j["user_id"] != a[1]:
                return None
            return 1
        if s.startswith("INSERT INTO bid_jobs"):
            if self._find_job(a[0], a[1]):
                return None
            j = self.add_job(a[0], a[1], a[2], prep_fee_mkd=a[3], success_fee_pct=a[4], free=a[5],
                             client_note=a[6])
            return j["id"]
        if s.startswith("SELECT EXISTS (SELECT 1 FROM bid_job_files"):
            return any(f["job_id"] == a[0] and f["client_visible"]
                       and f["approval_status"] != "approved" for f in self.files.values())
        if s.startswith("SELECT COUNT(*) FROM bid_job_files WHERE job_id = $1 AND client_visible"):
            return len([f for f in self.files.values() if f["job_id"] == a[0] and f["client_visible"]])
        if s.startswith("SELECT COUNT(*) FROM bid_job_files WHERE job_id = $1"):
            return len([f for f in self.files.values() if f["job_id"] == a[0]])
        if s.startswith("SELECT COUNT(*) FROM client_documents"):
            return len([d for d in self.docs.values() if d["user_id"] == a[0]])
        if s.startswith("SELECT status FROM bid_jobs WHERE id = $1"):
            j = self.jobs.get(a[0])
            return j["status"] if j else None
        if s.startswith("SELECT user_id FROM users WHERE calendar_token = $1"):
            for u in self.users.values():
                if u["calendar_token"] and u["calendar_token"] == a[0]:
                    return u["user_id"]
            return None
        if s.startswith("SELECT calendar_token FROM users"):
            return self.users[a[0]]["calendar_token"]
        if s.startswith("UPDATE users SET calendar_token = COALESCE"):
            u = self.users[a[0]]
            u["calendar_token"] = u["calendar_token"] or a[1]
            return u["calendar_token"]
        if s.startswith("SELECT 1 FROM users WHERE user_id = $1 AND LOWER(role) = 'admin'"):
            u = self.users.get(a[0])
            return 1 if u and u["role"].lower() == "admin" else None
        if s.startswith("SELECT 1 FROM users WHERE user_id = $1"):
            return 1 if a[0] in self.users else None
        if s.startswith("SELECT COUNT(*) FROM bid_messages WHERE user_id = $1 AND sender_role = 'client'"):
            return len([m for m in self.messages.values()
                        if m["user_id"] == a[0] and m["sender_role"] == "client"])
        # bid_notifications.claim_notification
        if s.startswith("INSERT INTO bid_job_events (job_id, kind, event, actor_role) VALUES ($1,'notify'"):
            if any(e["kind"] == "notify" and e["job_id"] == a[0] and e["event"] == a[1]
                   for e in self.events):
                return None
            self.events.append(dict(id=len(self.events) + 1, job_id=a[0], kind="notify",
                                    event=a[1]))
            return len(self.events)
        raise AssertionError(f"FakeDB.fetchval: unhandled SQL: {s[:160]}")

    async def fetch(self, sql, *a):
        s = _norm(sql)
        self.calls.append(("fetch", s, a))
        if "SELECT j.*" in s and s.endswith("WHERE j.user_id = $1"):
            return [self._job_row(j) for j in self.jobs.values() if j["user_id"] == a[0]]
        if s.startswith("SELECT * FROM ( SELECT COUNT(*) OVER () AS total_count"):
            return [self._job_row(j, admin=True) for j in self.jobs.values()]
        if s.startswith("SELECT j.id, j.tender_id, j.status, j.outcome, t.title, t.closing_date"):
            out = []
            for j in self.jobs.values():
                t = self.tenders.get(j["tender_id"])
                if (j["user_id"] == a[0] and j["status"] not in ("cancelled", "lost", "won")
                        and t and t.get("closing_date")):
                    out.append(dict(id=j["id"], tender_id=j["tender_id"], status=j["status"],
                                    outcome=j["outcome"], title=t["title"],
                                    closing_date=t["closing_date"]))
            return out
        if s.startswith("SELECT * FROM bid_job_files WHERE job_id = $1"):
            return [dict(f) for f in self.files.values() if f["job_id"] == a[0]
                    and (f["client_visible"] or "client_visible" not in s)]
        if "FROM bid_messages m" in s:
            return []
        if "FROM alert_matches am" in s:
            return []
        if s.startswith("SELECT status, COUNT(*) AS n FROM bid_jobs"):
            counts: dict = {}
            for j in self.jobs.values():
                counts[j["status"]] = counts.get(j["status"], 0) + 1
            return [dict(status=k, n=v) for k, v in counts.items()]
        if "FROM client_documents" in s or "FROM bid_job_events" in s:
            return []
        raise AssertionError(f"FakeDB.fetch: unhandled SQL: {s[:160]}")

    async def execute(self, sql, *a):
        s = _norm(sql)
        self.calls.append(("execute", s, a))
        if s.startswith("INSERT INTO bid_job_events (job_id, kind, event, actor_role, detail) "
                        "VALUES ($1,'audit','notify_failed'"):
            self.events.append(dict(id=len(self.events) + 1, job_id=a[0], kind="audit",
                                    event="notify_failed", actor_role="system",
                                    detail=json.loads(a[1])))
            return "INSERT 0 1"
        if s.startswith("INSERT INTO bid_job_events"):
            self.events.append(dict(id=len(self.events) + 1, job_id=a[0], kind="audit",
                                    event=a[1], actor_role=a[2],
                                    detail=json.loads(a[4]) if a[4] else None))
            return "INSERT 0 1"
        if s.startswith("SELECT 1 FROM users WHERE user_id = $1 FOR UPDATE"):
            return "SELECT 1"
        if s.startswith("UPDATE users SET terms_agreed_at = NOW(), agreement_version = $2"):
            self.users[a[0]].update(terms_agreed_at=datetime.now(timezone.utc),
                                    agreement_version=a[1])
            return "UPDATE 1"
        if s.startswith("UPDATE users SET account_type = 'prospect'"):
            u = self.users[a[0]]
            if u["account_type"] == "free":
                u["account_type"] = "prospect"
            return "UPDATE 1"
        if s.startswith("UPDATE bid_jobs SET invoice_file_path = $2"):
            self.jobs[a[0]].update(invoice_file_path=a[1], invoice_file_name=a[2])
            return "UPDATE 1"
        if s.startswith("UPDATE bid_jobs SET invoice_file_path = NULL"):
            self.jobs[a[0]].update(invoice_file_path=None, invoice_file_name=None)
            return "UPDATE 1"
        if s.startswith("UPDATE tender_alerts SET criteria"):
            for x in self.alerts:
                if x["alert_id"] == a[0]:
                    x["criteria"] = {"keywords": json.loads(a[1])}
            return "UPDATE 1"
        if s.startswith("INSERT INTO tender_alerts"):
            self.alerts.append(dict(alert_id=uuid.uuid4(), user_id=a[0], name=a[1],
                                    criteria=json.loads(a[2])))
            return "INSERT 0 1"
        if s.startswith("UPDATE users SET account_type='managed_client'"):
            u = self.users.get(a[0])
            if u and u["account_type"] in ("free", "prospect"):
                u["account_type"] = "managed_client"
                return "UPDATE 1"
            return "UPDATE 0"
        if s.startswith("UPDATE bid_service_leads"):
            return "UPDATE 0"
        if s.startswith("UPDATE bid_jobs SET updated_at = NOW() WHERE id = $1"):
            return "UPDATE 1"
        if s.startswith("UPDATE bid_job_files SET approval_status = 'approved'"):
            n = 0
            only_pending = "approval_status = 'pending'" in s
            for f in self.files.values():
                if (f["job_id"] == a[0] and f["client_visible"] and f["approval_status"] != "approved"
                        and (not only_pending or f["approval_status"] == "pending")):
                    f.update(approval_status="approved", reviewed_at=datetime.now())
                    n += 1
            return f"UPDATE {n}"
        if s.startswith("UPDATE bid_job_files SET client_visible = TRUE"):
            for f in self.files.values():
                if f["job_id"] == a[0]:
                    f["client_visible"] = True
                    if f["approval_status"] == "changes_requested":
                        f["approval_status"] = "pending"
            return "UPDATE"
        if s.startswith("UPDATE bid_messages m SET"):
            return "UPDATE 0"
        if s.startswith("UPDATE users SET calendar_token = $2"):
            self.users[a[0]]["calendar_token"] = a[1]
            return "UPDATE 1"
        if s.startswith("UPDATE users SET"):
            return "UPDATE 1"
        raise AssertionError(f"FakeDB.execute: unhandled SQL: {s[:160]}")

    @asynccontextmanager
    async def _tx(self):
        self.transactions += 1
        yield

    def transaction(self):
        return self._tx()

    def find(self, needle):
        return [c for c in self.calls if needle in c[1]]

    def audit_events(self, job_id):
        return [e["event"] for e in self.events if e["job_id"] == job_id and e["kind"] == "audit"]


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


def _ns(u: dict) -> SimpleNamespace:
    return SimpleNamespace(user_id=u["user_id"], email=u["email"], role=u["role"],
                           account_type=u["account_type"], company_name=u["company_name"],
                           full_name=u["full_name"], email_verified=True, is_active=True,
                           subscription_tier="free")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def files_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BID_FILES_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def mail(monkeypatch):
    rec = MailRecorder()
    monkeypatch.setattr(bid_notifications.postmark_service, "send_email", rec)
    return rec


@pytest.fixture
def db(monkeypatch, mail, files_dir):
    fake = FakeDB()

    async def fake_get_pool():
        return FakePool(fake)

    monkeypatch.setattr(bid_jobs, "get_asyncpg_pool", fake_get_pool)
    monkeypatch.setattr(bid_notifications, "get_asyncpg_pool", fake_get_pool)
    return fake


@pytest.fixture
def make_client(db):
    """make_client(user_dict, admin=False) -> TestClient acting as that user."""

    def _make(user=None, admin=False, real_admin_check=False):
        app = FastAPI()
        app.include_router(bid_jobs.router, prefix="/api")
        if user is not None:
            app.dependency_overrides[get_current_user] = lambda: _ns(user)
            app.dependency_overrides[rbac.get_current_user] = lambda: _ns(user)
        if admin:
            admin_user = user or db.add_user(role="admin", account_type="free")
            app.dependency_overrides[require_admin] = lambda: _ns(admin_user)
        return TestClient(app)

    return _make


PRICE_RE = re.compile(r"МКД|MKD|денар|%|\d+\s*ден|\b30[.,]?000\b|надомест|износ", re.IGNORECASE)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\U0001F000-\U0001F2FF]")
API = "/api/bid-service"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
class TestPureHelpers:
    def test_is_portal_user(self):
        assert bid_jobs.is_portal_user("prospect", "user")
        assert bid_jobs.is_portal_user("managed_client", None)
        assert bid_jobs.is_portal_user("free", "ADMIN")
        assert not bid_jobs.is_portal_user("free", "user")
        assert not bid_jobs.is_portal_user(None, None)

    def test_phase_for_every_status(self):
        for s in bid_jobs.STATUSES:
            text, who = bid_jobs.phase_for(s, None)
            assert text and who in ("client", "us", "none")
        assert bid_jobs.phase_for("payment_required", None)[1] == "client"
        assert bid_jobs.phase_for("requested", None)[1] == "us"
        assert bid_jobs.phase_for("cancelled", "cancelled")[0] == "Договорниот орган ја поништи постапката."
        assert bid_jobs.phase_for("cancelled", None)[0] == "Барањето е откажано."

    def test_deadline_info(self):
        t = date(2026, 10, 14)
        assert bid_jobs.deadline_info(None, "ready", t) == (None, None)
        assert bid_jobs.deadline_info(date(2026, 10, 13), "ready", t) == (-1, "passed")
        assert bid_jobs.deadline_info(t, "ready", t) == (0, "today")
        assert bid_jobs.deadline_info(date(2026, 10, 17), "preparing", t) == (3, "soon")
        assert bid_jobs.deadline_info(date(2026, 10, 18), "preparing", t) == (4, "ok")
        # state only for pre-submitted statuses
        assert bid_jobs.deadline_info(date(2026, 10, 13), "submitted", t) == (-1, None)

    def test_tender_open_for_begin(self):
        t = date(2026, 10, 14)
        assert bid_jobs.tender_open_for_begin("open", t, t)
        assert bid_jobs.tender_open_for_begin("ACTIVE", None, t)
        assert bid_jobs.tender_open_for_begin(None, None, t)
        assert not bid_jobs.tender_open_for_begin("awarded", None, t)
        assert not bid_jobs.tender_open_for_begin("open", date(2026, 10, 13), t)

    def test_can_transition(self):
        assert bid_jobs.can_transition("requested", "payment_required")
        assert bid_jobs.can_transition("payment_required", "preparing")
        assert not bid_jobs.can_transition("requested", "approved")
        assert not bid_jobs.can_transition("preparing", "approved")
        assert not bid_jobs.can_transition("submitted", "ready")
        assert not bid_jobs.can_transition("bogus", "ready")

    def test_allowed_extension(self):
        assert bid_jobs.allowed_extension("Ponuda.PDF") == ".pdf"
        assert bid_jobs.allowed_extension("x.p7s") == ".p7s"
        assert bid_jobs.allowed_extension("evil.exe") is None
        assert bid_jobs.allowed_extension("evil.pdf.exe") is None
        assert bid_jobs.allowed_extension(None) is None
        assert bid_jobs.allowed_extension("noext") is None

    def test_safe_display_name(self):
        assert bid_jobs.safe_display_name("../../etc/passwd.pdf") == "passwd.pdf"
        assert bid_jobs.safe_display_name("C:\\Users\\x\\понуда.docx") == "понуда.docx"
        assert bid_jobs.safe_display_name("a\x00b\x1f  c.pdf") == "ab c.pdf"
        assert bid_jobs.safe_display_name("") == "dokument"
        assert bid_jobs.safe_display_name("..") == "dokument"
        assert bid_jobs.safe_display_name(None) == "dokument"
        assert len(bid_jobs.safe_display_name("a" * 500 + ".pdf")) == 200

    def test_resolve_storage_path_rejects_traversal(self, files_dir):
        ok = bid_jobs.resolve_storage_path("jobs/x/abc.pdf")
        assert str(ok).startswith(str(files_dir.resolve()))
        for bad in ("../outside.pdf", "jobs/../../outside.pdf", "/etc/passwd", ""):
            with pytest.raises(ValueError):
                bid_jobs.resolve_storage_path(bad)

    def test_files_root_reads_env_at_call_time(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BID_FILES_DIR", str(tmp_path / "a"))
        assert bid_jobs.files_root() == tmp_path / "a"
        monkeypatch.setenv("BID_FILES_DIR", str(tmp_path / "b"))
        assert bid_jobs.files_root() == tmp_path / "b"

    def test_job_summary_shape(self):
        row = dict(id=uuid.uuid4(), tender_id="1/2026", status="ready", outcome=None,
                   prep_fee_mkd=30000, free=False, created_at=datetime(2026, 10, 1),
                   updated_at=datetime(2026, 10, 2), tender_title="T", procuring_entity="P",
                   closing_date=date(2026, 10, 15), estimated_value_mkd=None,
                   unread_messages=2, files_pending_review=1)
        s = bid_jobs.job_summary(row, date(2026, 10, 14))
        assert s["whose_move"] == "client" and s["deadline_state"] == "soon"
        assert s["closing_date"] == "2026-10-15" and s["days_left"] == 1
        assert s["id"] == str(row["id"]) and s["unread_messages"] == 2
        assert set(s) == {"id", "tender_id", "tender_title", "procuring_entity", "closing_date",
                          "estimated_value_mkd", "status", "outcome", "phase_text", "whose_move",
                          "days_left", "deadline_state", "prep_fee_mkd", "free",
                          "unread_messages", "files_pending_review", "created_at", "updated_at"}


class TestBuildIcs:
    def test_escaping_folding_and_structure(self):
        now = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
        ev = dict(uid="abc-deadline", date=date(2026, 10, 20),
                  summary="Рок: 1/2026 Набавка; со, запирки\\и\nнов ред " + "Д" * 80,
                  description="опис", url="https://nabavkidata.com/portal/bid/abc")
        out = bid_jobs.build_ics([ev], now)
        assert out.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n")
        assert "PRODID:-//NabavkiData//Rokovi//MK" in out
        assert "UID:abc-deadline@nabavkidata.com" in out
        assert "DTSTAMP:20261014T100000Z" in out
        assert "DTSTART;VALUE=DATE:20261020" in out and "DTEND;VALUE=DATE:20261021" in out
        unfolded = out.replace("\r\n ", "")
        assert "Набавка\\; со\\, запирки\\\\и\\nнов ред" in unfolded
        assert out.endswith("END:VCALENDAR\r\n")
        for line in out.split("\r\n"):
            assert len(line.encode("utf-8")) <= 75
        # no bare LF anywhere
        assert "\n" not in out.replace("\r\n", "")


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
class TestAccessControl:
    def test_free_user_blocked_from_portal_without_db(self, db, make_client):
        u = db.add_user(account_type="free")
        c = make_client(u)
        for method, path in [("get", "/jobs"), ("get", "/portal/summary"), ("get", "/documents"),
                             ("get", "/messages"), ("get", "/deadlines"),
                             ("get", "/calendar-token")]:
            r = getattr(c, method)(API + path)
            assert r.status_code == 403, path
            assert "Порталот" in r.json()["detail"]
        r = c.post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 403
        assert db.calls == []

    def test_other_users_job_is_404(self, db, make_client):
        owner = db.add_user()
        intruder = db.add_user()
        db.add_tender()
        job = db.add_job(owner["user_id"], status="ready", published_at=datetime.now())
        f = db.add_file(job["id"])
        c = make_client(intruder)
        jid, fid = job["id"], f["id"]
        assert c.get(f"{API}/jobs/{jid}").status_code == 404
        assert c.get(f"{API}/jobs/{jid}/files/{fid}/download").status_code == 404
        assert c.post(f"{API}/jobs/{jid}/files/{fid}/approve").status_code == 404
        assert c.post(f"{API}/jobs/{jid}/files/{fid}/request-changes",
                      json={"comment": "x"}).status_code == 404
        assert c.post(f"{API}/jobs/{jid}/approve-all").status_code == 404
        assert c.post(f"{API}/jobs/{jid}/mark-submitted").status_code == 404
        assert c.post(f"{API}/jobs/{jid}/cancel", json={}).status_code == 404
        assert c.get(f"{API}/jobs/{jid}/messages").status_code == 404
        # nothing changed
        assert job["status"] == "ready" and f["approval_status"] == "pending"

    def test_admin_sees_only_own_jobs_through_client_endpoints(self, db, make_client):
        owner = db.add_user()
        admin = db.add_user(role="admin", account_type="free")
        db.add_tender()
        job = db.add_job(owner["user_id"])
        assert make_client(admin).get(f"{API}/jobs/{job['id']}").status_code == 404

    def test_admin_endpoints_reject_non_admin(self, db, make_client):
        u = db.add_user(account_type="managed_client")
        db.add_tender()
        job = db.add_job(u["user_id"])
        c = make_client(u)  # require_admin NOT overridden -> real check on role
        for method, path, kw in [
            ("get", "/admin/jobs", {}),
            ("get", "/admin/summary", {}),
            ("get", f"/admin/jobs/{job['id']}", {}),
            ("post", f"/admin/jobs/{job['id']}/mark-paid", {"json": {}}),
            ("post", f"/admin/jobs/{job['id']}/mark-free", {}),
            ("post", f"/admin/jobs/{job['id']}/publish", {}),
            ("post", f"/admin/jobs/{job['id']}/invoice",
             {"json": {"prep_fee_mkd": 1, "invoice_number": "1"}}),
            ("get", "/admin/inbox", {}),
            ("get", "/admin/team", {}),
            ("patch", f"/admin/clients/{u['user_id']}", {"json": {"free_drafting": True}}),
        ]:
            r = getattr(c, method)(API + path, **kw)
            assert r.status_code == 403, (path, r.status_code)
        assert job["status"] == "requested" and u["account_type"] == "managed_client"

    def test_calendar_feed_is_public_and_token_scoped(self, db, make_client):
        u = db.add_user(calendar_token="tok_" + "a" * 30)
        db.add_tender()
        db.add_tender("2/2026", closing_date=None)
        db.add_job(u["user_id"], status="preparing")
        db.add_job(u["user_id"], tender_id="2/2026")  # no closing date -> omitted
        c = make_client(None)  # no auth override at all
        r = c.get(f"{API}/calendar/tok_{'a' * 30}.ics")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/calendar")
        assert "charset=utf-8" in r.headers["content-type"]
        assert r.text.count("BEGIN:VEVENT") == 1
        assert "Рок: 17400/2026" in r.text.replace("\r\n ", "")
        assert c.get(f"{API}/calendar/wrong-token.ics").status_code == 404
        assert c.get(f"{API}/calendar/{'x' * 80}.ics").status_code == 404

    def test_calendar_token_create_and_rotate(self, db, make_client):
        u = db.add_user()
        c = make_client(u)
        r = c.get(API + "/calendar-token").json()
        assert r["token"] and r["url"].endswith(f"/api/bid-service/calendar/{r['token']}.ics")
        assert r["webcal_url"].startswith("webcal://")
        assert c.get(API + "/calendar-token").json()["token"] == r["token"]
        r2 = c.post(API + "/calendar-token/rotate").json()
        assert r2["token"] != r["token"] and u["calendar_token"] == r2["token"]


# ---------------------------------------------------------------------------
# Begin / reopen
# ---------------------------------------------------------------------------
class TestBegin:
    def test_closed_tender_rejected(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender(closing_date=TODAY - timedelta(days=1))
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 409
        assert "истече" in r.json()["detail"]
        assert db.jobs == {} and mail.sent == []

    def test_awarded_tender_rejected(self, db, make_client):
        u = db.add_user()
        db.add_tender(status="awarded")
        assert make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"}).status_code == 409

    def test_missing_tender_404(self, db, make_client):
        u = db.add_user()
        r = make_client(u).post(API + "/jobs", json={"tender_id": "nope"})
        assert r.status_code == 404 and r.json()["detail"] == "Тендерот не е пронајден."

    def test_invalid_body_422(self, db, make_client):
        u = db.add_user()
        c = make_client(u)
        assert c.post(API + "/jobs", json={}).status_code == 422
        assert c.post(API + "/jobs", json={"tender_id": ""}).status_code == 422
        assert c.post(API + "/jobs", json={"tender_id": "x" * 101}).status_code == 422
        assert c.post(API + "/jobs", json={"tender_id": "1", "client_note": "x" * 2001}).status_code == 422

    def test_new_job_snapshots_fees_and_notifies_admin(self, db, make_client, mail):
        u = db.add_user(prep_fee_mkd=45000, success_fee_pct=4.5)
        db.add_tender()
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["created"] is True
        assert body["job"]["status"] == "requested" and body["job"]["whose_move"] == "us"
        job = next(iter(db.jobs.values()))
        assert job["prep_fee_mkd"] == 45000 and job["success_fee_pct"] == 4.5
        assert job["free"] is False
        sent = mail.by_tag("bid-job-job_requested")
        assert len(sent) == 1 and sent[0]["to"] == bid_notifications.ADMIN_EMAIL

    def test_duplicate_begin_returns_existing_without_email(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        c = make_client(u)
        first = c.post(API + "/jobs", json={"tender_id": "17400/2026"}).json()
        second = c.post(API + "/jobs", json={"tender_id": "17400/2026"}).json()
        assert second["created"] is False and second["job"]["id"] == first["job"]["id"]
        assert len(db.jobs) == 1
        assert len(mail.by_tag("bid-job-job_requested")) == 1

    def test_existing_job_returned_even_after_tender_closed(self, db, make_client):
        u = db.add_user()
        db.add_tender(closing_date=TODAY - timedelta(days=2))
        job = db.add_job(u["user_id"], status="submitted")
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 200 and r.json()["job"]["id"] == str(job["id"])

    def test_free_drafting_skips_payment(self, db, make_client, mail):
        u = db.add_user(free_drafting=True)
        db.add_tender()
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.json()["job"]["status"] == "preparing" and r.json()["job"]["free"] is True
        assert len(mail.by_tag("bid-job-job_requested")) == 1

    def test_reopen_cancelled_job(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="cancelled", cancelled_by="client",
                         cancelled_at=datetime.now() - timedelta(hours=1), cancel_reason="x",
                         paid_at=datetime.now())
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 200 and r.json()["created"] is True
        assert job["status"] == "preparing"  # already paid -> straight to preparing
        assert job["reopen_count"] == 1 and job["cancelled_at"] is None
        assert job["cancelled_by"] is None and job["cancel_reason"] is None
        # reopen_count is part of the key, so the admin hears about the reopen
        assert len(mail.by_tag("bid-job-job_requested")) == 1

    def test_tender_cancelled_job_is_not_reopened(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="cancelled", outcome="cancelled")
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.json()["created"] is False and job["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Status machine through the endpoints
# ---------------------------------------------------------------------------
class TestTransitions:
    def test_client_cannot_approve_before_ready(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="preparing")
        f = db.add_file(job["id"], client_visible=False)
        c = make_client(u)
        # unpublished file is invisible to the client
        assert c.post(f"{API}/jobs/{job['id']}/files/{f['id']}/approve").status_code == 404
        # approve-all on a preparing job is a status error
        r = c.post(f"{API}/jobs/{job['id']}/approve-all")
        assert r.status_code == 409 and r.json()["detail"] == bid_jobs.ERR_WRONG_STATUS
        assert c.post(f"{API}/jobs/{job['id']}/mark-submitted").status_code == 409
        assert job["status"] == "preparing" and f["approval_status"] == "pending"

    def test_mark_submitted_requires_publish(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="ready", published_at=None)
        assert make_client(u).post(f"{API}/jobs/{job['id']}/mark-submitted").status_code == 409

    def test_full_happy_path_with_promotion(self, db, make_client, mail):
        client_user = db.add_user(account_type="prospect")
        admin_user = db.add_user(role="admin", account_type="free")
        db.add_tender()
        job = db.add_job(client_user["user_id"])
        jid = job["id"]
        admin = make_client(admin_user, admin=True)
        client = make_client(client_user)

        # cannot mark paid before invoice
        assert admin.post(f"{API}/admin/jobs/{jid}/mark-paid", json={}).status_code == 409
        # cannot publish while requested
        assert admin.post(f"{API}/admin/jobs/{jid}/publish").status_code == 409

        r = admin.post(f"{API}/admin/jobs/{jid}/invoice",
                       json={"prep_fee_mkd": 25000, "invoice_number": "INV-7/2026"})
        assert r.status_code == 200, r.text
        assert job["status"] == "payment_required" and job["prep_fee_mkd"] == 25000
        assert r.json()["job"]["status"] == "payment_required"

        r = admin.post(f"{API}/admin/jobs/{jid}/mark-paid", json={"paid_at": "2026-10-10"})
        assert r.status_code == 200, r.text
        assert r.json()["account_promoted"] is True
        assert client_user["account_type"] == "managed_client"
        assert job["status"] == "preparing"
        assert job["paid_at"] == datetime(2026, 10, 10, 12, 0, tzinfo=ZoneInfo("Europe/Skopje"))
        assert db.find("UPDATE bid_service_leads SET status='client'")

        # fee locked after payment
        assert admin.patch(f"{API}/admin/jobs/{jid}", json={"prep_fee_mkd": 1}).status_code == 409

        # publish with no files -> 400
        r = admin.post(f"{API}/admin/jobs/{jid}/publish")
        assert r.status_code == 400 and r.json()["detail"] == "Нема прикачени документи."

        f1 = db.add_file(jid, client_visible=False)
        f2 = db.add_file(jid, client_visible=False, kind="finansiska")
        r = admin.post(f"{API}/admin/jobs/{jid}/publish")
        assert r.status_code == 200, r.text
        assert job["status"] == "ready" and job["publish_count"] == 1
        assert f1["client_visible"] and f2["client_visible"]

        detail = client.get(f"{API}/jobs/{jid}").json()
        assert detail["job"]["can_approve_all"] is True
        assert detail["payment"]["required"] is False
        assert {f["id"] for f in detail["files"]} == {str(f1["id"]), str(f2["id"])}
        assert all("storage_path" not in f for f in detail["files"])

        # approving one of two keeps the job in ready; the last one flips it
        r = client.post(f"{API}/jobs/{jid}/files/{f1['id']}/approve")
        assert r.status_code == 200 and job["status"] == "ready"
        r = client.post(f"{API}/jobs/{jid}/files/{f2['id']}/approve")
        assert r.status_code == 200 and job["status"] == "approved"
        assert job["approved_at"] is not None

        r = client.post(f"{API}/jobs/{jid}/mark-submitted")
        assert r.status_code == 200 and job["status"] == "submitted"

        # client cannot cancel after submission
        assert client.post(f"{API}/jobs/{jid}/cancel", json={}).status_code == 409

        r = admin.post(f"{API}/admin/jobs/{jid}/outcome", json={"outcome": "won"})
        assert r.status_code == 200 and job["status"] == "won" and job["outcome"] == "won"

        tags = [m["tag"] for m in mail.sent]
        assert tags == ["bid-job-invoice_issued", "bid-job-preparing", "bid-job-ready",
                        "bid-job-approved", "bid-job-submitted", "bid-job-won"]
        events = db.audit_events(jid)
        for e in ("invoice_issued", "paid", "published", "file_approved", "approved", "submitted",
                  "won"):
            assert e in events, e

    def test_mark_free_promotes_and_skips_payment(self, db, make_client, mail):
        u = db.add_user(account_type="prospect")
        db.add_tender()
        job = db.add_job(u["user_id"])
        r = make_client(admin=True).post(f"{API}/admin/jobs/{job['id']}/mark-free")
        assert r.status_code == 200 and r.json()["account_promoted"] is True
        assert job["status"] == "preparing" and job["free"] is True
        assert u["account_type"] == "managed_client"
        assert len(mail.by_tag("bid-job-preparing")) == 1

    def test_mark_paid_does_not_demote_managed_client(self, db, make_client):
        u = db.add_user(account_type="managed_client")
        db.add_tender()
        job = db.add_job(u["user_id"], status="payment_required")
        r = make_client(admin=True).post(f"{API}/admin/jobs/{job['id']}/mark-paid", json={})
        assert r.json()["account_promoted"] is False and u["account_type"] == "managed_client"

    def test_request_changes_then_republish(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="ready", publish_count=1, published_at=datetime.now())
        f1, f2 = db.add_file(job["id"]), db.add_file(job["id"])
        c = make_client(u)
        r = c.post(f"{API}/jobs/{job['id']}/files/{f1['id']}/request-changes",
                   json={"comment": "Сменете го рокот"})
        assert r.status_code == 200 and job["status"] == "changes_requested"
        r = c.post(f"{API}/jobs/{job['id']}/files/{f2['id']}/request-changes",
                   json={"comment": "Друга забелешка"})
        assert r.status_code == 200 and job["status"] == "changes_requested"
        # same transition twice -> exactly one admin email
        sent = mail.by_tag("bid-job-changes_requested")
        assert len(sent) == 1
        assert "Сменете го рокот" in sent[0]["html"]

        # empty comment rejected
        assert c.post(f"{API}/jobs/{job['id']}/files/{f1['id']}/request-changes",
                      json={"comment": ""}).status_code == 422

        # admin republishes -> files reset to pending, new cycle -> ready email again
        r = make_client(admin=True).post(f"{API}/admin/jobs/{job['id']}/publish")
        assert r.status_code == 200 and job["status"] == "ready" and job["publish_count"] == 2
        assert f1["approval_status"] == "pending" and f2["approval_status"] == "pending"
        assert len(mail.by_tag("bid-job-ready")) == 1
        # a request-changes in the new cycle notifies again
        c.post(f"{API}/jobs/{job['id']}/files/{f1['id']}/request-changes", json={"comment": "x"})
        assert len(mail.by_tag("bid-job-changes_requested")) == 2

    def test_approve_all(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="ready", published_at=datetime.now())
        f1, f2 = db.add_file(job["id"]), db.add_file(job["id"])
        hidden = db.add_file(job["id"], client_visible=False)
        c = make_client(u)
        r = c.post(f"{API}/jobs/{job['id']}/approve-all")
        assert r.status_code == 200 and job["status"] == "approved"
        assert f1["approval_status"] == f2["approval_status"] == "approved"
        assert hidden["approval_status"] == "pending"
        # idempotent no-op in approved
        assert c.post(f"{API}/jobs/{job['id']}/approve-all").status_code == 200
        assert len(mail.by_tag("bid-job-approved")) == 1

    def test_approve_all_without_visible_files_409(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="ready")
        assert make_client(u).post(f"{API}/jobs/{job['id']}/approve-all").status_code == 409

    def test_client_cancel_and_admin_cancel(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        db.add_tender("2/2026")
        j1 = db.add_job(u["user_id"], status="preparing")
        j2 = db.add_job(u["user_id"], tender_id="2/2026", status="payment_required")
        r = make_client(u).post(f"{API}/jobs/{j1['id']}/cancel", json={"reason": "Не сме заинтересирани"})
        assert r.status_code == 200 and j1["status"] == "cancelled"
        assert j1["cancelled_by"] == "client" and j1["cancel_reason"] == "Не сме заинтересирани"
        r = make_client(admin=True).post(f"{API}/admin/jobs/{j2['id']}/cancel")
        assert r.status_code == 200 and j2["cancelled_by"] == "admin"
        assert len(mail.by_tag("bid-job-cancelled_by_client")) == 1
        assert len(mail.by_tag("bid-job-cancelled_by_admin")) == 1
        assert make_client(u).post(f"{API}/jobs/{j1['id']}/cancel",
                                   json={"reason": "x" * 1001}).status_code == 422

    def test_outcome_not_allowed_on_client_cancelled_job(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="cancelled", outcome=None)
        r = make_client(admin=True).post(f"{API}/admin/jobs/{job['id']}/outcome",
                                         json={"outcome": "won"})
        assert r.status_code == 409 and job["status"] == "cancelled"

    def test_outcome_rejects_bad_value_and_missing_job(self, db, make_client):
        c = make_client(admin=True)
        assert c.post(f"{API}/admin/jobs/{uuid.uuid4()}/outcome",
                      json={"outcome": "maybe"}).status_code == 422
        assert c.post(f"{API}/admin/jobs/{uuid.uuid4()}/outcome",
                      json={"outcome": "won"}).status_code == 404

    def test_invoice_validation(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"])
        c = make_client(admin=True)
        assert c.post(f"{API}/admin/jobs/{job['id']}/invoice",
                      json={"prep_fee_mkd": 0, "invoice_number": "1"}).status_code == 422
        assert c.post(f"{API}/admin/jobs/{job['id']}/invoice",
                      json={"prep_fee_mkd": 100, "invoice_number": ""}).status_code == 422
        assert c.post(f"{API}/admin/jobs/not-a-uuid/invoice",
                      json={"prep_fee_mkd": 100, "invoice_number": "1"}).status_code == 422

    def test_assign_requires_admin_target(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"])
        c = make_client(admin=True)
        r = c.post(f"{API}/admin/jobs/{job['id']}/assign", json={"assigned_to": str(u["user_id"])})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
class TestFiles:
    def _job(self, db, status="preparing"):
        u = db.add_user()
        db.add_tender()
        return u, db.add_job(u["user_id"], status=status)

    def test_admin_upload_sanitises_name_and_stays_hidden(self, db, make_client, files_dir):
        _, job = self._job(db)
        c = make_client(admin=True)
        r = c.post(f"{API}/admin/jobs/{job['id']}/files",
                   files={"file": ("../../../etc/понуда.pdf", b"%PDF-1.4 test", "application/pdf")},
                   data={"kind": "tehnicka"})
        assert r.status_code == 200, r.text
        f = r.json()["file"]
        assert f["original_name"] == "понуда.pdf" and f["title"] == "понуда"
        assert f["client_visible"] is False and f["size_bytes"] == len(b"%PDF-1.4 test")
        assert "storage_path" not in f
        row = db.files[uuid.UUID(f["id"])]
        assert re.fullmatch(rf"jobs/{job['id']}/[0-9a-f]{{32}}\.pdf", row["storage_path"])
        on_disk = list(files_dir.rglob("*.pdf"))
        assert len(on_disk) == 1
        assert files_dir.resolve() in on_disk[0].resolve().parents
        # downloadable by admin
        d = c.get(f"{API}/admin/jobs/{job['id']}/files/{f['id']}/download")
        assert d.status_code == 200 and d.content == b"%PDF-1.4 test"

    def test_extension_whitelist(self, db, make_client, files_dir):
        _, job = self._job(db)
        c = make_client(admin=True)
        for name in ("evil.exe", "script.pdf.sh", "noext", "page.html"):
            r = c.post(f"{API}/admin/jobs/{job['id']}/files",
                       files={"file": (name, b"x", "application/octet-stream")},
                       data={"kind": "drugo"})
            assert r.status_code == 400, name
            assert r.json()["detail"].startswith("Дозволени формати")
        assert db.files == {} and list(files_dir.rglob("*.*")) == []

    def test_bad_kind_rejected(self, db, make_client):
        _, job = self._job(db)
        r = make_client(admin=True).post(f"{API}/admin/jobs/{job['id']}/files",
                                         files={"file": ("a.pdf", b"x", "application/pdf")},
                                         data={"kind": "virus"})
        assert r.status_code == 400

    def test_size_limit_413_and_partial_removed(self, db, make_client, files_dir, monkeypatch):
        monkeypatch.setattr(bid_jobs, "MAX_FILE_BYTES", 3 * 1024 * 1024)
        _, job = self._job(db)
        c = make_client(admin=True)
        big = b"0" * (3 * 1024 * 1024 + 1)
        r = c.post(f"{API}/admin/jobs/{job['id']}/files",
                   files={"file": ("big.pdf", big, "application/pdf")}, data={"kind": "drugo"})
        assert r.status_code == 413 and r.json()["detail"] == "Датотеката е поголема од 25 MB."
        assert db.files == {}
        assert [p for p in files_dir.rglob("*") if p.is_file()] == []
        # exactly at the limit is fine
        ok = b"0" * (3 * 1024 * 1024)
        r = c.post(f"{API}/admin/jobs/{job['id']}/files",
                   files={"file": ("ok.pdf", ok, "application/pdf")}, data={"kind": "drugo"})
        assert r.status_code == 200

    def test_upload_blocked_on_terminal_job(self, db, make_client, files_dir):
        _, job = self._job(db, status="won")
        r = make_client(admin=True).post(f"{API}/admin/jobs/{job['id']}/files",
                                         files={"file": ("a.pdf", b"x", "application/pdf")},
                                         data={"kind": "drugo"})
        assert r.status_code == 409
        assert [p for p in files_dir.rglob("*") if p.is_file()] == []

    def test_client_downloads_only_visible_files(self, db, make_client, files_dir):
        u, job = self._job(db, status="ready")
        visible = db.add_file(job["id"], client_visible=True, original_name="v.pdf")
        hidden = db.add_file(job["id"], client_visible=False, original_name="h.pdf")
        for f in (visible, hidden):
            p = files_dir / f["storage_path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"content-" + f["original_name"].encode())
        c = make_client(u)
        r = c.get(f"{API}/jobs/{job['id']}/files/{visible['id']}/download")
        assert r.status_code == 200 and r.content == b"content-v.pdf"
        assert c.get(f"{API}/jobs/{job['id']}/files/{hidden['id']}/download").status_code == 404
        # hidden file never listed for the client
        ids = [f["id"] for f in c.get(f"{API}/jobs/{job['id']}").json()["files"]]
        assert ids == [str(visible["id"])]

    def test_missing_file_on_disk_is_404(self, db, make_client, files_dir):
        u, job = self._job(db, status="ready")
        f = db.add_file(job["id"])
        r = make_client(u).get(f"{API}/jobs/{job['id']}/files/{f['id']}/download")
        assert r.status_code == 404 and r.json()["detail"] == bid_jobs.ERR_FILE_NOT_FOUND

    def test_tampered_storage_path_never_served(self, db, make_client, files_dir, tmp_path_factory):
        outside = tmp_path_factory.mktemp("outside") / "secret.pdf"
        outside.write_bytes(b"secret")
        u, job = self._job(db, status="ready")
        f = db.add_file(job["id"], storage_path=os.path.relpath(outside, files_dir))
        r = make_client(u).get(f"{API}/jobs/{job['id']}/files/{f['id']}/download")
        assert r.status_code == 404

    def test_client_document_upload_and_library(self, db, make_client, files_dir):
        u = db.add_user()
        c = make_client(u)
        r = c.post(API + "/documents",
                   files={"file": ("..\\..\\Тековна состојба.pdf", b"%PDF", "application/pdf")},
                   data={"category": "tekovna_sostojba",
                         "expires_on": (TODAY + timedelta(days=10)).isoformat()})
        assert r.status_code == 200, r.text
        d = r.json()["document"]
        assert d["original_name"] == "Тековна состојба.pdf" and d["title"] == "Тековна состојба"
        assert d["expires_soon"] is True and d["expired"] is False
        row = db.docs[uuid.UUID(d["id"])]
        assert row["storage_path"].startswith(f"company/{u['user_id']}/")
        # bad category / extension / date
        assert c.post(API + "/documents", files={"file": ("a.pdf", b"x", "application/pdf")},
                      data={"category": "bogus"}).status_code == 400
        assert c.post(API + "/documents", files={"file": ("a.exe", b"x", "application/pdf")},
                      data={"category": "drugo"}).status_code == 400
        assert c.post(API + "/documents", files={"file": ("a.pdf", b"x", "application/pdf")},
                      data={"category": "drugo", "expires_on": "31.12.2026"}).status_code == 400
        # another client cannot download it
        other = make_client(db.add_user())
        assert other.get(f"{API}/documents/{d['id']}/download").status_code == 404
        assert c.get(f"{API}/documents/{d['id']}/download").content == b"%PDF"

    def test_document_limit(self, db, make_client, monkeypatch):
        monkeypatch.setattr(bid_jobs, "MAX_DOCUMENTS_PER_USER", 1)
        u = db.add_user()
        c = make_client(u)
        up = lambda: c.post(API + "/documents",  # noqa: E731
                            files={"file": ("a.pdf", b"x", "application/pdf")},
                            data={"category": "drugo"})
        assert up().status_code == 200
        r = up()
        assert r.status_code == 400 and "максималниот" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
def _ctx(**kw):
    base = dict(job_id=str(uuid.uuid4()), status="ready", outcome=None, reopen_count=0,
                publish_count=1, tender_id="17400/2026",
                tender_title="Одржување на софтвер за субвенции", procuring_entity="МЕРМС",
                closing_date=date(2026, 10, 22), invoice_number="INV-12/2026",
                client_email="client@example.mk", client_name="Клиент",
                company_name="Клиент ДООЕЛ",
                change_comments=[{"title": "Финансиска", "comment": "проверете"}])
    base.update(kw)
    return base


class TestNotifications:
    def test_notification_key(self):
        assert bid_notifications.notification_key("ready", 0, 2) == "ready:0:2"
        assert bid_notifications.notification_key("job_requested", None, None) == "job_requested:0:0"

    @pytest.mark.parametrize("kind", sorted(bid_notifications.KINDS))
    def test_render_email_has_no_prices_or_emojis(self, kind):
        subject, html_body = bid_notifications.render_email(kind, _ctx())
        text = subject + " " + html_body
        assert not PRICE_RE.search(text), (kind, PRICE_RE.search(text))
        assert not EMOJI_RE.search(text), kind
        assert "nabavkidata.com" in html_body
        if bid_notifications.KINDS[kind] == "client":
            assert "/portal/bid/" in html_body and "Почитувани," in html_body
        else:
            assert "/admin/bids/" in html_body

    def test_render_email_escapes_html(self):
        _, html_body = bid_notifications.render_email(
            "ready", _ctx(tender_title="<script>alert(1)</script>"))
        assert "<script>" not in html_body and "&lt;script&gt;" in html_body

    def test_ready_email_includes_deadline(self):
        _, html_body = bid_notifications.render_email("ready", _ctx())
        assert "22.10.2026" in html_body

    def test_notify_dedupe_with_monkeypatched_parts(self, monkeypatch, mail):
        claimed: set = set()

        async def fake_pool():
            return FakePool(object())

        async def fake_load(conn, job_id):
            return _ctx(job_id=job_id)

        async def fake_claim(conn, job_id, key):
            if (job_id, key) in claimed:
                return False
            claimed.add((job_id, key))
            return True

        monkeypatch.setattr(bid_notifications, "get_asyncpg_pool", fake_pool)
        monkeypatch.setattr(bid_notifications, "load_context", fake_load)
        monkeypatch.setattr(bid_notifications, "claim_notification", fake_claim)
        jid = str(uuid.uuid4())
        assert asyncio.run(bid_notifications.notify(jid, "ready")) is True
        assert asyncio.run(bid_notifications.notify(jid, "ready")) is False
        assert len(mail.sent) == 1 and mail.sent[0]["to"] == "client@example.mk"
        assert mail.sent[0]["reply_to"] == bid_notifications.REPLY_TO
        # unknown kind / missing job never send
        assert asyncio.run(bid_notifications.notify(jid, "bogus")) is False

        async def none_load(conn, job_id):
            return None
        monkeypatch.setattr(bid_notifications, "load_context", none_load)
        assert asyncio.run(bid_notifications.notify(jid, "won")) is False
        assert len(mail.sent) == 1

    def test_notify_never_raises(self, monkeypatch, mail):
        async def boom():
            raise RuntimeError("db down")
        monkeypatch.setattr(bid_notifications, "get_asyncpg_pool", boom)
        assert asyncio.run(bid_notifications.notify(str(uuid.uuid4()), "ready")) is False

    def test_admin_publish_twice_same_cycle_is_deduped_by_db(self, db, mail):
        """The real claim path against the fake store: same key twice -> one email."""
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="ready", publish_count=1)
        jid = str(job["id"])
        assert asyncio.run(bid_notifications.notify(jid, "ready")) is True
        assert asyncio.run(bid_notifications.notify(jid, "ready")) is False
        job["publish_count"] = 2
        assert asyncio.run(bid_notifications.notify(jid, "ready")) is True
        assert len(mail.by_tag("bid-job-ready")) == 2

    def _msg_ctx(self, **kw):
        base = dict(message_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()),
                    job_id=str(uuid.uuid4()), sender_role="admin",
                    body="Цената е 30.000 МКД, 5% успех", client_email="c@example.mk",
                    client_name="Клиент", company_name="Клиент ДООЕЛ",
                    tender_id="17400/2026", tender_title="Набавка", earlier_unread=0)
        base.update(kw)
        return base

    def test_render_message_email_hides_body_from_client(self):
        to, subject, html_body = bid_notifications.render_message_email(self._msg_ctx())
        assert to == "c@example.mk"
        assert "30.000" not in html_body and "МКД" not in html_body and "%" not in html_body
        assert "/portal/bid/" in html_body
        to, _, html_body = bid_notifications.render_message_email(self._msg_ctx(job_id=None))
        assert "/portal/messages" in html_body

    def test_render_message_email_admin_gets_escaped_body(self):
        to, subject, html_body = bid_notifications.render_message_email(
            self._msg_ctx(sender_role="client", body="<b>прашање</b>\nвтор ред"))
        assert to == bid_notifications.ADMIN_EMAIL
        assert "&lt;b&gt;прашање&lt;/b&gt;<br>втор ред" in html_body
        assert subject.startswith("Порака од Клиент ДООЕЛ")

    def test_notify_message_only_on_first_unread(self, monkeypatch, mail):
        ctxs = [self._msg_ctx(earlier_unread=0), self._msg_ctx(earlier_unread=1)]

        async def fake_pool():
            return FakePool(object())

        async def fake_load(conn, message_id):
            return ctxs.pop(0)

        monkeypatch.setattr(bid_notifications, "get_asyncpg_pool", fake_pool)
        monkeypatch.setattr(bid_notifications, "load_message_context", fake_load)
        assert asyncio.run(bid_notifications.notify_message("m1")) is True
        assert asyncio.run(bid_notifications.notify_message("m2")) is False
        assert len(mail.sent) == 1 and mail.sent[0]["tag"] == "bid-message"
        assert "30.000" not in mail.sent[0]["html"]


# ---------------------------------------------------------------------------
# Misc client endpoints
# ---------------------------------------------------------------------------
class TestClientMisc:
    def test_message_rate_limit(self, db, make_client, monkeypatch):
        monkeypatch.setattr(bid_jobs, "MAX_CLIENT_MESSAGES_PER_HOUR", 0)
        u = db.add_user()
        r = make_client(u).post(API + "/messages", json={"body": "здраво"})
        assert r.status_code == 429

    def test_message_body_validation(self, db, make_client):
        u = db.add_user()
        c = make_client(u)
        assert c.post(API + "/messages", json={"body": ""}).status_code == 422
        assert c.post(API + "/messages", json={"body": "x" * 5001}).status_code == 422
        assert c.post(API + "/messages", json={"body": "   "}).status_code == 400

    def test_list_orders_client_move_first(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        db.add_tender("2/2026")
        db.add_tender("3/2026")
        db.add_job(u["user_id"], status="preparing")
        db.add_job(u["user_id"], tender_id="2/2026", status="won")
        db.add_job(u["user_id"], tender_id="3/2026", status="ready")
        jobs = make_client(u).get(API + "/jobs").json()["jobs"]
        assert [j["status"] for j in jobs] == ["ready", "preparing", "won"]

    def test_by_tender_and_portal_summary(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        c = make_client(u)
        assert c.get(API + "/jobs/by-tender", params={"tender_id": "17400/2026"}).json() == {"job": None}
        s = c.get(API + "/portal/summary").json()
        assert s["first_run"] is True and s["counts"]["total"] == 0
        job = db.add_job(u["user_id"], status="payment_required")
        r = c.get(API + "/jobs/by-tender", params={"tender_id": "17400/2026"}).json()
        assert r["job"]["id"] == str(job["id"])
        s = c.get(API + "/portal/summary").json()
        assert s["first_run"] is False and len(s["your_move"]) == 1 and s["active_jobs"] == []


class TestAdminList:
    def test_list_and_summary(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        db.add_tender("2/2026")
        db.add_job(u["user_id"], status="requested")
        db.add_job(u["user_id"], tender_id="2/2026", status="ready")
        c = make_client(admin=True)
        r = c.get(API + "/admin/jobs", params={"q": "50%_x", "assigned_to": "me"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1 and len(body["jobs"]) == 2
        assert body["summary"]["needs_us"] == 1 and body["summary"]["needs_client"] == 1
        assert set(body["summary"]["counts"]) == set(bid_jobs.STATUSES)
        sql, args = db.find("COUNT(*) OVER ()")[0][1:]
        assert "%50\\%\\_x%" in args  # LIKE wildcards escaped
        assert {"user_id", "user_email", "company_name", "publish_count"} <= set(body["jobs"][0])
        assert c.get(API + "/admin/jobs", params={"status": "bogus"}).status_code == 400
        assert c.get(API + "/admin/jobs", params={"limit": 501}).status_code == 422
        assert c.get(API + "/admin/summary").json()["needs_us"] == 1


# ---------------------------------------------------------------------------
# Pre-deploy review fixes (Oct 2026)
# ---------------------------------------------------------------------------
def _cancelled(db, u, **kw):
    base = dict(status="cancelled", cancelled_by="client",
                cancelled_at=datetime.now() - timedelta(hours=1))
    base.update(kw)
    return db.add_job(u["user_id"], **base)


class TestBeginGuards:
    def test_client_cannot_reopen_admin_cancelled_job(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = _cancelled(db, u, cancelled_by="admin", paid_at=datetime.now())
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 409 and r.json()["detail"] == bid_jobs.ERR_ADMIN_CANCELLED
        assert job["status"] == "cancelled" and job["reopen_count"] == 0
        assert mail.sent == []

    def test_reopen_count_capped(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = _cancelled(db, u, reopen_count=bid_jobs.MAX_REOPENS)
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 409 and r.json()["detail"] == bid_jobs.ERR_TOO_MANY_REOPENS
        assert job["status"] == "cancelled" and mail.sent == []

    def test_reopen_cooldown(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = _cancelled(db, u, cancelled_at=datetime.now(timezone.utc))
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 429 and job["status"] == "cancelled" and mail.sent == []

    def test_daily_begin_cap_for_prospects(self, db, make_client, mail):
        u = db.add_user(account_type="prospect")
        c = make_client(u)
        limit = bid_jobs.MAX_BEGINS_PER_DAY["prospect"]
        for i in range(limit):
            db.add_tender(f"{i + 1}/2026")
            assert c.post(API + "/jobs", json={"tender_id": f"{i + 1}/2026"}).status_code == 200
        db.add_tender("99/2026")
        r = c.post(API + "/jobs", json={"tender_id": "99/2026"})
        assert r.status_code == 429 and r.json()["detail"] == bid_jobs.ERR_TOO_MANY_BEGINS
        assert len(db.jobs) == limit
        assert len(mail.by_tag("bid-job-job_requested")) == limit

    def test_terms_required_then_accepted_on_begin(self, db, make_client, mail):
        u = db.add_user(terms_agreed_at=None, agreement_version=None)
        db.add_tender()
        c = make_client(u)
        r = c.post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 409 and r.json()["detail"] == bid_jobs.ERR_TERMS_REQUIRED
        assert db.jobs == {} and mail.sent == []
        r = c.post(API + "/jobs", json={"tender_id": "17400/2026", "accept_terms": True})
        assert r.status_code == 200 and r.json()["created"] is True
        assert u["terms_agreed_at"] is not None
        assert u["agreement_version"] == bid_jobs.AGREEMENT_VERSION

    def test_outdated_terms_version_requires_new_acceptance(self, db, make_client):
        u = db.add_user(agreement_version="2020-01")
        db.add_tender()
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 409 and r.json()["detail"] == bid_jobs.ERR_TERMS_REQUIRED

    def test_agreement_endpoints(self, db, make_client):
        u = db.add_user(terms_agreed_at=None, agreement_version=None, prep_fee_mkd=25000)
        c = make_client(u)
        a = c.get(API + "/agreement").json()
        assert a["accepted"] is False and a["prep_fee_mkd"] == 25000
        assert a["current_version"] == bid_jobs.AGREEMENT_VERSION
        assert c.post(API + "/agreement/accept", json={"version": "old"}).status_code == 409
        a = c.post(API + "/agreement/accept",
                   json={"version": bid_jobs.AGREEMENT_VERSION}).json()
        assert a["accepted"] is True


class TestApprovalGates:
    def test_cannot_submit_before_approval(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="ready", published_at=datetime.now())
        db.add_file(job["id"])
        c = make_client(u)
        detail = c.get(f"{API}/jobs/{job['id']}").json()["job"]
        assert detail["can_mark_submitted"] is False and detail["can_approve_all"] is True
        assert c.post(f"{API}/jobs/{job['id']}/mark-submitted").status_code == 409
        assert job["status"] == "ready"
        # the admin escape hatch stays open
        r = make_client(admin=True).post(f"{API}/admin/jobs/{job['id']}/mark-submitted")
        assert r.status_code == 200 and job["status"] == "submitted"

    def test_approve_all_refused_while_changes_requested(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="changes_requested", published_at=datetime.now())
        fixing = db.add_file(job["id"], approval_status="changes_requested")
        other = db.add_file(job["id"])
        c = make_client(u)
        assert c.get(f"{API}/jobs/{job['id']}").json()["job"]["can_approve_all"] is False
        assert c.post(f"{API}/jobs/{job['id']}/approve-all").status_code == 409
        assert fixing["approval_status"] == "changes_requested"
        assert other["approval_status"] == "pending" and job["status"] == "changes_requested"
        assert mail.by_tag("bid-job-approved") == []

    def test_second_change_request_cycle_emails_again(self, db, make_client, mail):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="ready", publish_count=1, published_at=datetime.now())
        f1, f2 = db.add_file(job["id"]), db.add_file(job["id"])
        c = make_client(u)
        jid = job["id"]
        c.post(f"{API}/jobs/{jid}/files/{f1['id']}/request-changes", json={"comment": "a"})
        c.post(f"{API}/jobs/{jid}/files/{f1['id']}/approve")
        c.post(f"{API}/jobs/{jid}/files/{f2['id']}/approve")
        assert job["status"] == "approved"
        c.post(f"{API}/jobs/{jid}/files/{f2['id']}/request-changes", json={"comment": "b"})
        assert job["status"] == "changes_requested"
        assert len(mail.by_tag("bid-job-changes_requested")) == 2
        assert len(mail.by_tag("bid-job-approved")) == 1


class TestUploadsAndInvoices:
    def test_document_byte_quota(self, db, make_client, monkeypatch, files_dir):
        monkeypatch.setattr(bid_jobs, "MAX_DOCUMENT_BYTES_DEFAULT", 10)
        monkeypatch.setattr(bid_jobs, "MAX_DOCUMENT_BYTES", {})
        u = db.add_user()
        c = make_client(u)
        assert c.post(API + "/documents", files={"file": ("a.pdf", b"12345678", "application/pdf")},
                      data={"category": "drugo"}).status_code == 200
        r = c.post(API + "/documents", files={"file": ("b.pdf", b"12345", "application/pdf")},
                   data={"category": "drugo"})
        assert r.status_code == 413 and "простор" in r.json()["detail"]
        assert len(db.docs) == 1
        assert len(list((files_dir / "company" / str(u["user_id"])).iterdir())) == 1

    def test_mime_comes_from_extension(self, db, make_client):
        u = db.add_user()
        c = make_client(u)
        r = c.post(API + "/documents", files={"file": ("x.pdf", b"%PDF", "text/html")},
                   data={"category": "drugo"})
        d = r.json()["document"]
        assert d["mime"] == "application/pdf"
        dl = c.get(f"{API}/documents/{d['id']}/download")
        assert dl.headers["content-type"].startswith("application/pdf")

    def test_fee_locked_once_invoiced(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"], status="payment_required", invoice_number="7/2026")
        r = make_client(admin=True).patch(f"{API}/admin/jobs/{job['id']}", json={"prep_fee_mkd": 1})
        assert r.status_code == 409 and job["prep_fee_mkd"] == 30000

    def test_invoice_pdf_flow(self, db, make_client, mail, files_dir):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"])
        admin = make_client(admin=True)
        client = make_client(u)
        jid = job["id"]
        pdf = {"file": ("faktura.pdf", b"%PDF-inv", "application/pdf")}
        assert admin.post(f"{API}/admin/jobs/{jid}/invoice-file", files=pdf).status_code == 409
        admin.post(f"{API}/admin/jobs/{jid}/invoice", json={"prep_fee_mkd": 30000, "invoice_number": "1/2026"})
        assert admin.post(f"{API}/admin/jobs/{jid}/invoice-file",
                          files={"file": ("x.docx", b"x", "application/pdf")}).status_code == 400
        assert admin.post(f"{API}/admin/jobs/{jid}/invoice-file", files=pdf).status_code == 200
        detail = client.get(f"{API}/jobs/{jid}").json()
        assert detail["payment"]["invoice_file_name"] == "faktura.pdf"
        assert client.get(f"{API}/jobs/{jid}/invoice").content == b"%PDF-inv"
        assert make_client(db.add_user()).get(f"{API}/jobs/{jid}/invoice").status_code == 404
        # a corrected invoice number drops the old PDF and emails the client once more
        admin.post(f"{API}/admin/jobs/{jid}/invoice", json={"prep_fee_mkd": 30000, "invoice_number": "2/2026"})
        assert job["invoice_file_path"] is None
        assert client.get(f"{API}/jobs/{jid}/invoice").status_code == 404
        # same number again: no new email
        admin.post(f"{API}/admin/jobs/{jid}/invoice", json={"prep_fee_mkd": 30000, "invoice_number": "2/2026"})
        assert len(mail.by_tag("bid-job-invoice_issued")) == 2


class TestAdminCreateAndMisc:
    def test_admin_creates_job_without_email(self, db, make_client, mail):
        u = db.add_user(account_type="free", terms_agreed_at=None, agreement_version=None)
        db.add_tender()
        c = make_client(admin=True)
        r = c.post(API + "/admin/jobs", json={"user_id": str(u["user_id"]), "tender_id": "17400/2026"})
        assert r.status_code == 200, r.text
        assert r.json()["created"] is True and r.json()["job"]["status"] == "requested"
        assert u["account_type"] == "prospect"
        assert mail.sent == []
        again = c.post(API + "/admin/jobs", json={"user_id": str(u["user_id"]), "tender_id": "17400/2026"})
        assert again.json()["created"] is False and len(db.jobs) == 1
        assert c.post(API + "/admin/jobs", json={"user_id": str(uuid.uuid4()),
                                                 "tender_id": "17400/2026"}).status_code == 404

    def test_admin_can_reopen_admin_cancelled_job(self, db, make_client):
        u = db.add_user()
        db.add_tender()
        job = _cancelled(db, u, cancelled_by="admin")
        r = make_client(admin=True).post(API + "/admin/jobs", json={"user_id": str(u["user_id"]),
                                                                    "tender_id": "17400/2026"})
        assert r.status_code == 200 and job["status"] == "requested" and job["reopen_count"] == 1

    def test_calendar_feed_stops_after_downgrade(self, db, make_client):
        u = db.add_user(calendar_token="tok_" + "b" * 30)
        db.add_tender()
        db.add_job(u["user_id"], status="preparing")
        c = make_client(None)
        assert c.get(f"{API}/calendar/tok_{'b' * 30}.ics").status_code == 200
        u["account_type"] = "free"
        assert c.get(f"{API}/calendar/tok_{'b' * 30}.ics").status_code == 404

    def test_keywords_roundtrip(self, db, make_client):
        u = db.add_user()
        c = make_client(u)
        assert c.get(API + "/portal/keywords").json() == {"keywords": []}
        r = c.put(API + "/portal/keywords", json={"keywords": ["софтвер", " софтвер ", "ab", "  градежни  работи "]})
        assert r.json()["keywords"] == ["софтвер", "градежни работи"]
        assert c.get(API + "/portal/keywords").json()["keywords"] == ["софтвер", "градежни работи"]
        c.put(API + "/portal/keywords", json={"keywords": ["одржување"]})
        assert len(db.alerts) == 1 and db.alerts[0]["criteria"]["keywords"] == ["одржување"]

    def test_failed_send_is_recorded_once(self, db, make_client, monkeypatch):
        u = db.add_user()
        db.add_tender()
        job = db.add_job(u["user_id"])

        async def failing_send(**kw):
            return False

        monkeypatch.setattr(bid_notifications.postmark_service, "send_email", failing_send)
        assert asyncio.run(bid_notifications.notify(str(job["id"]), "preparing")) is False
        assert asyncio.run(bid_notifications.notify(str(job["id"]), "preparing")) is False
        assert db.audit_events(job["id"]).count("notify_failed") == 1
