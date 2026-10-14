"""
Tests for client-win detection: services/client_wins.py (pure) and
crons/detect_client_wins.py (with a fake asyncpg pool and mail recorder).

Run:  cd backend && venv/bin/python -m pytest tests/test_detect_client_wins.py -q --noconftest
"""
import asyncio
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-client-wins-tests")
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "crons"))

import types  # noqa: E402

import db_pool  # noqa: E402,F401

# backend/__init__.py is a stray copy of api/__init__.py; pre-seed an inert module
# so pytest does not execute it (see tests/test_bid_jobs.py).
if "backend" not in sys.modules:
    _stub = types.ModuleType("backend")
    _stub.__file__ = os.path.join(BACKEND, "__init__.py")
    _stub.__path__ = [BACKEND]
    sys.modules["backend"] = _stub

import pytest  # noqa: E402

from services import client_wins as cw  # noqa: E402
import detect_client_wins as cron  # noqa: E402


class TestNormalize:
    @pytest.mark.parametrize("raw,expected", [
        ("Фактурино ДООЕЛ Велес", "фактурино велес"),
        ("Друштво за трговија „СЕМОС“ ДОО Скопје", "трговија семос"),
        ("SEMOS DOO Skopje", "семос"),
        ("Fakturino DOOEL", "фактурино"),
        ("ЛАТРОН СОЛУШНС ДООЕЛ увоз-извоз Скопје", "латрон солушнс"),
        ("Kips-Kom", "кипс ком"),
        ("Džambo Gjorgji Ljubica Njegoš Kjoska Zhivko Chair Shop Dzid",
         "џамбо ѓорѓи љубица његош ќоска живко чаир шоп ѕид"),
        ("", ""),
        (None, ""),
    ])
    def test_normalize(self, raw, expected):
        assert cw.normalize_company(raw) == expected

    def test_latin_and_cyrillic_forms_match(self):
        a = cw.normalize_company("ASEE DOOEL Skopje")
        b = cw.normalize_company("АСЕЕ ДООЕЛ Скопје")
        assert a == b == "асее"


class TestSimilarity:
    def test_identical_and_disjoint(self):
        assert cw.trigram_similarity("семос", "семос") == 1.0
        assert cw.trigram_similarity("семос", "латрон") == 0.0
        assert cw.trigram_similarity("", "семос") == 0.0

    def test_matches_pg_trgm_definition(self):
        # pg_trgm: similarity('word','words') = 4/7 (" w"," wo","wor","ord","rd " vs "rds","ds ")
        assert cw.trigram_similarity("word", "words") == pytest.approx(4 / 7)

    def test_threshold_behaviour(self):
        client = cw.normalize_company("Фактурино ДООЕЛ")
        assert cw.trigram_similarity(cw.normalize_company("ФАКТУРИНО ДООЕЛ Велес"), client) \
            >= cw.WIN_MATCH_THRESHOLD
        assert cw.trigram_similarity(cw.normalize_company("Фактура Плус ДОО"), client) \
            < cw.WIN_MATCH_THRESHOLD

    def test_best_match(self):
        name, score, amount = cw.best_match(
            [("Латрон ДООЕЛ", 1), ("Fakturino DOOEL Veles", 2)], "Фактурино ДООЕЛ Велес")
        assert name == "Fakturino DOOEL Veles" and amount == 2 and score == 1.0
        assert cw.best_match([("X", 1)], "")[0] is None


class TestMonthsAndFee:
    @pytest.mark.parametrize("text,months", [
        ("12 месеци", 12), ("24 месеци од склучување", 24), ("1 месец", 1),
        ("2 години", 24), ("1 година", 12), ("90 дена", 3), ("45 дена", 2), ("10 ден", 1),
        ("до 3 год.", 36), ("", None), (None, None), ("неопределено", None),
        ("150000 денари", None),
    ])
    def test_parse_contract_months(self, text, months):
        assert cw.parse_contract_months(text) == months

    def test_first_year_value(self):
        assert cw.first_year_value(1_200_000, 24) == Decimal("600000.00")
        assert cw.first_year_value(500_000, 6) == Decimal(500000)
        assert cw.first_year_value(500_000, None) == Decimal(500000)
        assert cw.first_year_value(None, 24) is None

    def test_fee_with_credit_and_no_cap(self):
        assert cw.compute_success_fee(1_000_000, 5, 0) == 50_000
        assert cw.compute_success_fee(1_000_000, 5, 30_000) == 20_000
        assert cw.compute_success_fee(100_000, 5, 30_000) == 0  # never negative
        # no cap: a 500M first year at 5% is 25M
        assert cw.compute_success_fee(500_000_000, 5, 0) == 25_000_000
        assert cw.compute_success_fee(Decimal("33333.33"), Decimal("4.5"), 0) == 1500

    def test_build_win_row_sources_and_credit(self):
        job = dict(id=uuid.uuid4(), user_id=uuid.uuid4(), tender_id="1/2026",
                   success_fee_pct=None, prep_fee_mkd=25000,
                   paid_at=datetime.now(timezone.utc), free=False)
        tender = dict(title="Одржување", procuring_entity="МЕРМС", actual_value_mkd=2_400_000,
                      estimated_value_mkd=3_000_000, contract_duration="24 месеци")
        row = cw.build_win_row(job, {"success_fee_pct": 5}, tender, "СЕМОС", 0.8, None)
        assert row["value_source"] == "actual" and row["contract_months"] == 24
        assert row["first_year_value_mkd"] == Decimal("1200000.00")
        assert row["success_fee_pct"] == Decimal(5) and row["prep_fee_credit_mkd"] == 25000
        assert row["success_fee_mkd"] == 60000 - 25000
        bid = cw.build_win_row(job, {"success_fee_pct": 5}, tender, "СЕМОС", 0.8, 1_000_000)
        assert bid["value_source"] == "bid" and bid["contract_value_mkd"] == Decimal(1000000)
        free_job = dict(job, free=True)
        assert cw.build_win_row(free_job, {"success_fee_pct": 5}, tender, "x", 1, None)[
            "prep_fee_credit_mkd"] == 0
        unpaid = dict(job, paid_at=None)
        assert cw.build_win_row(unpaid, None, dict(tender, actual_value_mkd=None), "x", 1, None)[
            "value_source"] == "estimated"
        job_pct = dict(job, success_fee_pct=3)
        assert cw.build_win_row(job_pct, {"success_fee_pct": 5}, tender, "x", 1, None)[
            "success_fee_pct"] == Decimal(3)
        args = cw.win_insert_args(row)
        assert len(args) == len(cw.WIN_COLUMNS) and cw.INSERT_WIN_SQL.count("$") == len(args)
        assert "ON CONFLICT (user_id, tender_id) DO NOTHING" in cw.INSERT_WIN_SQL

    def test_split_winner_names(self):
        assert cw.split_winner_names("А ДОО; Б ДООЕЛ,\nВ") == ["А ДОО", "Б ДООЕЛ", "В"]
        assert cw.split_winner_names(None) == []


