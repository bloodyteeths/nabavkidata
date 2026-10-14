"""
Self-serve card payments for the done-for-you bid service (Phase 2b, 14 Oct 2026).

Ported from BidFinder (tenderuk/backend/api/bid_service.py pay-prep /
prep-complete / billing setup-checkout + setup-complete), with these deliberate
differences:

- one idempotent mark_job_paid() shared by the Checkout return leg, the Stripe
  webhook (api/billing.py, shared "Atlas" account — only sessions whose
  metadata.product == "nabavkidata" and kind is ours are handled here) and the
  admin „Означи платено“ (invoice route);
- the amount always comes from the DB job, and the return leg / webhook
  re-check it against the paid session (amount_total) before marking paid;
- the webhook payload is never trusted: the session is re-retrieved from Stripe;
- a reused stripe_customer_id whose currency is not MKD (e.g. a churned EUR
  subscriber) is replaced, because a Stripe customer cannot mix currencies;
- all Stripe SDK calls are synchronous and run in asyncio.to_thread, and no DB
  connection is held while waiting on Stripe when the caller passes conn=None.

This module must not import api.bid_jobs (cycle): bid_jobs imports us.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Optional

import stripe

from db_pool import get_asyncpg_pool
from services import bid_notifications

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
if STRIPE_SECRET_KEY and not stripe.api_key:
    stripe.api_key = STRIPE_SECRET_KEY

# MKD is a Stripe presentment currency and is NOT zero-decimal: amounts are
# denars * 100. Keep the conversion here only.
STRIPE_CURRENCY = "mkd"
MINOR_UNITS = 100
PRODUCT_TAG = "nabavkidata"
KIND_PREP = "bid_prep_fee"
KIND_SETUP = "card_setup"
KIND_SUCCESS_FEE = "success_fee"
SITE = "https://nabavkidata.com"
ERR_CARD_UNAVAILABLE = ("Плаќањето со картичка моментално не е достапно. "
                        "Изберете плаќање со фактура.")

# Version of the service terms a client accepts before the first bid. Bump it
# when /terms changes materially. api.bid_jobs re-exports it.
AGREEMENT_VERSION = "2026-10-14"


class PaymentVerificationError(Exception):
    """The Stripe session does not belong to this job/user or is not ours."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def card_payments_enabled() -> bool:
    return bool(STRIPE_SECRET_KEY)


def to_minor(mkd: int | Decimal | float) -> int:
    return int(round(Decimal(str(mkd)))) * MINOR_UNITS


