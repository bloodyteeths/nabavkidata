"""
Client perks (Phase 2b, 14 Oct 2026): every paid feature belongs to managed
clients and admins only. Free users and prospects keep browsing/search, the
assessment, in-app alert matches and messaging.

Run:  cd backend && venv/bin/python -m pytest tests/test_client_perks.py -q --noconftest
"""
import asyncio
import os
import sys
import types
import uuid
from contextlib import asynccontextmanager

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-client-perks-tests")

import db_pool  # noqa: E402,F401  (backend/db_pool before ai/ shadows it)

_BACKEND_INIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "__init__.py")
if "backend" not in sys.modules:
    _stub = types.ModuleType("backend")
    _stub.__file__ = _BACKEND_INIT
    _stub.__path__ = [os.path.dirname(_BACKEND_INIT)]
    sys.modules["backend"] = _stub

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from models import User  # noqa: E402
from services import entitlements_service as es  # noqa: E402
from services.entitlements_service import (  # noqa: E402
    client_perks_clause,
    client_perks_sql,
    effective_tier,
    has_client_perks,
    perks_required_detail,
)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeRecord:
    """Mimics asyncpg.Record: item access only, no attribute access, has .get."""

    def __init__(self, **kw):
        self._d = kw

    def __getitem__(self, k):
        return self._d[k]

    def get(self, k, default=None):
        return self._d.get(k, default)

    def keys(self):
        return self._d.keys()


def orm_user(account_type="free", role="user"):
    return User(user_id=uuid.uuid4(), email="x@example.mk", account_type=account_type,
                role=role, subscription_tier="professional")