# ---------------------------------------------------------------------------
# Cron run
# ---------------------------------------------------------------------------
class FakeConn:
    def __init__(self, candidates, bidders):
        self.candidates = candidates
        self.bidders = bidders
        self.inserted: list = []
        self.updated: list = []

    async def fetch(self, sql, *a):
        if "FROM bid_jobs j JOIN users u" in sql:
            assert "NOT EXISTS (SELECT 1 FROM client_wins" in sql
            assert "LOWER(COALESCE(u.role, '')) <> 'admin'" in sql
            return [c for c in self.candidates
                    if not any(i[0] == c["user_id"] and i[2] == c["tender_id"]
                               for i in self.inserted)]
        if "FROM tender_bidders" in sql:
            return self.bidders.get(a[0], [])
        raise AssertionError(sql)

    async def fetchval(self, sql, *a):
        assert sql.startswith("INSERT INTO client_wins")
        if any(i[0] == a[0] and i[2] == a[2] for i in self.inserted):
            return None
        self.inserted.append(a)
        return uuid.uuid4()

    async def execute(self, sql, *a):
        self.updated.append((sql, a))
        return "UPDATE 1"


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self.conn


def _cand(**kw):
    c = dict(id=uuid.uuid4(), user_id=uuid.uuid4(), tender_id="17400/2026",
             status="submitted", success_fee_pct=5, prep_fee_mkd=20000,
             paid_at=datetime.now(timezone.utc), free=False, company_name="Фактурино ДООЕЛ",
             u_pct=5, email="c@example.mk", title="Одржување", procuring_entity="МЕРМС",
             winner=None, actual_value_mkd=None, estimated_value_mkd=800000,
             contract_duration="12 месеци")
    c.update(kw)
    return c


@pytest.fixture
def notified(monkeypatch):
    sent = []

    async def fake_notify(job_id, kind, extra=None):
        sent.append((job_id, kind))
        return True

    monkeypatch.setattr(cron.bid_notifications, "notify", fake_notify)
    return sent


def _run(monkeypatch, conn, dry=False):
    async def fake_pool():
        return FakePool(conn)
    monkeypatch.setattr(cron, "get_asyncpg_pool", fake_pool)
    return asyncio.run(cron.run(dry_run=dry))


class TestCron:
    def test_detects_from_bidders_and_winner_text(self, monkeypatch, notified):
        a = _cand()
        b = _cand(tender_id="2/2026", winner="ЛАТРОН ДООЕЛ; FAKTURINO DOOEL")
        c = _cand(tender_id="3/2026", winner="Семос ДОО")
        conn = FakeConn([a, b, c], {"17400/2026": [
            {"company_name": "ФАКТУРИНО ДООЕЛ Велес", "bid_amount_mkd": 700000}]})
        stats = _run(monkeypatch, conn)
        assert stats == {"candidates": 3, "matched": 2, "inserted": 2, "notified": 2}
        first = dict(zip(cw.WIN_COLUMNS, conn.inserted[0]))
        assert first["value_source"] == "bid" and first["contract_value_mkd"] == Decimal(700000)
        assert first["success_fee_mkd"] == 35000 - 20000
        assert {k for _, k in notified} == {"win_detected"}
        assert len([u for u in conn.updated if "admin_notified_at" in u[0]]) == 2
        # second run: nothing new
        stats = _run(monkeypatch, conn)
        assert stats["inserted"] == 0 and len(notified) == 2

    def test_dry_run_writes_nothing(self, monkeypatch, notified):
        conn = FakeConn([_cand(winner="Фактурино ДООЕЛ")], {})
        stats = _run(monkeypatch, conn, dry=True)
        assert stats["matched"] == 1 and stats["inserted"] == 0
        assert conn.inserted == [] and notified == []

    def test_crontab_line_documented(self):
        assert "30 6 * * *" in cron.__doc__
