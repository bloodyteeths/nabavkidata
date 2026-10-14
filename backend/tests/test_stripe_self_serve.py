"""
Acceptance tests for Phase 2b self-serve payments (owner decisions 14 Oct 2026):
Stripe Checkout prep fee, return leg + webhook sharing one idempotent mark-paid,
invoice alternative, card mandate / success-fee authorisation, publish gate,
win detection and the DRAFT success-fee invoice, and qualify auto-login.

Stripe is never called (services.bid_payments.stripe is a FakeStripe), Postmark
is a recorder and the database is the in-memory FakeDB from test_bid_jobs.py.

Run:  cd backend && venv/bin/python -m pytest tests/test_stripe_self_serve.py -q --noconftest
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from test_bid_jobs import (API, bid_jobs, bid_notifications, db, files_dir,  # noqa: E402,F401
                           mail, make_client)
from test_bid_payments import FakeStripe, billing_app, fs, pdb, _event  # noqa: E402,F401
from services import bid_payments  # noqa: E402


def _admin(pdb, make_client):
    return make_client(pdb.add_user(role="admin", account_type="free"), admin=True)


def _unauthorised(**kw):
    base = dict(success_fee_authorised_at=None, success_fee_authorised_via=None,
                success_fee_authorised_ref=None)
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# pay-prep
# ---------------------------------------------------------------------------
class TestPayPrep:
    def test_amount_is_db_fee_in_mkd_minor_units_never_client_input(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required", prep_fee_mkd=18500)
        r = make_client(u).post(
            f"{API}/jobs/{job['id']}/pay-prep?amount=1&currency=eur",
            json={"amount": 1, "unit_amount": 100, "currency": "eur", "prep_fee_mkd": 1})
        assert r.status_code == 200, r.text
        (_, kw), = fs.of("Session.create")
        (item,) = kw["line_items"]
        assert item["quantity"] == 1
        assert item["price_data"]["currency"] == "mkd"
        assert item["price_data"]["unit_amount"] == 18500 * 100
        assert kw["payment_intent_data"]["setup_future_usage"] == "off_session"
        assert kw["metadata"]["job_id"] == str(job["id"])
        assert kw["metadata"]["user_id"] == str(u["user_id"])

    def test_fee_changed_by_admin_is_picked_up(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required", prep_fee_mkd=30000)
        job["prep_fee_mkd"] = 12000  # admin lowered the fee before the client paid
        assert make_client(u).post(f"{API}/jobs/{job['id']}/pay-prep").status_code == 200
        assert fs.of("Session.create")[0][1]["line_items"][0]["price_data"]["unit_amount"] == 1_200_000

    @pytest.mark.parametrize("status,ok", [
        ("requested", True), ("payment_required", True), ("preparing", False),
        ("ready", False), ("submitted", False), ("won", False), ("cancelled", False),
    ])
    def test_only_while_fee_is_due(self, pdb, fs, make_client, status, ok):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status=status)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/pay-prep")
        assert r.status_code == (200 if ok else 409), r.text
        assert bool(fs.of("Session.create")) is ok

    def test_only_own_job(self, pdb, fs, make_client):
        owner = pdb.add_user()
        intruder = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(owner["user_id"], status="payment_required")
        r = make_client(intruder).post(f"{API}/jobs/{job['id']}/pay-prep")
        assert r.status_code == 404
        assert not fs.of("Session.create") and not fs.of("Customer.create")

    def test_free_user_is_not_a_portal_user(self, pdb, fs, make_client):
        u = pdb.add_user(account_type="free")
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        assert make_client(u).post(f"{API}/jobs/{job['id']}/pay-prep").status_code == 403
        assert not fs.of("Session.create")

    def test_free_jobs_skip_payment(self, pdb, fs, make_client):
        u = pdb.add_user(free_drafting=True)
        pdb.add_tender()
        c = make_client(u)
        r = c.post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 200 and r.json()["payment_required"] is False
        job = next(iter(pdb.jobs.values()))
        assert job["status"] == "preparing" and job["free"] is True
        detail = c.get(f"{API}/jobs/{job['id']}").json()
        assert detail["payment"]["required"] is False and detail["payment"]["can_pay_card"] is False
        assert c.post(f"{API}/jobs/{job['id']}/pay-prep").status_code == 409
        assert c.post(f"{API}/jobs/{job['id']}/choose-invoice").status_code == 409
        # a free job explicitly flagged free also never reaches Checkout
        other = pdb.add_job(u["user_id"], tender_id="2/2026", status="requested", free=True)
        assert c.post(f"{API}/jobs/{other['id']}/pay-prep").status_code == 409
        assert not fs.of("Session.create")

    def test_begin_lands_at_fee_gate(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        r = make_client(u).post(API + "/jobs", json={"tender_id": "17400/2026"})
        assert r.status_code == 200, r.text
        assert r.json()["payment_required"] is True
        assert r.json()["job"]["status"] == "payment_required"
        assert u["account_type"] == "prospect"  # no perks until paid


# ---------------------------------------------------------------------------
# prep-complete (return leg)
# ---------------------------------------------------------------------------
class TestPrepComplete:
    def test_twice_is_one_transition_and_one_email(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u)
        c = make_client(u)
        bodies = [c.post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid}).json()
                  for _ in range(2)]
        assert [b["paid"] for b in bodies] == [True, True]
        assert bodies[0]["account_promoted"] is True and bodies[1]["account_promoted"] is False
        assert bodies[1]["reason"] == "already_paid"
        assert pdb.audit_events(job["id"]).count("paid") == 1
        transitions = [e for e in pdb.events
                       if e["job_id"] == job["id"] and e["event"] == "paid"]
        assert len(transitions) == 1
        assert len(mail.by_tag("bid-job-preparing")) == 1
        assert len(mail.by_tag("bid-job-paid_online")) == 1
        assert u["account_type"] == "managed_client"

    def test_session_must_belong_to_job_and_user(self, pdb, fs, make_client):
        u = pdb.add_user()
        other = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        other_job = pdb.add_job(other["user_id"], status="payment_required")
        c = make_client(u)
        # the other user's real paid session, replayed against my job
        theirs = fs.add_prep_session(other_job, other, sid="cs_test_theirs_01")
        assert c.post(f"{API}/jobs/{job['id']}/prep-complete",
                      json={"session_id": theirs}).status_code == 400
        # their session replayed against their job by me: not my job
        assert c.post(f"{API}/jobs/{other_job['id']}/prep-complete",
                      json={"session_id": theirs}).status_code == 404
        # metadata user forged to mine but job is theirs
        forged = fs.add_prep_session(other_job, other, sid="cs_test_forged_1", user_id=u["user_id"])
        assert c.post(f"{API}/jobs/{job['id']}/prep-complete",
                      json={"session_id": forged}).status_code == 400
        # unknown session id
        assert c.post(f"{API}/jobs/{job['id']}/prep-complete",
                      json={"session_id": "cs_test_nonexistent"}).status_code == 400
        assert job["paid_at"] is None and other_job["paid_at"] is None
        assert u["account_type"] == "prospect"

    def test_unpaid_session_is_402_and_not_marked(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u, paid=False)
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 402
        assert job["paid_at"] is None and not mail.by_tag("bid-job-preparing")

    def test_session_id_validation(self, pdb, fs, make_client):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": "x"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Webhook (api/billing.py, shared Stripe account)
# ---------------------------------------------------------------------------
class TestWebhook:
    def _ours(self, fs, sid):
        return {"id": sid, "object": "checkout.session", "metadata": fs.sessions[sid]["metadata"]}

    def test_ours_marks_paid_idempotently(self, pdb, fs, billing_app, mail):
        client, calls = billing_app
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u)
        for _ in range(3):  # Stripe redelivers
            r = client.post("/api/billing/webhook", json=_event(self._ours(fs, sid)))
            assert r.status_code == 200 and r.json()["handled_by"] == "bid_service"
        assert calls == []
        assert job["status"] == "preparing" and job["paid_via"] == "stripe"
        assert pdb.audit_events(job["id"]).count("paid") == 1
        assert len(mail.by_tag("bid-job-preparing")) == 1
        assert len(mail.by_tag("bid-job-paid_online")) == 1
        assert not mail.by_tag("bid-job-payment_alert")

    def test_webhook_then_return_leg(self, pdb, fs, billing_app, make_client, mail):
        client, _ = billing_app
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u)
        assert client.post("/api/billing/webhook", json=_event(self._ours(fs, sid))).status_code == 200
        r = make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.status_code == 200 and r.json()["paid"] is True
        assert r.json()["job"]["status"] == "preparing"
        assert pdb.audit_events(job["id"]).count("paid") == 1
        assert len(mail.by_tag("bid-job-preparing")) == 1

    @pytest.mark.parametrize("metadata", [
        {"product": "tenderuk", "kind": "bid_prep_fee", "job_id": "x", "user_id": "y"},
        {"product": "nabavkidata", "kind": "subscription"},
        {"tier": "professional"},
        {},
    ])
    def test_foreign_sessions_go_to_existing_handler(self, pdb, fs, billing_app, metadata):
        client, calls = billing_app
        obj = {"id": "cs_foreign_0001", "object": "checkout.session", "metadata": metadata,
               "customer": "cus_x", "client_reference_id": str(uuid.uuid4())}
        r = client.post("/api/billing/webhook", json=_event(obj))
        assert r.status_code == 200 and "handled_by" not in r.json()
        assert len(calls) == 1 and calls[0]["id"] == "cs_foreign_0001"
        assert not fs.of("Session.retrieve")

    @pytest.mark.parametrize("etype,handler", [
        ("customer.subscription.created", "handle_subscription_created"),
        ("customer.subscription.updated", "handle_subscription_updated"),
        ("customer.subscription.deleted", "handle_subscription_deleted"),
        ("invoice.payment_succeeded", "handle_payment_succeeded"),
        ("invoice.payment_failed", "handle_payment_failed"),
    ])
    def test_subscription_events_still_routed(self, pdb, fs, billing_app, monkeypatch,
                                              etype, handler):
        from api import billing
        client, calls = billing_app
        seen = []

        async def rec(db, obj):
            seen.append(obj["id"])
        monkeypatch.setattr(billing, handler, rec)
        # even an object carrying our metadata is not ours unless it is a checkout session event
        obj = {"id": "obj_1", "object": "subscription",
               "metadata": {"product": "nabavkidata", "kind": "bid_prep_fee"}}
        r = client.post("/api/billing/webhook",
                        json={"id": "evt_2", "object": "event", "type": etype,
                              "data": {"object": obj}})
        assert r.status_code == 200 and "handled_by" not in r.json()
        assert seen == ["obj_1"] and calls == []
        assert not fs.of("Session.retrieve")


# ---------------------------------------------------------------------------
# Invoice route
# ---------------------------------------------------------------------------
class TestInvoiceRoute:
    def test_choose_invoice_then_admin_marks_paid(self, pdb, fs, make_client, mail):
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        c = make_client(u)
        r = c.post(f"{API}/jobs/{job['id']}/choose-invoice")
        assert r.status_code == 200
        assert r.json()["payment"]["invoice_requested_at"]
        assert job["status"] == "payment_required" and job["paid_at"] is None
        assert len(mail.by_tag("bid-job-invoice_requested")) == 1
        admin = _admin(pdb, make_client)
        r = admin.post(f"{API}/admin/jobs/{job['id']}/mark-paid", json={})
        assert r.status_code == 200 and r.json()["account_promoted"] is True
        assert job["status"] == "preparing" and job["paid_via"] == "invoice"
        assert u["account_type"] == "managed_client"
        assert not fs.calls  # the invoice route never touches Stripe
        # a later card session for the same job is a duplicate: alert, no second transition
        sid = fs.add_prep_session(job, u)
        r = c.post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert r.json()["reason"] == "duplicate"
        assert pdb.audit_events(job["id"]).count("paid") == 1
        assert len(mail.by_tag("bid-job-payment_alert")) == 1

    def test_invoice_available_when_card_payments_are_off(self, pdb, fs, make_client,
                                                          monkeypatch):
        monkeypatch.setattr(bid_payments, "STRIPE_SECRET_KEY", "")
        u = pdb.add_user()
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        c = make_client(u)
        pay = c.get(f"{API}/jobs/{job['id']}").json()["payment"]
        assert pay["required"] is True and pay["can_pay_card"] is False
        assert c.post(f"{API}/jobs/{job['id']}/pay-prep").status_code == 503
        assert c.post(f"{API}/jobs/{job['id']}/choose-invoice").status_code == 200
        assert c.get(f"{API}/billing/status").json()["card_payments_enabled"] is False
        assert c.post(f"{API}/billing/setup-checkout").status_code == 503


# ---------------------------------------------------------------------------
# Card mandate + success-fee authorisation
# ---------------------------------------------------------------------------
class TestSetup:
    def test_setup_checkout_then_complete_stores_mandate_and_authorises(self, pdb, fs,
                                                                         make_client):
        u = pdb.add_user(**_unauthorised())
        c = make_client(u)
        r = c.post(f"{API}/billing/setup-checkout")
        assert r.status_code == 200 and r.json()["url"]
        (_, kw), = fs.of("Session.create")
        assert kw["mode"] == "setup" and kw["payment_method_types"] == ["card"]
        assert kw["customer"] == u["stripe_customer_id"]
        assert kw["metadata"] == {"product": "nabavkidata", "kind": "card_setup",
                                  "user_id": str(u["user_id"])}
        sid = fs.add_setup_session(u)
        r = c.post(f"{API}/billing/setup-complete", json={"session_id": sid})
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["has_card"] is True and st["card_brand"] == "mastercard"
        assert st["success_fee_authorised"] is True and st["success_fee_authorised_via"] == "card"
        assert u["stripe_mandate_pm_id"] == "pm_card_2"
        assert u["success_fee_authorised_at"] is not None
        assert ("Customer.modify", "cus_existing",
                {"invoice_settings": {"default_payment_method": "pm_card_2"}}) in fs.calls

    def test_setup_replaces_card_but_keeps_authorisation(self, pdb, fs, make_client):
        when = datetime(2026, 10, 1, tzinfo=timezone.utc)
        u = pdb.add_user(stripe_mandate_pm_id="pm_old", stripe_card_last4="1111",
                         success_fee_authorised_at=when, success_fee_authorised_via="card")
        sid = fs.add_setup_session(u)
        r = make_client(u).post(f"{API}/billing/setup-complete", json={"session_id": sid})
        assert r.status_code == 200
        assert u["stripe_mandate_pm_id"] == "pm_card_2" and u["stripe_card_last4"] == "5555"
        assert u["success_fee_authorised_at"] == when

    def test_prep_payment_does_not_replace_existing_mandate(self, pdb, fs, make_client):
        u = pdb.add_user(stripe_mandate_pm_id="pm_old", stripe_card_last4="1111")
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="payment_required")
        sid = fs.add_prep_session(job, u)
        make_client(u).post(f"{API}/jobs/{job['id']}/prep-complete", json={"session_id": sid})
        assert u["stripe_mandate_pm_id"] == "pm_old" and u["stripe_card_last4"] == "1111"
        assert job["paid_via"] == "stripe"

    def test_no_authorisation_without_current_terms(self, pdb, fs, make_client):
        u = pdb.add_user(**_unauthorised(terms_agreed_at=None, agreement_version=None))
        sid = fs.add_setup_session(u)
        st = make_client(u).post(f"{API}/billing/setup-complete", json={"session_id": sid}).json()
        assert st["has_card"] is True and st["success_fee_authorised"] is False
        assert u["success_fee_authorised_at"] is None


# ---------------------------------------------------------------------------
# Publish gate
# ---------------------------------------------------------------------------
class TestPublishGate:
    def _ready_to_publish(self, pdb, **user_kw):
        u = pdb.add_user(**_unauthorised(**user_kw))
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="preparing", paid_at=datetime.now(timezone.utc),
                          paid_via="invoice")
        pdb.add_file(job["id"], client_visible=False)
        return u, job

    def test_blocked_without_authorisation(self, pdb, make_client, files_dir, mail):
        u, job = self._ready_to_publish(pdb)
        admin = _admin(pdb, make_client)
        r = admin.post(f"{API}/admin/jobs/{job['id']}/publish")
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "success_fee_not_authorised"
        assert job["status"] == "preparing" and job["published_at"] is None
        assert not mail.by_tag("bid-job-ready")

    def test_allowed_after_offline_authorisation(self, pdb, make_client, files_dir, mail):
        u, job = self._ready_to_publish(pdb)
        admin = _admin(pdb, make_client)
        r = admin.post(f"{API}/admin/clients/{u['user_id']}/authorise-success-fee",
                       json={"reference": "Писмен договор 7/2026"})
        assert r.status_code == 200
        assert u["success_fee_authorised_via"] == "offline"
        r = admin.post(f"{API}/admin/jobs/{job['id']}/publish")
        assert r.status_code == 200, r.text
        assert job["status"] == "ready"
        # offline authorisation is not overwritten by a later card
        assert admin.post(f"{API}/admin/clients/{u['user_id']}/authorise-success-fee",
                          json={"reference": "друго"}).status_code == 200
        assert u["success_fee_authorised_ref"] == "Писмен договор 7/2026"

    def test_reference_length_validated(self, pdb, make_client):
        u = pdb.add_user()
        admin = _admin(pdb, make_client)
        assert admin.post(f"{API}/admin/clients/{u['user_id']}/authorise-success-fee",
                          json={"reference": "ab"}).status_code == 422

    def test_non_admin_cannot_authorise(self, pdb, make_client):
        u = pdb.add_user(**_unauthorised())
        r = make_client(u).post(f"{API}/admin/clients/{u['user_id']}/authorise-success-fee",
                                json={"reference": "сам себе"})
        assert r.status_code in (401, 403)
        assert u["success_fee_authorised_at"] is None


# ---------------------------------------------------------------------------
# Win detection + success fee
# ---------------------------------------------------------------------------
class TestWinDetection:
    def test_fee_is_pct_of_first_year_value_without_cap(self, monkeypatch):
        import test_detect_client_wins as tdw
        from services import client_wins as cw

        sent = []

        async def fake_notify(job_id, kind, extra=None):
            sent.append(kind)
            return True
        monkeypatch.setattr(tdw.cron.bid_notifications, "notify", fake_notify)
        big = tdw._cand(tender_id="900/2026", winner="FAKTURINO DOOEL Veles",
                        actual_value_mkd=240_000_000, estimated_value_mkd=None,
                        contract_duration="24 месеци", success_fee_pct=5, prep_fee_mkd=30000)
        nomatch = tdw._cand(tender_id="901/2026", winner="Семос ДОО Скопје")
        conn = tdw.FakeConn([big, nomatch], {})
        stats = tdw._run(monkeypatch, conn)
        assert stats["matched"] == 1 and stats["inserted"] == 1
        row = dict(zip(cw.WIN_COLUMNS, conn.inserted[0]))
        assert row["contract_months"] == 24
        assert row["first_year_value_mkd"] == Decimal("120000000.00")
        # 5% of 120M first-year value minus the prep fee already paid; no cap.
        assert row["success_fee_mkd"] == 6_000_000 - 30000
        assert sent == ["win_detected"]

    def test_short_contract_uses_total(self):
        from services import client_wins as cw
        assert cw.first_year_value(600_000, 6) == 600_000
        assert cw.first_year_value(600_000, None) == 600_000
        assert cw.first_year_value(3_600_000, 36) == 1_200_000
        assert cw.compute_success_fee(cw.first_year_value(3_600_000, 36), 5, 0) == 60_000

    def test_similarity_threshold(self):
        from services import client_wins as cw
        a = cw.normalize_company("ФАКТУРИНО ДООЕЛ Велес")
        assert cw.trigram_similarity(a, cw.normalize_company("Fakturino DOOEL")) >= \
            cw.WIN_MATCH_THRESHOLD
        assert cw.trigram_similarity(a, cw.normalize_company("Семос ДОО")) < cw.WIN_MATCH_THRESHOLD


class TestConfirmInvoice:
    def _win(self, pdb, **user_kw):
        u = pdb.add_user(**user_kw)
        pdb.add_tender()
        job = pdb.add_job(u["user_id"], status="submitted")
        w = pdb.add_win(u["user_id"], job_id=job["id"], success_fee_mkd=50000)
        return u, job, w

    def test_draft_invoice_with_mandate(self, pdb, fs, make_client):
        u, job, w = self._win(pdb, stripe_customer_id="cus_9", stripe_mandate_pm_id="pm_9")
        r = _admin(pdb, make_client).post(f"{API}/admin/wins/{w['id']}/confirm", json={})
        assert r.status_code == 200, r.text
        assert r.json()["invoice"]["created"] is True
        (_, inv), = fs.of("Invoice.create")
        assert inv["auto_advance"] is False and inv["customer"] == "cus_9"
        assert inv["default_payment_method"] == "pm_9" and inv["currency"] == "mkd"
        (_, item), = fs.of("InvoiceItem.create")
        assert item["invoice"] == "in_draft_1" and item["amount"] == 50000 * 100
        # never finalised, paid or sent from code
        assert not [c for c in fs.calls if c[0].split(".")[-1] in ("finalize_invoice", "pay",
                                                                   "send_invoice")]
        assert w["charge_not_before"] is not None and w["notice_sent_at"] is not None
        assert (w["charge_not_before"] - w["notice_sent_at"]).days == 7

    @pytest.mark.parametrize("user_kw", [
        {},                                         # no customer, no card
        {"stripe_customer_id": "cus_9"},            # customer but no saved card
        {"stripe_mandate_pm_id": "pm_9"},           # card id but no customer
    ])
    def test_no_invoice_without_mandate(self, pdb, fs, make_client, user_kw):
        u, job, w = self._win(pdb, **user_kw)
        r = _admin(pdb, make_client).post(f"{API}/admin/wins/{w['id']}/confirm", json={})
        assert r.status_code == 200
        assert r.json()["win"]["status"] == "confirmed"
        assert r.json()["invoice"] == {"created": False, "stripe_invoice_id": None,
                                       "message": bid_jobs.ERR_NO_CARD_FOR_INVOICE}
        assert not fs.of("Invoice.create") and not fs.of("InvoiceItem.create")

    def test_admin_can_opt_out_of_stripe_invoice(self, pdb, fs, make_client):
        u, job, w = self._win(pdb, stripe_customer_id="cus_9", stripe_mandate_pm_id="pm_9")
        r = _admin(pdb, make_client).post(f"{API}/admin/wins/{w['id']}/confirm",
                                          json={"create_stripe_invoice": False})
        assert r.status_code == 200 and r.json()["invoice"]["created"] is False
        assert not fs.of("Invoice.create")

    def test_confirmed_value_recomputes_fee_without_cap(self, pdb, fs, make_client):
        u, job, w = self._win(pdb)
        w.update(success_fee_pct=5, prep_fee_credit_mkd=25000)
        r = _admin(pdb, make_client).post(f"{API}/admin/wins/{w['id']}/confirm",
                                          json={"first_year_value_mkd": 400_000_000})
        assert r.json()["win"]["success_fee_mkd"] == 20_000_000 - 25000


# ---------------------------------------------------------------------------
# Qualify auto-login (BidFinder §4.2)
# ---------------------------------------------------------------------------
class TestQualifyAutoLogin:
    @pytest.fixture
    def qualify(self, monkeypatch):
        import test_bid_service as tbs
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        tbs.bid_service._qualify_hits.clear()
        monkeypatch.setattr(tbs.bid_service.postmark_service, "send_email", tbs.MailRecorder())

        def _make(conn):
            async def fake_pool():
                return tbs.FakePool(conn)
            monkeypatch.setattr(tbs.bid_service, "get_asyncpg_pool", fake_pool)
            app = FastAPI()
            app.include_router(tbs.bid_service.router, prefix="/api")
            return TestClient(app)
        yield tbs, _make
        tbs.bid_service._qualify_hits.clear()

    def test_new_email_gets_tokens_and_one_session(self, qualify):
        tbs, make = qualify
        conn = tbs.FakeConn()
        r = make(conn).post("/api/bid-service/qualify", json=tbs._payload(email="New@Firma.MK"))
        assert r.status_code == 200
        auth = r.json()["auth"]
        # Access token only: a refresh token would survive the real owner claiming it.
        assert auth and auth["access_token"] and auth["refresh_token"] is None
        sessions = conn.find("INSERT INTO user_sessions")
        assert len(sessions) == 1 and sessions[0][2][0] == conn.user_id
        lookup = conn.find("FROM users WHERE LOWER(email)")[0]
        assert lookup[2] == ("new@firma.mk",)
        ins = conn.find("INSERT INTO users")[0]
        assert ins[2][0] == "new@firma.mk" and "email_verified" in ins[1]

    @pytest.mark.parametrize("email", ["owner@firma.mk", "OWNER@FIRMA.MK", "  Owner@Firma.mk "])
    def test_existing_email_any_case_gets_no_tokens(self, qualify, email):
        tbs, make = qualify
        conn = tbs.FakeConn(existing_user={"user_id": uuid.uuid4(), "account_type": "managed_client"})
        r = make(conn).post("/api/bid-service/qualify", json=tbs._payload(email=email))
        assert r.status_code == 200
        assert r.json()["auth"] is None and r.json()["next"] is None
        assert conn.find("INSERT INTO user_sessions") == []
        assert conn.find("INSERT INTO users") == []
        assert conn.find("FROM users WHERE LOWER(email)")[0][2] == ("owner@firma.mk",)

    def test_race_lost_insert_gets_no_tokens(self, qualify):
        tbs, make = qualify
        conn = tbs.FakeConn(race_user={"user_id": uuid.uuid4(), "account_type": "free"})
        r = make(conn).post("/api/bid-service/qualify", json=tbs._payload())
        assert r.status_code == 200 and r.json()["auth"] is None
        assert conn.find("INSERT INTO user_sessions") == []

    def test_token_subject_is_never_from_request(self, qualify):
        from jose import jwt
        from api.auth import ALGORITHM, SECRET_KEY
        tbs, make = qualify
        conn = tbs.FakeConn()
        evil = str(uuid.uuid4())
        r = make(conn).post("/api/bid-service/qualify",
                            json=tbs._payload(user_id=evil, sub=evil),
                            headers={"Authorization": f"Bearer {evil}"})
        tok = jwt.decode(r.json()["auth"]["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        assert tok["sub"] == str(conn.user_id) != evil