# ---------------------------------------------------------------------------
# Predicate
# ---------------------------------------------------------------------------
class TestPredicate:
    @pytest.mark.parametrize("make", [
        lambda at, role: orm_user(at, role),
        lambda at, role: {"account_type": at, "role": role},
        lambda at, role: FakeRecord(account_type=at, role=role),
    ], ids=["orm", "dict", "record"])
    @pytest.mark.parametrize("account_type,role,expected", [
        ("managed_client", "user", True),
        ("prospect", "user", False),
        ("free", "user", False),
        ("free", "admin", True),
        ("free", "ADMIN", True),
        (None, None, False),
    ])
    def test_has_client_perks(self, make, account_type, role, expected):
        assert has_client_perks(make(account_type, role)) is expected

    def test_none_and_missing_fields(self):
        assert has_client_perks(None) is False
        assert has_client_perks({}) is False
        assert has_client_perks(FakeRecord()) is False

    def test_subscription_tier_is_ignored(self):
        # A legacy paid SaaS subscriber who is not a bid client has no perks.
        u = orm_user("free", "user")
        u.subscription_tier = "enterprise"
        assert has_client_perks(u) is False
        assert effective_tier(u) == "free"

    def test_effective_tier(self):
        assert effective_tier(orm_user("managed_client")) == es.PERK_TIER == "enterprise"
        assert effective_tier(orm_user("prospect")) == es.NO_PERK_TIER == "free"
        assert effective_tier({"role": "admin"}) == "enterprise"
        assert effective_tier(None) == "free"

    def test_sql_helpers(self):
        assert client_perks_sql("u") == (
            "(u.account_type = 'managed_client' OR LOWER(COALESCE(u.role, '')) = 'admin')")
        assert client_perks_sql("x").startswith("(x.account_type")
        from sqlalchemy.dialects import postgresql
        compiled = str(client_perks_clause(User).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "users.account_type = 'managed_client'" in compiled
        assert "lower(coalesce(users.role, '')) = 'admin'" in compiled

    def test_detail_opens_paywall(self):
        d = perks_required_detail("exports")
        assert d["error"] == "upgrade_required"
        assert d["code"] == "client_perks_required"
        assert d["feature"] == "exports"
        assert "клиентите" in d["message"]
        assert "МКД" not in d["message"]


# ---------------------------------------------------------------------------
# Middleware gates
# ---------------------------------------------------------------------------
class TestGates:
    def test_require_client_perks(self):
        from middleware.entitlements import require_client_perks, require_paid_plan
        for dep in (require_client_perks, require_paid_plan):
            with pytest.raises(HTTPException) as e:
                run(dep(current_user=orm_user("prospect")))
            assert e.value.status_code == 403
            assert e.value.detail == perks_required_detail()
            client = orm_user("managed_client")
            assert run(dep(current_user=client)) is client
            admin = orm_user("free", "admin")
            assert run(dep(current_user=admin)) is admin

    @pytest.mark.parametrize("module_name", ["RAG_SEARCH", "PRICE_INTELLIGENCE",
                                             "ANALYTICS", "COMPETITOR_TRACKING",
                                             "EXPORT_CSV", "RISK_ANALYSIS"])
    def test_entitlement_checker_prospect_vs_client(self, module_name):
        from config.plans import ModuleName
        from middleware.entitlements import require_module
        checker = require_module(getattr(ModuleName, module_name))
        prospect = orm_user("prospect")
        prospect.subscription_tier = "enterprise"  # legacy tier must not leak perks
        with pytest.raises(HTTPException) as e:
            run(checker(current_user=prospect, db=None))
        assert e.value.status_code == 403
        assert e.value.detail["code"] == "client_perks_required"
        assert e.value.detail["feature"] == getattr(ModuleName, module_name).value
        client = orm_user("managed_client")
        client.subscription_tier = "free"
        assert run(checker(current_user=client, db=None)) is client

    def test_basic_search_stays_open(self):
        from config.plans import ModuleName
        from middleware.entitlements import require_module
        u = orm_user("free")
        assert run(require_module(ModuleName.BASIC_SEARCH)(current_user=u, db=None)) is u

    def test_trial_no_longer_grants_perks(self):
        from datetime import datetime, timedelta
        from config.plans import ModuleName
        from middleware.entitlements import check_trial_credit, require_module
        u = orm_user("free")
        u.trial_ends_at = datetime.utcnow() + timedelta(days=3)
        with pytest.raises(HTTPException):
            run(require_module(ModuleName.RAG_SEARCH)(current_user=u, db=None))
        assert run(check_trial_credit(u, "ai_messages", db=None)) == {
            "in_trial": False, "credits": None}

    def test_price_view_quota_zero_for_non_clients(self):
        from middleware.entitlements import check_price_view_quota
        q = run(check_price_view_quota(orm_user("prospect"), db=None))
        assert q["has_quota"] is False and q["limit"] == 0
        q = run(check_price_view_quota(orm_user("managed_client"), db=None))
        assert q["has_quota"] is True and q["limit"] is None

    def test_free_plan_and_fraud_limits(self):
        from config.plans import AccessLevel, ModuleName, get_plan
        from services.fraud_prevention import TIER_LIMITS
        free = get_plan("free")
        assert free.modules[ModuleName.BASIC_SEARCH] == AccessLevel.FULL
        assert free.modules[ModuleName.ADVANCED_FILTERS] == AccessLevel.FULL
        assert free.modules[ModuleName.ALERTS] == AccessLevel.LIMITED
        for m in (ModuleName.RAG_SEARCH, ModuleName.PRICE_INTELLIGENCE,
                  ModuleName.DOCUMENT_EXTRACTION, ModuleName.ANALYTICS):
            assert free.modules[m] == AccessLevel.NONE
        for k in ("rag_queries", "exports", "document_views", "price_views"):
            assert (free.limits[k].daily, free.limits[k].monthly) == (0, 0)
        assert TIER_LIMITS["free"]["daily_queries"] == 0
        assert TIER_LIMITS["free"]["monthly_queries"] == 0
        assert TIER_LIMITS["free"]["max_trial_queries"] == 0

    def test_saved_search_and_api_key_helpers(self):
        from api.api_keys import verify_enterprise_tier
        from api.saved_searches import get_user_tier
        assert get_user_tier(orm_user("prospect")) == "free"
        assert get_user_tier(orm_user("managed_client")) == "enterprise"
        assert run(verify_enterprise_tier(orm_user("prospect"))) is False
        assert run(verify_enterprise_tier(orm_user("managed_client"))) is True


# ---------------------------------------------------------------------------
# Crons: alert emails are a client perk
# ---------------------------------------------------------------------------
class _Result:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows


class FakeSession:
    def __init__(self, alert_rows):
        self.alert_rows = alert_rows
        self.sql: list[str] = []

    async def execute(self, stmt, params=None):
        sql = " ".join(str(stmt).split())
        self.sql.append(sql)
        if "FROM tender_alerts ta" in sql and "SELECT ta.alert_id" in sql:
            return _Result(self.alert_rows)
        return _Result()

    async def commit(self):
        pass

    @asynccontextmanager
    async def _nested(self):
        yield

    def begin_nested(self):
        return self._nested()


class TestInstantAlerts:
    @pytest.fixture
    def ia(self, monkeypatch):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "crons"))
        from crons import instant_alerts as mod

        async def always_match(alert, tender):
            return True, 80, ["клучен збор"]

        sent = []

        async def fake_send(email, name, tender, reasons):
            sent.append(email)
            return True

        notes = []

        async def fake_note(db, user_id, *a, **kw):
            notes.append(user_id)

        monkeypatch.setattr(mod, "check_alert_against_tender", always_match)
        monkeypatch.setattr(mod, "send_alert_email", fake_send)
        monkeypatch.setattr(mod, "create_notification", fake_note)
        mod._sent, mod._notes = sent, notes
        return mod

    def _row(self, email, verified, perks):
        return (uuid.uuid4(), uuid.uuid4(), "Следење", {"keywords": ["софтвер"]},
                ["email", "in_app"], email, "Име", verified, perks)

    def test_sql_selects_prospects_and_perks_flag(self, ia):
        db = FakeSession([])
        run(ia.process_tender_alert_matches(db, [{"tender_id": "1/2026", "title": "T"}], "e-nabavki"))
        sql = db.sql[0]
        assert client_perks_sql("u") + " AS perks" in sql
        assert "u.account_type IN ('prospect', 'managed_client')" in sql
        assert "LOWER(COALESCE(u.role, '')) = 'admin'" in sql
        assert "u.email_verified = true" not in sql  # prospects keep in-app matches

    def test_only_verified_clients_get_emails(self, ia):
        rows = [
            self._row("client@x.mk", True, True),
            self._row("prospect@x.mk", True, False),
            self._row("unverified-client@x.mk", False, True),
        ]
        db = FakeSession(rows)
        matches, emails = run(ia.process_tender_alert_matches(
            db, [{"tender_id": "1/2026", "title": "T"}], "e-nabavki"))
        assert matches == 3
        assert emails == 1
        assert ia._sent == ["client@x.mk"]
        assert len(ia._notes) == 3  # in-app notifications kept for everyone matched

    def test_change_watchers_require_perks(self, ia):
        from datetime import datetime

        class ChangeDB(FakeSession):
            async def execute(self, stmt, params=None):
                sql = " ".join(str(stmt).split())
                self.sql.append(sql)
                if "FROM tenders t" in sql:
                    return _Result([("1/2026", "T", "awarded", "W", "E")])
                return _Result()

        db = ChangeDB([])
        run(ia.check_tender_changes(db, datetime.utcnow()))
        watcher_sql = [s for s in db.sql if "FROM alert_matches am" in s][0]
        assert "u.email_verified = true" in watcher_sql
        assert client_perks_sql("u") in watcher_sql


