"""
Tests for Phase 2b self-serve payments (services/bid_payments.py + the payment,
billing and wins endpoints in api/bid_jobs.py + the webhook branch in
api/billing.py).

Stripe is never called: services.bid_payments.stripe is replaced with FakeStripe.
The in-memory FakeDB and fixtures come from tests/test_bid_jobs.py.

Run:  cd backend && venv/bin/python -m pytest tests/test_bid_payments.py -q --noconftest
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402
import stripe as real_stripe  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from test_bid_jobs import (API, FakePool, bid_jobs, bid_notifications, db, files_dir,  # noqa: E402,F401
                           mail, make_client)
from services import bid_payments  # noqa: E402


# ---------------------------------------------------------------------------
# Fake Stripe
# ---------------------------------------------------------------------------
class FakeStripe:
    error = real_stripe.error

    def __init__(self):
        self.calls: list = []
        self.sessions: dict = {}
        self.customers: dict = {}
        self.n = 0
        outer = self

        class _Session:
            @staticmethod
            def create(**kw):
                outer.n += 1
                sid = f"cs_test_{outer.n:04d}xyz"
                outer.calls.append(("Session.create", kw))
                return SimpleNamespace(id=sid, url=f"https://checkout.stripe.test/{sid}")

            @staticmethod
            def retrieve(sid, **kw):
                outer.calls.append(("Session.retrieve", sid, kw))
                if sid not in outer.sessions:
                    raise real_stripe.error.InvalidRequestError("No such session", "id")
                return outer.sessions[sid]

        class _Customer:
            @staticmethod
            def create(**kw):
                outer.n += 1
                cid = f"cus_{outer.n}"
                outer.customers[cid] = {"id": cid, "currency": None}
                outer.calls.append(("Customer.create", kw))
                return SimpleNamespace(id=cid)

            @staticmethod
            def retrieve(cid):
                outer.calls.append(("Customer.retrieve", cid))
                if cid not in outer.customers:
                    raise real_stripe.error.InvalidRequestError("No such customer", "id")
                return outer.customers[cid]

            @staticmethod
            def modify(cid, **kw):
                outer.calls.append(("Customer.modify", cid, kw))
                return {"id": cid}

        class _Invoice:
            @staticmethod
            def create(**kw):
                outer.calls.append(("Invoice.create", kw))
                return SimpleNamespace(id="in_draft_1")

            @staticmethod
            def delete(inv_id):
                outer.calls.append(("Invoice.delete", inv_id))
                return {"id": inv_id, "deleted": True}

        class _InvoiceItem:
            @staticmethod
            def create(**kw):
                outer.calls.append(("InvoiceItem.create", kw))
                return SimpleNamespace(id="ii_1")

        class _SetupIntent:
            @staticmethod
            def retrieve(sid, **kw):
                outer.calls.append(("SetupIntent.retrieve", sid))
                return {"id": sid, "payment_method": None}

        self.checkout = SimpleNamespace(Session=_Session)
        self.Customer = _Customer
        self.Invoice = _Invoice
        self.InvoiceItem = _InvoiceItem
        self.SetupIntent = _SetupIntent

    def of(self, name):
        return [c for c in self.calls if c[0] == name]

    def add_prep_session(self, job, user, *, sid="cs_test_paid_0001", amount=None, paid=True,
                         currency="mkd", job_id=None, user_id=None):
        md = {"product": "nabavkidata", "kind": "bid_prep_fee",
              "job_id": str(job_id or job["id"]), "user_id": str(user_id or user["user_id"]),
              "tender_id": job["tender_id"]}
        self.sessions[sid] = {
            "id": sid, "object": "checkout.session", "metadata": md,
            "payment_status": "paid" if paid else "unpaid", "status": "complete",
            "currency": currency,
            "amount_total": amount if amount is not None else job["prep_fee_mkd"] * 100,
            "customer": "cus_existing",
            "payment_intent": {"id": "pi_1", "payment_method": {
                "id": "pm_card_1", "card": {"brand": "visa", "last4": "4242"}}},
        }
        return sid

    def add_setup_session(self, user, *, sid="cs_test_setup_0001", user_id=None):
        md = {"product": "nabavkidata", "kind": "card_setup",
              "user_id": str(user_id or user["user_id"])}
        self.sessions[sid] = {
            "id": sid, "object": "checkout.session", "metadata": md, "status": "complete",
            "payment_status": "no_payment_required", "customer": "cus_existing",
            "setup_intent": {"id": "seti_1", "payment_method": {
                "id": "pm_card_2", "card": {"brand": "mastercard", "last4": "5555"}}},
        }
        return sid


@pytest.fixture
def fs(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr(bid_payments, "stripe", fake)
    monkeypatch.setattr(bid_payments, "STRIPE_SECRET_KEY", "sk_test_dummy")
    return fake


@pytest.fixture
def pdb(db, monkeypatch):
    async def fake_get_pool():
        return FakePool(db)

    monkeypatch.setattr(bid_payments, "get_asyncpg_pool", fake_get_pool)
    return db


def _unauthorised(**kw):
    base = dict(success_fee_authorised_at=None, success_fee_authorised_via=None,
                success_fee_authorised_ref=None)
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
class TestHelpers:
    def test_minor_units(self):
        assert bid_payments.STRIPE_CURRENCY == "mkd" and bid_payments.MINOR_UNITS == 100
        assert bid_payments.to_minor(25000) == 2_500_000
        assert bid_payments.to_minor(0) == 0

    def test_session_guard(self):
        ok = {"metadata": {"product": "nabavkidata", "kind": "bid_prep_fee"}}
        assert bid_payments.is_bid_service_session(ok)
        assert bid_payments.is_bid_service_session(
            {"metadata": {"product": "nabavkidata", "kind": "card_setup"}})
        assert not bid_payments.is_bid_service_session({"metadata": {"tier": "starter"}})
        assert not bid_payments.is_bid_service_session(
            {"metadata": {"product": "tenderuk", "kind": "bid_prep_fee"}})
        assert not bid_payments.is_bid_service_session({"metadata": None})
        assert not bid_payments.is_bid_service_session({})

    def test_agreement_version_shared(self):
        assert bid_jobs.AGREEMENT_VERSION == bid_payments.AGREEMENT_VERSION == "2026-10-14"


# ---------------------------------------------------------------------------
# pay-prep
# ---------------------------------------------------------------------------
class TestPayPrep:
    def test_checkout_amount_from_db_and_card_saved(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required", prep_fee_mkd=25000)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/pay-prep", json={"amount": 1})
        assert r.status_code == 200, r.text
        assert r.json()["url"].startswith("https://checkout.stripe.test/")
        (_, kw), = fs.of("Session.create")
        assert kw["mode"] == "payment" and kw["payment_method_types"] == ["card"]
        pd = kw["line_items"][0]["price_data"]
        assert pd["currency"] == "mkd" and pd["unit_amount"] == 2_500_000
        assert kw["payment_intent_data"]["setup_future_usage"] == "off_session"
        assert kw["metadata"] == {"product": "nabavkidata", "kind": "bid_prep_fee",
                                  "job_id": str(job["id"]), "user_id": str(u["user_id"]),
                                  "tender_id": "17400/2026"}
        assert kw["client_reference_id"] == str(u["user_id"])
        assert kw["after_expiration"] == {"recovery": {"enabled": True}}
        assert kw["success_url"].endswith(f"/portal/bid/{job['id']}?paid={{CHECKOUT_SESSION_ID}}")
        assert kw["customer"] == u["stripe_customer_id"] and u["stripe_customer_id"].startswith("cus_")
        # Nothing is marked paid by starting a checkout.
        assert job["paid_at"] is None and job["status"] == "payment_required"

    def test_no_card_once_invoice_issued(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required", invoice_number="ФА-1/2026")
        c = make_client(u)
        r = c.post(f"{API}/jobs/{job['id']}/pay-prep")
        assert r.status_code == 409 and r.json()["detail"] == bid_jobs.ERR_INVOICE_ISSUED
        assert c.get(f"{API}/jobs/{job['id']}").json()["payment"]["can_pay_card"] is False
        assert not fs.of("Session.create")

    def test_concurrent_customer_creation_keeps_one(self, pdb, fs):
        """Compare-and-set: a customer stored meanwhile wins over ours."""
        import asyncio
        u = pdb.add_user()
        orig_create = fs.Customer.create

        def create_and_race(**kw):
            res = orig_create(**kw)
            u["stripe_customer_id"] = "cus_winner"  # the other request stored first
            return res
        fs.Customer.create = staticmethod(create_and_race)
        fs.customers["cus_winner"] = {"id": "cus_winner", "currency": None}
        assert asyncio.run(bid_payments.ensure_stripe_customer(None, u["user_id"])) == "cus_winner"
        assert u["stripe_customer_id"] == "cus_winner"

    def test_reuses_mkd_customer_and_replaces_eur_customer(self, pdb, fs, make_client):
        fs.customers["cus_mkd"] = {"id": "cus_mkd", "currency": "mkd"}
        fs.customers["cus_eur"] = {"id": "cus_eur", "currency": "eur"}
        pdb.add_tender()
        a = pdb.add_user(stripe_customer_id="cus_mkd")
        ja = pdb.add_job(a["user_id"], status="payment_required")
        assert make_client(a).post(f"{API}/jobs/{ja['id']}/pay-prep").status_code == 200
        assert fs.of("Session.create")[-1][1]["customer"] == "cus_mkd"
        assert not fs.of("Customer.create")
        b = pdb.add_user(stripe_customer_id="cus_eur")
        jb = pdb.add_job(b["user_id"], status="payment_required")
        assert make_client(b).post(f"{API}/jobs/{jb['id']}/pay-prep").status_code == 200
        assert b["stripe_customer_id"] not in ("cus_eur", None)
        assert fs.of("Session.create")[-1][1]["customer"] == b["stripe_customer_id"]

    def test_guards(self, pdb, fs, make_client, monkeypatch):
        pdb.add_tender()
        u = pdb.add_user()
        other = pdb.add_user()
        paid = pdb.add_job(u["user_id"], status="preparing", paid_at=datetime.now(timezone.utc))
        c = make_client(u)
        assert c.post(f"{API}/jobs/{paid['id']}/pay-prep").status_code == 409
        foreign = pdb.add_job(other["user_id"], tender_id="1/2026", status="payment_required")
        assert c.post(f"{API}/jobs/{foreign['id']}/pay-prep").status_code == 404
        free = pdb.add_job(u["user_id"], tender_id="2/2026", status="payment_required", free=True)
        assert c.post(f"{API}/jobs/{free['id']}/pay-prep").status_code == 409
        due = pdb.add_job(u["user_id"], tender_id="3/2026", status="payment_required")
        u["agreement_version"] = "2026-10"
        r = c.post(f"{API}/jobs/{due['id']}/pay-prep")
        assert r.status_code == 409 and r.json()["detail"] == "terms_required"
        monkeypatch.setattr(bid_payments, "STRIPE_SECRET_KEY", "")
        r = c.post(f"{API}/jobs/{due['id']}/pay-prep")
        assert r.status_code == 503 and r.json()["detail"] == bid_payments.ERR_CARD_UNAVAILABLE
        assert not fs.of("Session.create")

    def test_stripe_failure_is_502(self, pdb, fs, make_client, monkeypatch):
        pdb.add_tender()
        u = pdb.add_user()
        job = pdb.add_job(u["user_id"], status="payment_required")

        def boom(**kw):
            raise real_stripe.error.APIConnectionError("down")
        monkeypatch.setattr(fs.checkout.Session, "create", staticmethod(boom))
        r = make_client(u).post(f"{API}/jobs/{job['id']}/pay-prep")
        assert r.status_code == 502


# ---------------------------------------------------------------------------
# Return leg, webhook and admin share one idempotent mark-paid
# ---------------------------------------------------------------------------
class TestPrepComplete:
    def test_paid_promotes_saves_card_and_authorises(self, pdb, fs, make_client, mail):
        u = pdb.add_user(**_unauthorised())
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required", prep_fee_mkd=25000)
        sid = fs.add_prep_session(job, u)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["paid"] is True and body["account_promoted"] is True
        assert body["job"]["status"] == "preparing"
        assert body["payment"]["paid_via"] == "stripe" and body["payment"]["can_pay_card"] is False
        assert job["paid_via"] == "stripe" and job["stripe_checkout_session_id"] == sid
        assert job["stripe_payment_intent_id"] == "pi_1"
        assert u["account_type"] == "managed_client"
        assert (u["stripe_mandate_pm_id"], u["stripe_card_brand"], u["stripe_card_last4"]) == \
            ("pm_card_1", "visa", "4242")
        assert u["success_fee_authorised_via"] == "card"
        assert fs.of("Customer.modify")[0][2] == {
            "invoice_settings": {"default_payment_method": "pm_card_1"}}
        assert len(mail.by_tag("bid-job-preparing")) == 1
        paid_online = mail.by_tag("bid-job-paid_online")
        assert len(paid_online) == 1 and paid_online[0]["to"] == bid_notifications.ADMIN_EMAIL

    def test_rejects_other_users_session(self, pdb, fs, make_client):
        u = pdb.add_user()
        other = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u, user_id=other["user_id"])
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 400
        assert job["paid_at"] is None

    def test_rejects_session_for_other_job(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        job2 = pdb.add_job(u["user_id"], tender_id="9/2026", status="payment_required")
        sid = fs.add_prep_session(job2, u)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 400
        assert job["paid_at"] is None and job2["paid_at"] is None

    def test_rejects_amount_mismatch_and_alerts(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required", prep_fee_mkd=25000)
        sid = fs.add_prep_session(job, u, amount=100)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 200
        assert r.json()["paid"] is False and r.json()["reason"] == "amount_mismatch"
        assert job["paid_at"] is None and job["status"] == "payment_required"
        assert "payment_amount_mismatch" in pdb.audit_events(job["id"])
        assert len(mail.by_tag("bid-job-payment_alert")) == 1
        # wrong currency is a mismatch too
        sid2 = fs.add_prep_session(job, u, sid="cs_test_eur_00001", currency="eur")
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid2})
        assert r.json()["paid"] is False and job["paid_at"] is None

    def test_unpaid_session_is_402(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u, paid=False)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 402 and job["paid_at"] is None

    def test_idempotent_across_return_leg_webhook_and_admin(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u)
        c = make_client(u)
        for _ in range(2):
            r = c.post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
            assert r.status_code == 200 and r.json()["paid"] is True
        assert bid_payments.is_bid_service_session(fs.sessions[sid])
        import asyncio
        assert asyncio.run(bid_payments.handle_checkout_session_completed(
            {"id": sid, "metadata": fs.sessions[sid]["metadata"]})) is True
        assert pdb.audit_events(job["id"]).count("paid") == 1
        assert job["paid_via"] == "stripe"
        assert len(mail.by_tag("bid-job-preparing")) == 1
        assert len(mail.by_tag("bid-job-paid_online")) == 1
        assert not mail.by_tag("bid-job-payment_alert")

    def test_invoice_mark_paid_after_card_is_a_duplicate(self, pdb, fs, make_client, mail):
        """Card first, then the bank transfer for the фактура arrives: the admin's
        „Означи платено“ must not pass silently — a refund is due."""
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.json()["paid"] is True
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/jobs/{job['id']}/mark-paid", json={})
        assert r.status_code == 409
        assert r.json()["detail"] == bid_jobs.ERR_ALREADY_PAID_CARD
        assert "duplicate_payment" in pdb.audit_events(job["id"])
        assert job["paid_via"] == "stripe"
        assert len(mail.by_tag("bid-job-payment_alert")) == 1

    def test_second_session_for_paid_job_alerts(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        c = make_client(u)
        s1 = fs.add_prep_session(job, u, sid="cs_test_first_001")
        s2 = fs.add_prep_session(job, u, sid="cs_test_second_02")
        assert c.post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": s1}).json()["paid"]
        r = c.post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": s2})
        assert r.status_code == 200 and r.json()["reason"] == "duplicate"
        assert job["stripe_checkout_session_id"] == s1
        assert "duplicate_payment" in pdb.audit_events(job["id"])
        alerts = mail.by_tag("bid-job-payment_alert")
        assert len(alerts) == 1 and alerts[0]["to"] == bid_notifications.ADMIN_EMAIL

    def test_paid_while_cancelled_records_and_reopen_goes_to_preparing(self, pdb, fs, make_client,
                                                                        mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="cancelled", cancelled_by="client",
                          cancelled_at=datetime.now(timezone.utc) - timedelta(hours=2))
        sid = fs.add_prep_session(job, u)
        c = make_client(u)
        r = c.post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 200
        assert job["status"] == "cancelled" and job["paid_at"] is not None
        assert "paid_while_cancelled" in pdb.audit_events(job["id"])
        assert len(mail.by_tag("bid-job-payment_alert")) == 1
        r = c.post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 200, r.text
        assert job["status"] == "preparing" and r.json()["payment_required"] is False


class TestMarkJobPaidUnit:
    def test_free_and_wrong_status(self, pdb):
        import asyncio
        u = pdb.add_user()
        free = pdb.add_job(u["user_id"], status="preparing", free=True)
        ready = pdb.add_job(u["user_id"], tender_id="5/2026", status="ready")

        async def go():
            a = await bid_payments.mark_job_paid(pdb, free["id"], "invoice")
            b = await bid_payments.mark_job_paid(pdb, ready["id"], "invoice")
            return a, b
        a, b = asyncio.run(go())
        assert a["changed"] is False and a["reason"] == "free"
        assert b["changed"] is False and b["reason"] == "wrong_status"
        with pytest.raises(LookupError):
            asyncio.run(bid_payments.mark_job_paid(pdb, uuid.uuid4(), "invoice"))

    def test_admin_mark_paid_from_requested_and_conflicts(self, pdb, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        job = pdb.add_job(u["user_id"], status="requested")
        assert admin.post(f"{API}/admin/jobs/{job['id']}/mark-paid", json={}).status_code == 200
        assert job["status"] == "preparing" and job["paid_via"] == "invoice"
        ready = pdb.add_job(u["user_id"], tender_id="6/2026", status="ready")
        assert admin.post(f"{API}/admin/jobs/{ready['id']}/mark-paid", json={}).status_code == 409
        assert admin.post(f"{API}/admin/jobs/{uuid.uuid4()}/mark-paid", json={}).status_code == 404


# ---------------------------------------------------------------------------
# Webhook branch in api/billing.py
# ---------------------------------------------------------------------------
@pytest.fixture
def billing_app(monkeypatch):
    from api import billing
    calls = []

    async def fake_checkout_completed(db, obj):
        calls.append(obj)

    monkeypatch.setattr(billing, "handle_checkout_completed", fake_checkout_completed)
    monkeypatch.setattr(billing, "STRIPE_WEBHOOK_SECRET", "")
    app = FastAPI()
    app.include_router(billing.router, prefix="/api")
    app.dependency_overrides[billing.get_db] = lambda: None
    return TestClient(app, raise_server_exceptions=False), calls


def _event(obj):
    return {"id": "evt_1", "object": "event", "type": "checkout.session.completed",
            "data": {"object": obj}}


class TestWebhook:
    def test_foreign_session_goes_to_existing_handler(self, pdb, fs, billing_app):
        client, calls = billing_app
        obj = {"id": "cs_other_product", "object": "checkout.session",
               "metadata": {"tier": "professional"}, "customer": "cus_x"}
        r = client.post("/api/billing/webhook", json=_event(obj))
        assert r.status_code == 200 and "handled_by" not in r.json()
        assert len(calls) == 1
        assert not fs.of("Session.retrieve")

    def test_our_session_never_reaches_subscription_handler(self, pdb, fs, billing_app, mail):
        client, calls = billing_app
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u)
        r = client.post("/api/billing/webhook", json=_event(
            {"id": sid, "object": "checkout.session", "metadata": fs.sessions[sid]["metadata"]}))
        assert r.status_code == 200, r.text
        assert r.json()["handled_by"] == "bid_service"
        assert calls == []
        assert job["status"] == "preparing" and job["paid_via"] == "stripe"
        assert u["account_type"] == "managed_client"

    def test_payload_is_not_trusted(self, pdb, fs, billing_app):
        client, calls = billing_app
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u, paid=False)  # Stripe says: not paid
        forged = dict(fs.sessions[sid], payment_status="paid")
        r = client.post("/api/billing/webhook", json=_event(forged))
        assert r.status_code == 200
        assert job["paid_at"] is None and calls == []

    def test_stripe_outage_returns_500_for_retry(self, pdb, fs, billing_app):
        client, calls = billing_app
        obj = {"id": "cs_missing_00001", "object": "checkout.session",
               "metadata": {"product": "nabavkidata", "kind": "bid_prep_fee",
                            "job_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4())}}
        r = client.post("/api/billing/webhook", json=_event(obj))
        assert r.status_code == 500 and calls == []

    def test_setup_session_via_webhook(self, pdb, fs, billing_app):
        client, calls = billing_app
        u = pdb.add_user(**_unauthorised())
        sid = fs.add_setup_session(u)
        r = client.post("/api/billing/webhook", json=_event(
            {"id": sid, "object": "checkout.session", "metadata": fs.sessions[sid]["metadata"]}))
        assert r.status_code == 200 and calls == []
        assert u["stripe_mandate_pm_id"] == "pm_card_2"
        assert u["success_fee_authorised_via"] == "card"


# ---------------------------------------------------------------------------
# Billing (card mandate) and invoice choice
# ---------------------------------------------------------------------------
class TestBilling:
    def test_status_shape(self, pdb, fs, make_client):
        u = pdb.add_user(**_unauthorised())
        r = make_client(u).get(f"{API}/billing/status")
        assert r.status_code == 200
        assert set(r.json()) == {"has_card", "card_brand", "card_last4", "terms_accepted",
                                 "current_version", "success_fee_pct", "success_fee_authorised",
                                 "success_fee_authorised_at", "success_fee_authorised_via",
                                 "card_payments_enabled"}
        assert r.json()["card_payments_enabled"] is True and r.json()["has_card"] is False

    def test_setup_checkout(self, pdb, fs, make_client):
        u = pdb.add_user()
        r = make_client(u).post(f"{API}/billing/setup-checkout")
        assert r.status_code == 200
        (_, kw), = fs.of("Session.create")
        assert kw["mode"] == "setup" and kw["metadata"]["kind"] == "card_setup"
        assert kw["setup_intent_data"]["metadata"]["user_id"] == str(u["user_id"])
        assert kw["success_url"].endswith("/portal/billing?setup={CHECKOUT_SESSION_ID}")

    def test_setup_complete_authorises_only_with_current_terms(self, pdb, fs, make_client):
        u = pdb.add_user(**_unauthorised(agreement_version="2026-10"))
        c = make_client(u)
        sid = fs.add_setup_session(u)
        r = c.post(f"{API}/billing/setup-complete", json={"session_id": sid})
        assert r.status_code == 200, r.text
        assert r.json()["has_card"] is True and r.json()["card_last4"] == "5555"
        assert r.json()["success_fee_authorised"] is False
        assert r.json()["terms_accepted"] is False
        r = c.post(f"{API}/agreement/accept", json={"version": bid_jobs.AGREEMENT_VERSION})
        assert r.status_code == 200 and r.json()["success_fee_authorised"] is True
        assert u["success_fee_authorised_via"] == "card"

    def test_setup_complete_rejects_other_users_session(self, pdb, fs, make_client):
        u = pdb.add_user(**_unauthorised())
        other = pdb.add_user()
        sid = fs.add_setup_session(other)
        r = make_client(u).post(f"{API}/billing/setup-complete", json={"session_id": sid})
        assert r.status_code == 400 and u["stripe_mandate_pm_id"] is None

    def test_choose_invoice(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        c = make_client(u)
        r = c.post(f"{API}/jobs/{job['id']}/choose-invoice")
        assert r.status_code == 200, r.text
        assert r.json()["payment"]["invoice_requested_at"] is not None
        assert r.json()["payment"]["required"] is True
        first = job["invoice_requested_at"]
        assert c.post(f"{API}/jobs/{job['id']}/choose-invoice").status_code == 200
        assert job["invoice_requested_at"] == first
        sent = mail.by_tag("bid-job-invoice_requested")
        assert len(sent) == 1 and sent[0]["to"] == bid_notifications.ADMIN_EMAIL
        assert pdb.audit_events(job["id"]).count("invoice_requested") == 1
        # the invoice route still ends at the admin's mark-paid
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        assert admin.post(f"{API}/admin/jobs/{job['id']}/mark-paid", json={}).status_code == 200
        assert job["paid_via"] == "invoice"
        ready = pdb.add_job(u["user_id"], tender_id="8/2026", status="ready")
        assert c.post(f"{API}/jobs/{ready['id']}/choose-invoice").status_code == 409


# ---------------------------------------------------------------------------
# Begin, publish gate, offline authorisation
# ---------------------------------------------------------------------------
class TestBeginAndGate:
    def test_free_drafting_begin_skips_fee_gate(self, pdb, make_client):
        u = pdb.add_user(free_drafting=True)
        pdb.add_tender()
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 200 and r.json()["payment_required"] is False
        job = next(iter(pdb.jobs.values()))
        assert job["status"] == "preparing" and job["free"] is True and job["paid_via"] == "free"
        assert u["account_type"] == "managed_client"

    def test_zero_fee_begin_is_free(self, pdb, make_client):
        u = pdb.add_user(prep_fee_mkd=0)
        pdb.add_tender()
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.json()["job"]["status"] == "preparing"
        assert u["account_type"] == "managed_client"

    def test_admin_create_still_requested(self, pdb, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(API + "/admin/jobs", json={"user_id": str(u["user_id"]),
                                                  "tender_id": "17400/2026"})
        assert r.status_code == 200 and r.json()["job"]["status"] == "requested"

    def test_publish_gate_and_offline_authorisation(self, pdb, make_client, files_dir):
        u = pdb.add_user(**_unauthorised())
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="preparing", paid_at=datetime.now(timezone.utc))
        pdb.add_file(job["id"], client_visible=False)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/jobs/{job['id']}/publish")
        assert r.status_code == 409
        d = r.json()["detail"]
        assert d["code"] == "success_fee_not_authorised" and d["missing"] == ["card"]
        detail = admin.get(f"{API}/admin/jobs/{job['id']}").json()
        assert "картичка" in detail["job"]["publish_blocked_reason"]
        assert detail["client"]["has_card"] is False
        r = admin.post(f"{API}/admin/clients/{u['user_id']}/authorise-success-fee",
                       json={"reference": "Договор бр. 12/2026"})
        assert r.status_code == 200
        assert r.json()["client"]["success_fee_authorised_via"] == "offline"
        assert r.json()["client"]["success_fee_authorised_ref"] == "Договор бр. 12/2026"
        assert admin.get(f"{API}/admin/jobs/{job['id']}").json()["job"]["publish_blocked_reason"] is None
        assert admin.post(f"{API}/admin/jobs/{job['id']}/publish").status_code == 200
        assert admin.post(f"{API}/admin/clients/{uuid.uuid4()}/authorise-success-fee",
                          json={"reference": "abc"}).status_code == 404

    def test_publish_gate_missing_terms_and_card(self, pdb, make_client):
        u = pdb.add_user(**_unauthorised(agreement_version="2026-10"))
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="preparing", paid_at=datetime.now(timezone.utc))
        pdb.add_file(job["id"], client_visible=False)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/jobs/{job['id']}/publish")
        assert r.json()["detail"]["missing"] == ["terms", "card"]

    def test_publish_gate_refreshes_card_authorisation(self, pdb, make_client):
        u = pdb.add_user(**_unauthorised(stripe_mandate_pm_id="pm_x"))
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="preparing", paid_at=datetime.now(timezone.utc))
        pdb.add_file(job["id"], client_visible=False)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        assert admin.post(f"{API}/admin/jobs/{job['id']}/publish").status_code == 200
        assert u["success_fee_authorised_via"] == "card"

    def test_zero_success_fee_is_not_gated(self, pdb, make_client):
        u = pdb.add_user(**_unauthorised())
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="preparing", success_fee_pct=0)
        pdb.add_file(job["id"], client_visible=False)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        assert admin.post(f"{API}/admin/jobs/{job['id']}/publish").status_code == 200


# ---------------------------------------------------------------------------
# Wins
# ---------------------------------------------------------------------------
class TestWins:
    def test_outcome_won_creates_suspected_win_once(self, pdb, make_client):
        u = pdb.add_user(company_name="Фактурино ДООЕЛ")
        pdb.add_tender(actual_value_mkd=600000, contract_duration="12 месеци")
        job = pdb.add_job(u["user_id"], status="submitted", paid_at=datetime.now(timezone.utc),
                          prep_fee_mkd=10000, success_fee_pct=5)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        assert admin.post(f"{API}/admin/jobs/{job['id']}/outcome",
                          json={"outcome": "won"}).status_code == 200
        (w,) = pdb.wins.values()
        assert w["status"] == "suspected" and w["matched_name"] == "Фактурино ДООЕЛ"
        assert float(w["match_score"]) == 1.0 and w["value_source"] == "actual"
        assert w["prep_fee_credit_mkd"] == 10000 and w["success_fee_mkd"] == 20000
        admin.post(f"{API}/admin/jobs/{job['id']}/outcome", json={"outcome": "lost"})
        admin.post(f"{API}/admin/jobs/{job['id']}/outcome", json={"outcome": "won"})
        assert len(pdb.wins) == 1

    def test_confirm_creates_draft_invoice_before_item(self, pdb, fs, make_client, mail):
        u = pdb.add_user(stripe_customer_id="cus_1", stripe_mandate_pm_id="pm_1")
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="submitted")
        w = pdb.add_win(u["user_id"], job_id=job["id"], success_fee_pct=5, prep_fee_credit_mkd=0)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/wins/{w['id']}/confirm",
                       json={"first_year_value_mkd": 2_000_000})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["win"]["status"] == "confirmed" and body["win"]["success_fee_mkd"] == 100000
        assert body["win"]["charge_not_before"] is not None
        assert body["invoice"]["created"] is True and body["invoice"]["stripe_invoice_id"] == "in_draft_1"
        names = [c[0] for c in fs.calls if c[0] in ("Invoice.create", "InvoiceItem.create")]
        assert names == ["Invoice.create", "InvoiceItem.create"]
        inv_kw = fs.of("Invoice.create")[0][1]
        assert inv_kw["auto_advance"] is False and inv_kw["currency"] == "mkd"
        assert inv_kw["collection_method"] == "charge_automatically"
        assert inv_kw["default_payment_method"] == "pm_1"
        assert inv_kw["metadata"]["kind"] == "success_fee"
        item_kw = fs.of("InvoiceItem.create")[0][1]
        assert item_kw["invoice"] == "in_draft_1" and item_kw["amount"] == 10_000_000
        assert "(5%)" in item_kw["description"]
        assert w["stripe_invoice_id"] == "in_draft_1"
        assert job["status"] == "won" and job["outcome"] == "won"
        assert len(mail.by_tag("bid-job-won")) == 1
        notice = mail.by_tag("bid-job-success_fee_notice")
        assert len(notice) == 1 and notice[0]["to"] == u["email"]
        assert "100" not in notice[0]["subject"] + notice[0]["html"].split("/portal/")[0]
        # only once
        assert admin.post(f"{API}/admin/wins/{w['id']}/confirm", json={}).status_code == 409

    def test_confirm_without_card_and_invoiced_flow(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="won", outcome="won")
        w = pdb.add_win(u["user_id"], job_id=job["id"])
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/wins/{w['id']}/confirm", json={"success_fee_mkd": 12345})
        assert r.status_code == 200
        assert r.json()["invoice"]["created"] is False
        assert r.json()["invoice"]["message"] == bid_jobs.ERR_NO_CARD_FOR_INVOICE
        assert w["success_fee_mkd"] == 12345 and not fs.of("Invoice.create")
        assert admin.post(f"{API}/admin/wins/{w['id']}/dismiss", json={}).status_code == 200
        w2 = pdb.add_win(u["user_id"], job_id=None, tender_id="77/2026", status="confirmed")
        r = admin.post(f"{API}/admin/wins/{w2['id']}/mark-invoiced",
                       json={"invoice_number": "ФА-3/2026"})
        assert r.status_code == 200 and r.json()["win"]["invoice_number"] == "ФА-3/2026"
        assert admin.post(f"{API}/admin/wins/{w2['id']}/mark-invoiced", json={}).status_code == 409

    def test_confirm_stripe_failure_still_confirms(self, pdb, fs, make_client, monkeypatch):
        u = pdb.add_user(stripe_customer_id="cus_1", stripe_mandate_pm_id="pm_1")
        w = pdb.add_win(u["user_id"])

        def boom(**kw):
            raise real_stripe.error.APIConnectionError("down")
        monkeypatch.setattr(fs.Invoice, "create", staticmethod(boom))
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/wins/{w['id']}/confirm", json={})
        assert r.status_code == 200 and r.json()["win"]["status"] == "confirmed"
        assert r.json()["invoice"]["created"] is False and "down" in r.json()["invoice"]["message"]

    def test_notice_clock_starts_only_when_email_sent(self, pdb, fs, make_client, monkeypatch,
                                                        mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="won", outcome="won")
        w = pdb.add_win(u["user_id"], job_id=job["id"])
        sent = {"ok": False}

        async def flaky_send(**kw):
            if not sent["ok"]:
                return False
            return await mail(**kw)
        monkeypatch.setattr(bid_notifications.postmark_service, "send_email", flaky_send)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/wins/{w['id']}/confirm", json={})
        assert r.status_code == 200
        assert r.json()["notice"]["sent"] is False
        assert r.json()["notice"]["message"] == bid_jobs.MSG_NOTICE_FAILED
        assert w["status"] == "confirmed"
        assert w["notice_sent_at"] is None and w["charge_not_before"] is None
        sent["ok"] = True
        r = admin.post(f"{API}/admin/wins/{w['id']}/send-notice")
        assert r.status_code == 200 and r.json()["notice"]["sent"] is True
        assert w["notice_sent_at"] is not None and w["charge_not_before"] is not None
        assert len(mail.by_tag("bid-job-success_fee_notice")) == 1
        # sent once: a second resend is refused
        assert admin.post(f"{API}/admin/wins/{w['id']}/send-notice").status_code == 409

    def test_no_notice_without_job_or_fee(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        w = pdb.add_win(u["user_id"], job_id=None)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/wins/{w['id']}/confirm", json={})
        assert r.json()["notice"] == {"sent": False, "message": bid_jobs.MSG_NOTICE_NO_JOB}
        assert w["charge_not_before"] is None
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="won", outcome="won")
        w2 = pdb.add_win(u["user_id"], job_id=job["id"], tender_id="5/2026")
        r = admin.post(f"{API}/admin/wins/{w2['id']}/confirm", json={"success_fee_mkd": 0})
        assert r.json()["notice"]["message"] == bid_jobs.MSG_NOTICE_NO_FEE
        assert not mail.by_tag("bid-job-success_fee_notice")

    def test_confirm_refuses_missing_pct_and_estimated_value(self, pdb, make_client):
        u = pdb.add_user()
        w = pdb.add_win(u["user_id"], success_fee_pct=None)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/wins/{w['id']}/confirm",
                       json={"first_year_value_mkd": 1_000_000})
        assert r.status_code == 400 and r.json()["detail"] == bid_jobs.ERR_PCT_MISSING
        assert admin.post(f"{API}/admin/wins/{w['id']}/confirm",
                          json={"success_fee_mkd": 5000}).status_code == 200
        w2 = pdb.add_win(u["user_id"], tender_id="9/2026", value_source="estimated")
        r = admin.post(f"{API}/admin/wins/{w2['id']}/confirm", json={})
        assert r.status_code == 400 and r.json()["detail"] == bid_jobs.ERR_ESTIMATED_VALUE
        assert w2["status"] == "suspected"
        assert admin.post(f"{API}/admin/wins/{w2['id']}/confirm",
                          json={"first_year_value_mkd": 800_000}).status_code == 200

    def test_dismiss_deletes_stripe_draft(self, pdb, fs, make_client):
        u = pdb.add_user()
        w = pdb.add_win(u["user_id"], status="confirmed", stripe_invoice_id="in_draft_9")
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.post(f"{API}/admin/wins/{w['id']}/dismiss", json={})
        assert r.status_code == 200 and "in_draft_9" in r.json()["message"]
        assert fs.of("Invoice.delete") == [("Invoice.delete", "in_draft_9")]
        assert w["status"] == "dismissed"

    def test_list_and_summary(self, pdb, make_client):
        u = pdb.add_user()
        pdb.add_win(u["user_id"], success_fee_mkd=1000)
        pdb.add_win(u["user_id"], tender_id="2/2026", status="confirmed", success_fee_mkd=500)
        admin = make_client(pdb.add_user(role="admin", account_type="free"), admin=True)
        r = admin.get(f"{API}/admin/wins")
        assert r.status_code == 200
        s = r.json()["summary"]
        assert s["suspected"] == 1 and s["confirmed"] == 1
        assert s["pipeline_fee_mkd"] == 1000 and s["confirmed_fee_mkd"] == 500
        assert len(r.json()["wins"]) == 2 and r.json()["wins"][0]["email"] == u["email"]
        assert admin.get(f"{API}/admin/wins?status=bogus").status_code == 400

    def test_client_sees_confirmed_success_fee(self, pdb, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="won")
        pdb.add_win(u["user_id"], job_id=job["id"], status="confirmed", success_fee_mkd=30000,
                    charge_not_before=datetime.now(timezone.utc) + timedelta(days=7))
        pay = make_client(u).get(f"{API}/jobs/{job['id']}").json()["payment"]
        assert pay["success_fee"]["fee_mkd"] == 30000 and pay["success_fee"]["stripe"] is False
        assert pay["success_fee"]["charge_not_before"] is not None