def _sget(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from a StripeObject, dict or plain object."""
    if obj is None:
        return default
    if isinstance(obj, Mapping) or hasattr(obj, "get"):
        try:
            v = obj.get(key, default)
            return default if v is None else v
        except Exception:
            pass
    return getattr(obj, key, default)


def _metadata(obj: Any) -> dict:
    md = _sget(obj, "metadata") or {}
    try:
        return dict(md)
    except Exception:
        return {}


def is_bid_service_session(obj: Any) -> bool:
    md = _metadata(obj)
    return md.get("product") == PRODUCT_TAG and md.get("kind") in {KIND_PREP, KIND_SETUP}


def _id_of(obj: Any) -> Optional[str]:
    """An expandable Stripe field is either an id string or an object."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    return _sget(obj, "id")


def _as_uuid(v: Any) -> uuid.UUID:
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


@asynccontextmanager
async def _conn_or_pool(conn):
    if conn is not None:
        yield conn
        return
    pool = await get_asyncpg_pool()
    async with pool.acquire() as c:
        yield c


async def _stripe(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)


async def _audit(conn, job_id, event: str, actor_role: str, actor_id=None,
                 detail: Optional[dict] = None) -> None:
    await conn.execute(
        "INSERT INTO bid_job_events (job_id, kind, event, actor_role, actor_user_id, detail) "
        "VALUES ($1,'audit',$2,$3,$4,$5::jsonb)",
        job_id, event, actor_role, actor_id, json.dumps(detail) if detail is not None else None,
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def promote_user(conn, user_id) -> bool:
    res = await conn.execute(
        "UPDATE users SET account_type='managed_client', updated_at=NOW() "
        "WHERE user_id=$1 AND account_type IN ('free','prospect')",
        user_id,
    )
    await conn.execute(
        "UPDATE bid_service_leads SET status='client', updated_at=NOW() "
        "WHERE user_id=$1 AND status IN ('new','contacted','qualified')",
        user_id,
    )
    return isinstance(res, str) and res.split()[-1] != "0"


async def ensure_stripe_customer(conn, user_id) -> str:
    """The client's MKD Stripe customer (created or reused). conn=None uses short
    pool connections so none is held during the Stripe calls."""
    async with _conn_or_pool(conn) as c:
        row = await c.fetchrow(
            "SELECT email, company_name, stripe_customer_id FROM users WHERE user_id = $1",
            user_id)
    if not row:
        raise LookupError("user not found")
    existing = row["stripe_customer_id"]
    if existing:
        try:
            cust = await _stripe(stripe.Customer.retrieve, existing)
            deleted = bool(_sget(cust, "deleted", False))
            currency = _sget(cust, "currency")
            if not deleted and currency in (None, "", STRIPE_CURRENCY):
                return existing
            logger.info("stripe customer %s unusable for MKD (deleted=%s currency=%s); "
                        "creating a new one for user %s", existing, deleted, currency, user_id)
        except stripe.error.InvalidRequestError:
            logger.warning("stripe customer %s not found; creating a new one", existing)
    cust = await _stripe(
        stripe.Customer.create,
        email=row["email"],
        name=row["company_name"] or None,
        metadata={"product": PRODUCT_TAG, "user_id": str(user_id)},
    )
    # Compare-and-set: two concurrent calls (double click) must agree on one
    # customer, so the mandate card and the success-fee invoice share it.
    async with _conn_or_pool(conn) as c:
        won = await c.fetchval(
            "UPDATE users SET stripe_customer_id = $2, updated_at = NOW() "
            "WHERE user_id = $1 AND stripe_customer_id IS NOT DISTINCT FROM $3 "
            "RETURNING stripe_customer_id",
            user_id, cust.id, existing)
        if won is None:
            winner = await c.fetchval(
                "SELECT stripe_customer_id FROM users WHERE user_id = $1", user_id)
    if won is None:
        logger.info("stripe customer race for user %s: using %s, %s unused",
                    user_id, winner, cust.id)
        if winner:
            return winner
    return cust.id


# ---------------------------------------------------------------------------
# Checkout sessions
# ---------------------------------------------------------------------------
async def create_prep_checkout(conn, job_row: Mapping, user_id) -> str:
    """Stripe hosted Checkout for the prep fee; the card is saved for the success fee."""
    job_id = str(job_row["id"])
    tender_id = str(job_row["tender_id"])
    fee = job_row["prep_fee_mkd"]
    if fee is None or int(fee) <= 0:
        raise ValueError("no prep fee due")
    cust = await ensure_stripe_customer(conn, user_id)
    md = {"product": PRODUCT_TAG, "kind": KIND_PREP, "job_id": job_id,
          "user_id": str(user_id), "tender_id": tender_id}
    session = await _stripe(
        stripe.checkout.Session.create,
        mode="payment",
        customer=cust,
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": STRIPE_CURRENCY,
                "unit_amount": to_minor(fee),  # always from the DB job, never the client
                "product_data": {"name": "Подготовка на понуда",
                                 "description": f"Тендер {tender_id}"},
            },
            "quantity": 1,
        }],
        # Keep the card on file from this same payment: the success fee is
        # collectable only from a stored card (BidFinder).
        payment_intent_data={
            "setup_future_usage": "off_session",
            "description": f"НабавкиДата: подготовка на понуда {tender_id}",
            "metadata": md,
        },
        client_reference_id=str(user_id),
        metadata=md,
        after_expiration={"recovery": {"enabled": True}},
        success_url=f"{SITE}/portal/bid/{job_id}?paid={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{SITE}/portal/bid/{job_id}?payment=cancelled",
    )
    return session.url