def test_retired_campaigns_are_guarded(monkeypatch, capsys):
    monkeypatch.delenv("ALLOW_RETIRED_SAAS_CAMPAIGNS", raising=False)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("welcome_series", "trial_outreach", "reactivation_campaign",
                 "broadcast_discount", "personal_outreach"):
        path = os.path.join(root, "crons", f"{name}.py")
        if not os.path.exists(path):  # some retired scripts were never committed
            continue
        src = open(path, encoding="utf-8").read()
        assert 'os.getenv("ALLOW_RETIRED_SAAS_CAMPAIGNS") != "1"' in src, name


# ---------------------------------------------------------------------------
# HTTP gates: free users and prospects are refused before any handler runs;
# managed clients and admins pass the same gate.
# ---------------------------------------------------------------------------
def _gate_app(user):
    """Mount the cheap-to-import routers with the caller overridden. Every gated
    route's gate dependency runs first, so a 403 means no handler code ran."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api.auth as api_auth
    import middleware.rbac as rbac
    from database import get_db
    from api import (corruption, market_analytics, personalization, pricing, products,
                     rag, risk, tenders)

    app = FastAPI()
    for r in (rag.router, tenders.router, pricing.router, products.router,
              market_analytics.router):
        app.include_router(r, prefix="/api")
    for r in (corruption.router, personalization.router, risk.router):
        app.include_router(r)

    async def no_db():
        yield None

    for dep in (rbac.get_current_active_user, rbac.get_current_user,
                api_auth.get_current_user, api_auth.get_current_active_user):
        app.dependency_overrides[dep] = lambda: user
    app.dependency_overrides[get_db] = no_db
    return TestClient(app, raise_server_exceptions=False)


PERK_REQUESTS = [
    ("post", "/api/rag/search", {"query": "софтвер"}),
    ("post", "/api/tenders/export", {}),
    ("get", "/api/tenders/123/2026/ai_summary", None),
    ("get", "/api/tenders/by-id/123/2026/ai_summary", None),
    ("get", "/api/tenders/by-id/123/2026/price_history", None),
    ("get", "/api/tenders/price_history", None),
    ("get", "/api/tenders/compare", None),
    ("get", "/api/ai/price-history/72000000", None),
    ("get", "/api/products/aggregate", None),
    ("get", "/api/analytics/market-overview", None),
    ("get", "/api/analytics/competitor-analysis", None),
    ("get", "/api/analytics/supplier-strength/1", None),
    ("get", "/api/corruption/flagged-tenders", None),
    ("get", "/api/corruption/tender/123/2026/analysis", None),
    ("post", "/api/corruption/predict/123/2026", None),
    ("get", "/api/corruption/graph/clusters", None),
    ("get", "/api/personalization/insights", None),
    ("get", "/api/personalization/digests", None),
    ("get", "/api/personalization/tracked-competitors", None),
    ("post", "/api/risk/investigate", {"company_name": "Тест"}),
]

# AI features that do our paid work (bid advice, RAG/tender chat): admins only
# since 15 Oct 2026. Clients use the concierge (/api/concierge) instead.
ADMIN_ONLY_REQUESTS = [
    ("post", "/api/rag/query", {"question": "Кој победува?"}),
    ("post", "/api/rag/query/stream", {"question": "Кој победува?"}),
    ("post", "/api/tenders/123/2026/chat", {"question": "Што бараат?"}),
    ("get", "/api/tenders/by-id/123/2026/bid-advice", None),
    ("get", "/api/ai/bid-advisor/123/2026", None),
]


def _route_for(client, method, path):
    from fastapi.routing import APIRoute
    return next(r for r in client.app.routes if isinstance(r, APIRoute)
                and r.matches({"type": "http", "path": path,
                               "method": method.upper()})[0].name == "FULL")


class TestAdminOnlyAI:
    @pytest.mark.parametrize("account_type", ["free", "prospect", "managed_client"])
    @pytest.mark.parametrize("method,path,body", ADMIN_ONLY_REQUESTS,
                             ids=[f"{m} {p}" for m, p, _ in ADMIN_ONLY_REQUESTS])
    def test_non_admins_get_403(self, account_type, method, path, body):
        user = orm_user(account_type, "user")
        user.subscription_tier = "enterprise"
        client = _gate_app(user)
        kw = {"json": body} if body is not None else {}
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 403, (path, r.status_code, r.text[:200])

    @pytest.mark.parametrize("method,path,body", ADMIN_ONLY_REQUESTS,
                             ids=[f"{m} {p}" for m, p, _ in ADMIN_ONLY_REQUESTS])
    def test_admin_passes_require_admin(self, method, path, body):
        from middleware.rbac import require_admin
        user = orm_user("free", "admin")
        client = _gate_app(user)
        route = _route_for(client, method, path)
        calls = _dep_calls(route)
        assert require_admin in calls, path
        assert run(require_admin(current_user=user)) is user
        for name in ("require_client_perks",):
            assert name not in {getattr(c, "__name__", "") for c in calls}, path


class TestHttpGates:
    @pytest.mark.parametrize("account_type", ["free", "prospect"])
    @pytest.mark.parametrize("method,path,body", PERK_REQUESTS,
                             ids=[f"{m} {p}" for m, p, _ in PERK_REQUESTS])
    def test_non_clients_get_403(self, account_type, method, path, body):
        user = orm_user(account_type)
        user.subscription_tier = "enterprise"  # a legacy tier must not leak perks
        client = _gate_app(user)
        kw = {"json": body} if body is not None else {}
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 403, (path, r.status_code, r.text[:200])
        detail = r.json()["detail"]
        assert detail["error"] == "upgrade_required"
        assert detail["code"] == "client_perks_required"

    @pytest.mark.parametrize("account_type,role", [("managed_client", "user"), ("free", "admin")])
    @pytest.mark.parametrize("method,path,body", PERK_REQUESTS,
                             ids=[f"{m} {p}" for m, p, _ in PERK_REQUESTS])
    def test_clients_and_admins_pass_the_gate(self, account_type, role, method, path, body):
        """Walk the same route's gate dependencies directly (no handler runs, so
        nothing reaches a database or Gemini)."""
        from fastapi.routing import APIRoute
        user = orm_user(account_type, role)
        user.subscription_tier = "free"
        client = _gate_app(user)
        route = next(r for r in client.app.routes if isinstance(r, APIRoute)
                     and r.matches({"type": "http", "path": path,
                                    "method": method.upper()})[0].name == "FULL")
        gates = [d.call for d in route.dependant.dependencies
                 if getattr(d.call, "__name__", "") in ("require_client_perks",)
                 or type(d.call).__name__ == "EntitlementChecker"]
        assert gates, f"{path} has no perks gate"
        for gate in gates:
            if type(gate).__name__ == "EntitlementChecker":
                assert run(gate(current_user=user, db=None)) is user
            else:
                assert run(gate(current_user=user)) is user

    def test_public_browsing_stays_open(self):
        """Search and detail basics are not gated (they need a DB, so only the
        absence of a perks gate is checked)."""
        from fastapi.routing import APIRoute
        client = _gate_app(orm_user("free"))
        open_paths = {("GET", "/api/tenders"), ("POST", "/api/tenders/search"),
                      ("GET", "/api/tenders/{tender_id:path}"),
                      ("GET", "/api/tenders/by-id/{tender_id:path}/documents"),
                      ("GET", "/api/corruption/public-stats")}
        seen = set()
        for r in client.app.routes:
            if not isinstance(r, APIRoute):
                continue
            for m in r.methods:
                if (m, r.path) in open_paths:
                    seen.add((m, r.path))
                    names = {getattr(d.call, "__name__", type(d.call).__name__)
                             for d in r.dependant.dependencies}
                    assert "require_client_perks" not in names
                    assert "EntitlementChecker" not in names
        assert seen == open_paths

    def test_main_mounts_chat_and_collusion_behind_perks(self):
        """main.py needs a live DB to import; check the mounts by source."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = open(os.path.join(root, "main.py"), encoding="utf-8").read()

        def mount(router):
            return next(l for l in src.splitlines()
                        if f"app.include_router({router}" in l and not l.lstrip().startswith("#"))

        for router in ("collusion.router", "explainability.router"):
            assert "dependencies=[Depends(require_client_perks)]" in mount(router)
        for router in ("chat_sessions.router", "chat_v2.router"):
            assert "dependencies=[Depends(require_admin)]" in mount(router)
        assert 'app.include_router(concierge.router, prefix="/api")' in mount("concierge.router")
        assert "from middleware.rbac import require_admin" in src