async def create_setup_checkout(conn, user_id) -> str:
    cust = await ensure_stripe_customer(conn, user_id)
    md = {"product": PRODUCT_TAG, "kind": KIND_SETUP, "user_id": str(user_id)}
    session = await _stripe(
        stripe.checkout.Session.create,
        mode="setup",
        payment_method_types=["card"],
        customer=cust,
        metadata=md,
        setup_intent_data={"metadata": md},
        success_url=f"{SITE}/portal/billing?setup={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{SITE}/portal/billing?setup=cancelled",
    )
    return session.url


async def retrieve_session(session_id: str):
    return await _stripe(
        stripe.checkout.Session.retrieve, session_id,
        expand=["payment_intent.payment_method", "setup_intent.payment_method"])


# ---------------------------------------------------------------------------
# Mandate + success-fee authorisation
# ---------------------------------------------------------------------------
def _card_details(pm: Any) -> tuple[Optional[str], Optional[str], Optional[str]]:
    pm_id = _id_of(pm)
    if pm is None or isinstance(pm, str):
        return pm_id, None, None
    card = _sget(pm, "card")
    brand = _sget(card, "brand")
    last4 = _sget(card, "last4")
    return pm_id, (str(brand)[:30] if brand else None), (str(last4)[:4] if last4 else None)


async def save_mandate(conn, user_id, pm, *, replace: bool, customer: Optional[str] = None) -> None:
    """Store the card as the success-fee mandate. replace=False keeps an existing
    mandate (BidFinder's COALESCE); the card becomes the customer's default
    payment method only when it is stored."""
    pm_id, brand, last4 = _card_details(pm)
    if not pm_id:
        return
    async with _conn_or_pool(conn) as c:
        row = await c.fetchrow(
            "SELECT stripe_mandate_pm_id, stripe_customer_id FROM users WHERE user_id = $1",
            user_id)
    if not row:
        raise LookupError("user not found")
    if row["stripe_mandate_pm_id"] and not replace:
        return
    # The card is attached to the session's customer; store that customer with
    # it so the success-fee invoice (customer + default_payment_method) always
    # pairs a card with the customer it belongs to.
    cust = customer or row["stripe_customer_id"]
    if cust:
        try:
            await _stripe(stripe.Customer.modify, cust,
                          invoice_settings={"default_payment_method": pm_id})
        except Exception:
            logger.exception("could not set default payment method for user %s", user_id)
    async with _conn_or_pool(conn) as c:
        if replace:
            await c.execute(
                "UPDATE users SET stripe_mandate_pm_id = $2, stripe_card_brand = $3, "
                "stripe_card_last4 = $4, stripe_customer_id = COALESCE($5, stripe_customer_id), "
                "updated_at = NOW() WHERE user_id = $1",
                user_id, pm_id, brand, last4, cust)
        else:
            await c.execute(
                "UPDATE users SET stripe_mandate_pm_id = $2, stripe_card_brand = $3, "
                "stripe_card_last4 = $4, stripe_customer_id = COALESCE($5, stripe_customer_id), "
                "updated_at = NOW() WHERE user_id = $1 AND stripe_mandate_pm_id IS NULL",
                user_id, pm_id, brand, last4, cust)


async def refresh_success_fee_authorisation(conn, user_id) -> bool:
    """Authorised by card = current terms accepted AND a card on file."""
    await conn.execute(
        "UPDATE users SET success_fee_authorised_at = NOW(), success_fee_authorised_via = 'card', "
        "updated_at = NOW() WHERE user_id = $1 AND success_fee_authorised_at IS NULL "
        "AND terms_agreed_at IS NOT NULL AND agreement_version = $2 "
        "AND stripe_mandate_pm_id IS NOT NULL",
        user_id, AGREEMENT_VERSION)
    val = await conn.fetchval(
        "SELECT success_fee_authorised_at IS NOT NULL FROM users WHERE user_id = $1", user_id)
    return bool(val)


# ---------------------------------------------------------------------------
# The one mark-paid
# ---------------------------------------------------------------------------
async def mark_job_paid(conn, job_id, via: str, *, session_id: Optional[str] = None,
                        payment_intent_id: Optional[str] = None,
                        paid_at: Optional[datetime] = None,
                        actor_role: str = "system", actor_id=None) -> dict:
    """Idempotent. The caller holds a transaction. Notifications are the caller's
    job, after commit: notify(job, "preparing") and, for via="stripe",
    notify(job, "paid_online"); an "alert" result also warrants an admin alert."""
    if via not in ("stripe", "invoice"):
        raise ValueError(f"invalid paid_via: {via}")
    jid = _as_uuid(job_id)
    job = await conn.fetchrow("SELECT * FROM bid_jobs WHERE id = $1 FOR UPDATE", jid)
    if not job:
        raise LookupError("job not found")
    base = {"job_id": str(jid), "user_id": job["user_id"], "promoted": False}
    if job["free"]:
        if session_id:  # money arrived for a job we made free: refund due
            await _audit(conn, jid, "paid_while_free", actor_role, actor_id,
                         {"session_id": session_id, "via": via})
            return {**base, "changed": False, "reason": "free", "alert": True,
                    "status": job["status"]}
        return {**base, "changed": False, "reason": "free", "status": job["status"]}
    if job["paid_at"] is not None:
        stored = job["stripe_checkout_session_id"]
        # Paid by card, now also marked paid by invoice (bank transfer): a
        # double payment just like a second card session -> refund due.
        cross_channel = (via == "invoice" and job.get("paid_via") == "stripe")
        if (session_id and session_id != stored) or cross_channel:
            await _audit(conn, jid, "duplicate_payment", actor_role, actor_id,
                         {"session_id": session_id, "via": via})
            return {**base, "changed": False, "reason": "duplicate", "alert": True,
                    "status": job["status"]}
        return {**base, "changed": False, "reason": "already_paid", "status": job["status"]}
    if job["status"] == "cancelled":
        await conn.execute(
            "UPDATE bid_jobs SET paid_at = COALESCE($2::timestamptz, NOW()), paid_via = $3, "
            "stripe_checkout_session_id = $4, stripe_payment_intent_id = $5, updated_at = NOW() "
            "WHERE id = $1 AND paid_at IS NULL",
            jid, paid_at, via, session_id, payment_intent_id)
        await _audit(conn, jid, "paid_while_cancelled", actor_role, actor_id,
                     {"via": via, "session_id": session_id})
        return {**base, "changed": True, "status": "cancelled", "alert": True,
                "reason": "paid_while_cancelled"}
    if job["status"] in ("requested", "payment_required"):
        updated = await conn.fetchrow(
            "UPDATE bid_jobs SET status = 'preparing', paid_at = COALESCE($2::timestamptz, NOW()), "
            "paid_via = $3, stripe_checkout_session_id = $4, stripe_payment_intent_id = $5, "
            "updated_at = NOW() WHERE id = $1 AND status IN ('requested','payment_required') "
            "AND paid_at IS NULL RETURNING id",
            jid, paid_at, via, session_id, payment_intent_id)
        if not updated:
            return {**base, "changed": False, "reason": "wrong_status", "status": job["status"]}
        await _audit(conn, jid, "paid", actor_role, actor_id,
                     {"via": via, "session_id": session_id,
                      "paid_at": paid_at.isoformat() if paid_at else None})
        promoted = await promote_user(conn, job["user_id"])
        return {**base, "changed": True, "status": "preparing", "promoted": promoted,
                "reason": None}
    if session_id:  # card money for a job past the fee gate: record it, alert the admin
        await conn.execute(
            "UPDATE bid_jobs SET paid_at = COALESCE($2::timestamptz, NOW()), paid_via = $3, "
            "stripe_checkout_session_id = $4, stripe_payment_intent_id = $5, updated_at = NOW() "
            "WHERE id = $1 AND paid_at IS NULL",
            jid, paid_at, via, session_id, payment_intent_id)
        await _audit(conn, jid, "paid_wrong_status", actor_role, actor_id,
                     {"via": via, "session_id": session_id, "status": job["status"]})
        return {**base, "changed": True, "reason": "wrong_status", "alert": True,
                "status": job["status"]}
    return {**base, "changed": False, "reason": "wrong_status", "status": job["status"]}