# ---------------------------------------------------------------------------
# Digest cron recipients
# ---------------------------------------------------------------------------
class TestDigestRecipients:
    def test_digest_query_requires_client_perks(self, monkeypatch):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "crons"))
        from crons import email_digest as ed
        import services.cron_logger as cl

        captured = []

        class _Res:
            def all(self):
                return []

        class _Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def execute(self, stmt, *a, **kw):
                captured.append(stmt)
                return _Res()

            async def commit(self):
                pass

        async def _start(db, name, meta=None):
            return 1

        async def _done(*a, **kw):
            return None

        monkeypatch.setattr(ed, "AsyncSessionLocal", lambda: _Session())
        monkeypatch.setattr(cl, "log_cron_start", _start)
        monkeypatch.setattr(cl, "log_cron_complete", _done)
        monkeypatch.setattr(cl, "log_cron_failed", _done)
        for freq in ("daily", "weekly"):
            captured.clear()
            run(ed.generate_all_digests(freq))
            assert captured, "digest cron issued no query"
            from sqlalchemy.dialects import postgresql
            sql = str(captured[0].compile(dialect=postgresql.dialect(),
                                          compile_kwargs={"literal_binds": True}))
            assert "users.email_verified = true" in sql
            assert "users.account_type = 'managed_client'" in sql
            assert "lower(coalesce(users.role, '')) = 'admin'" in sql

    def test_instant_preference_users_require_client_perks(self):
        import inspect
        from crons import instant_alerts as ia
        src = inspect.getsource(ia.process_instant_alerts)
        q = src[src.index("users_query = select(User, UserPreferences)"):]
        q = q[:q.index("users_result = await db.execute(users_query)")]
        assert "client_perks_clause(User)" in q and "User.email_verified == True" in q