async def notify_paid(job_id: str, result: Mapping, via: str,
                      session_id: Optional[str] = None) -> None:
    """Post-commit emails for a mark_job_paid result (each is sent once)."""
    if result.get("changed") and result.get("status") == "preparing":
        await bid_notifications.notify(job_id, "preparing")
        if via == "stripe":
            await bid_notifications.notify(job_id, "paid_online")
    if result.get("alert"):
        reason = str(result.get("reason") or "alert")
        await bid_notifications.notify(job_id, "payment_alert",
                                       extra=f"{reason}:{session_id}" if session_id else reason)


# ---------------------------------------------------------------------------
# Session completion (return leg + webhook)
# ---------------------------------------------------------------------------
async def complete_prep_session(session, *, expected_user_id=None) -> dict:
    md = _metadata(session)
    if md.get("product") != PRODUCT_TAG or md.get("kind") != KIND_PREP:
        raise PaymentVerificationError("not_prep_session")
    if expected_user_id is not None and md.get("user_id") != str(expected_user_id):
        raise PaymentVerificationError("user_mismatch")
    try:
        job_id = _as_uuid(md.get("job_id"))
    except (ValueError, TypeError, AttributeError):
        raise PaymentVerificationError("bad_job_id")
    session_id = _sget(session, "id")
    if _sget(session, "payment_status") != "paid":
        return {"paid": False, "reason": "not_paid", "promoted": False, "job_id": str(job_id)}

    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT id, user_id, prep_fee_mkd, paid_at, stripe_checkout_session_id "
            "FROM bid_jobs WHERE id = $1", job_id)
    if not job:
        raise LookupError("job not found")
    if str(job["user_id"]) != md.get("user_id"):
        raise PaymentVerificationError("user_mismatch")

    already_this = job["paid_at"] is not None and job["stripe_checkout_session_id"] == session_id
    currency = str(_sget(session, "currency") or "").lower()
    amount = _sget(session, "amount_total")
    expected = to_minor(job["prep_fee_mkd"]) if job["prep_fee_mkd"] is not None else None
    if not already_this and (currency != STRIPE_CURRENCY or expected is None
                             or amount is None or int(amount) != expected):
        async with pool.acquire() as conn:
            await _audit(conn, job_id, "payment_amount_mismatch", "system", None,
                         {"session_id": session_id, "amount_total": amount,
                          "currency": currency, "expected": expected})
        await bid_notifications.notify(str(job_id), "payment_alert",
                                       extra=f"amount_mismatch:{session_id}")
        return {"paid": False, "reason": "amount_mismatch", "promoted": False,
                "job_id": str(job_id), "user_id": job["user_id"]}

    pi = _sget(session, "payment_intent")
    pm = _sget(pi, "payment_method") if pi is not None and not isinstance(pi, str) else None
    if pm is not None:
        await save_mandate(None, job["user_id"], pm, replace=False,
                           customer=_id_of(_sget(session, "customer")))
    async with pool.acquire() as conn:
        async with conn.transaction():
            await refresh_success_fee_authorisation(conn, job["user_id"])
            result = await mark_job_paid(conn, job_id, "stripe", session_id=session_id,
                                         payment_intent_id=_id_of(pi), actor_role="system")
    await notify_paid(str(job_id), result, "stripe", session_id)
    return {"paid": True, **result}


async def complete_setup_session(session, *, expected_user_id=None) -> dict:
    md = _metadata(session)
    if md.get("product") != PRODUCT_TAG or md.get("kind") != KIND_SETUP:
        raise PaymentVerificationError("not_setup_session")
    if expected_user_id is not None and md.get("user_id") != str(expected_user_id):
        raise PaymentVerificationError("user_mismatch")
    try:
        user_id = _as_uuid(md.get("user_id"))
    except (ValueError, TypeError, AttributeError):
        raise PaymentVerificationError("bad_user_id")
    if _sget(session, "status") != "complete":
        return {"saved": False, "reason": "not_complete", "authorised": False}
    si = _sget(session, "setup_intent")
    pm = _sget(si, "payment_method") if si is not None and not isinstance(si, str) else None
    if pm is None and isinstance(si, str):
        si_obj = await _stripe(stripe.SetupIntent.retrieve, si, expand=["payment_method"])
        pm = _sget(si_obj, "payment_method")
    if pm is None:
        return {"saved": False, "reason": "no_card", "authorised": False}
    await save_mandate(None, user_id, pm, replace=True,
                       customer=_id_of(_sget(session, "customer")))
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        authorised = await refresh_success_fee_authorisation(conn, user_id)
    return {"saved": True, "reason": None, "authorised": authorised, "user_id": user_id}


async def handle_checkout_session_completed(session_obj) -> bool:
    """Webhook entry (api/billing.py). True if the session is ours. The payload
    is not trusted: the session is re-retrieved from Stripe. Transient errors
    propagate (Stripe retries; everything here is idempotent); a session that
    fails verification is logged and acknowledged so it is not retried forever."""
    if not is_bid_service_session(session_obj):
        return False
    session_id = _sget(session_obj, "id")
    session = await retrieve_session(session_id)
    if not is_bid_service_session(session):
        logger.warning("bid-service webhook: retrieved session %s is not ours", session_id)
        return True
    kind = _metadata(session).get("kind")
    try:
        if kind == KIND_PREP:
            res = await complete_prep_session(session)
        else:
            res = await complete_setup_session(session)
        logger.info("bid-service webhook %s %s: %s", kind, session_id,
                    {k: res.get(k) for k in ("paid", "saved", "reason", "changed")})
    except (PaymentVerificationError, LookupError) as e:
        logger.error("bid-service webhook: session %s rejected: %s", session_id, e)
    return True


# ---------------------------------------------------------------------------
# Success-fee draft invoice (admin win confirm)
# ---------------------------------------------------------------------------
def _fmt_pct(pct: Any) -> str:
    d = Decimal(str(pct if pct is not None else 0)).normalize()
    s = format(d, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


async def delete_success_fee_invoice(invoice_id: str) -> bool:
    """Delete a DRAFT success-fee invoice (dismissed win). False when Stripe
    refuses (e.g. it was already finalised) or the call fails."""
    try:
        await _stripe(stripe.Invoice.delete, invoice_id)
        return True
    except Exception:
        logger.exception("could not delete draft invoice %s", invoice_id)
        return False


async def create_success_fee_invoice(*, customer: str, payment_method: str, fee_mkd: int,
                                     pct: Any, tender_title: Optional[str], win_id,
                                     job_id) -> str:
    """DRAFT invoice (auto_advance=False): never finalised or charged from code —
    the admin sends it from the Stripe Dashboard after charge_not_before.
    Invoice first, then the item attached to it (BidFinder created the item
    first; on API >= 2022-08-01 pending items are excluded, so its invoice was
    empty)."""
    md = {"product": PRODUCT_TAG, "kind": KIND_SUCCESS_FEE, "win_id": str(win_id),
          "job_id": str(job_id) if job_id else ""}
    inv = await _stripe(
        stripe.Invoice.create,
        customer=customer,
        collection_method="charge_automatically",
        auto_advance=False,
        currency=STRIPE_CURRENCY,
        default_payment_method=payment_method,
        metadata=md,
    )
    await _stripe(
        stripe.InvoiceItem.create,
        customer=customer,
        invoice=inv.id,
        amount=to_minor(fee_mkd),
        currency=STRIPE_CURRENCY,
        description=f"Надомест за успех ({_fmt_pct(pct)}%) — {tender_title or 'доделена набавка'}",
    )
    return inv.id