# ---------------------------------------------------------------------------
# Review fixes: remaining perk leaks (e-Pazar prices, competitor stats,
# dashboard analytics, document AI summary, RAG embedding writes)
# ---------------------------------------------------------------------------
def _route(router, path, method="GET"):
    for r in router.routes:
        if getattr(r, "path", None) == path and method in getattr(r, "methods", set()):
            return r
    raise AssertionError(f"route not found: {method} {path}")


def _dep_calls(route):
    return [d.call for d in route.dependant.dependencies]


class TestReviewLeaks:
    def test_epazar_price_masking(self):
        from api import epazar
        rows = [{"item_name": "Тонер", "quantity": 3, "estimated_unit_price_mkd": 100,
                 "estimated_total_price_eur": 5, "contracted_total_mkd": 300}]
        masked = epazar._mask_prices(rows, False)
        assert masked[0]["item_name"] == "Тонер" and masked[0]["quantity"] == 3
        assert masked[0]["estimated_unit_price_mkd"] is None
        assert masked[0]["estimated_total_price_eur"] is None
        assert masked[0]["contracted_total_mkd"] is None
        assert epazar._mask_prices(rows, True)[0]["estimated_unit_price_mkd"] == 100
        assert rows[0]["estimated_unit_price_mkd"] == 100  # input untouched

    def test_epazar_price_history_requires_perks(self):
        from api import epazar
        from middleware.entitlements import require_client_perks
        route = _route(epazar.router, "/api/epazar/items/{item_id}/price-history")
        assert require_client_perks in _dep_calls(route)

    def test_epazar_aggregations_empty_for_non_clients(self):
        from api import epazar
        prospect = types.SimpleNamespace(account_type="prospect", role="user")
        res = asyncio.run(epazar.get_epazar_items_aggregations(search="x", db=None,
                                                               current_user=prospect))
        assert res == {"aggregations": [], "price_gated": True}
        res = asyncio.run(epazar.get_epazar_items_aggregations_batch(
            body={"items": ["Тонер"]}, db=None, current_user=None))
        assert res == {"aggregations": {}, "price_gated": True}

    def test_competitor_stats_requires_perks(self):
        from api import market_analytics
        prospect = types.SimpleNamespace(account_type="prospect", role="user")
        req = market_analytics.CompetitorStatsRequest(company_name="Семос")
        with pytest.raises(HTTPException) as e:
            asyncio.run(market_analytics.get_competitor_stats(req, db=None,
                                                              current_user=prospect))
        assert e.value.status_code == 403
        assert e.value.detail["code"] == "client_perks_required"

    def test_rag_embedding_writes_are_admin_only(self):
        from api import rag
        from middleware.rbac import require_admin
        for path in ("/rag/embed/document", "/rag/embed/batch"):
            route = next(r for r in rag.router.routes if getattr(r, "path", "").endswith(
                path.split("/rag")[-1]) and "POST" in r.methods)
            assert require_admin in _dep_calls(route), path

    def test_document_content_open_to_all_signed_in_users(self):
        from api import documents
        route = next(r for r in documents.router.routes
                     if getattr(r, "path", "").endswith("/{doc_id}/content"))
        # No module gate: the text is tender-detail basics; the AI summary is
        # dropped in the handler for non-clients.
        assert not any(getattr(c, "__name__", "") == "check_module_access"
                       or "require_module" in getattr(c, "__qualname__", "")
                       for c in _dep_calls(route))
