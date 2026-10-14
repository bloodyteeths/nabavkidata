"""
Bid jobs, client portal and admin console — Phase 2 of the done-for-you bid
service (Oct 2026). Ported from BidFinder (tenderuk/backend/api/bid_service.py)
with the Macedonian adaptations:

- payment (Phase 2b, 14.10.2026): a client's begin puts the job at
  payment_required; the client pays the prep fee by card (Stripe Checkout,
  services/bid_payments.py — the card is saved for the success fee) or asks for
  an invoice (фактура) that an admin issues and marks paid. Every route goes
  through bid_payments.mark_job_paid, which promotes the user to managed_client.
  Free jobs (free_drafting or a zero fee) go straight to preparing;
- success fee: detected client wins (client_wins, crons/detect_client_wins.py)
  are confirmed by an admin, which emails a 7-day notice and creates a DRAFT
  Stripe invoice; publishing a bid requires the success fee to be authorised
  (card mandate + current terms, or offline/written authorisation);
- clients never upload tender documents (we scrape them); they upload only
  their own company documents to a reusable library (client_documents);
- bid preparation is human: admins upload deliverables (bid_job_files) and
  publish them. Phase 3 AI drafting plugs in at status 'preparing';
- the client reviews, approves, signs with their own certificate, submits on
  e-nabavki and clicks „Поднесено“.

Emails fire once per transition (services.bid_notifications); no polling, no
reminders, no prices in emails.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import secrets
import shutil
import unicodedata
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query,
                     UploadFile)
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from api.auth import get_current_user
from db_pool import get_asyncpg_pool
from middleware.rbac import require_admin
from services import bid_notifications, bid_payments, client_wins

router = APIRouter(prefix="/bid-service", tags=["Bid jobs"])
logger = logging.getLogger(__name__)

ADMIN_EMAIL = "atillatkulu@gmail.com"
SITE = "https://nabavkidata.com"
PUBLIC_API = os.getenv("PUBLIC_API_URL", "https://api.nabavkidata.com")

ADMIN_SENDER_NAME = "Тимот на НабавкиДата"

STATUSES = ("requested", "payment_required", "preparing", "ready", "changes_requested",
            "approved", "submitted", "won", "lost", "cancelled")
PRE_SUBMITTED = frozenset({"requested", "payment_required", "preparing", "ready",
                           "changes_requested", "approved"})
TERMINAL = frozenset({"won", "lost", "cancelled"})
REVIEWABLE = frozenset({"ready", "changes_requested", "approved"})
PUBLISHABLE = frozenset({"preparing", "ready", "changes_requested", "approved"})
NEEDS_US = frozenset({"requested", "preparing", "changes_requested"})
NEEDS_CLIENT = frozenset({"payment_required", "ready", "approved"})

FILE_KINDS = frozenset({"tehnicka", "finansiska", "izjava", "checklist", "drugo"})
DOC_CATEGORIES = ("tekovna_sostojba", "danocno_uverenie", "ddv_registracija", "kazneno_potvrda",
                  "iso_sertifikat", "drug_sertifikat", "referenca", "boni_finansiski",
                  "cv_personal", "drugo")
MAX_DOCUMENTS_PER_USER = 200
# Company-library byte quota per client (150 GB SSD is shared with Postgres).
MAX_DOCUMENT_BYTES = {"prospect": 200 * 1024 * 1024}
MAX_DOCUMENT_BYTES_DEFAULT = 500 * 1024 * 1024
MAX_CLIENT_MESSAGES_PER_HOUR = 30
# Begin/reopen limits: every begin emails the admin, so a script must not be
# able to loop it (BidFinder's 57-email incident).
MAX_BEGINS_PER_DAY = {"prospect": 5}
MAX_BEGINS_PER_DAY_DEFAULT = 20
MAX_REOPENS = 3
REOPEN_COOLDOWN_MINUTES = 10

# Version of the service terms (prep fee by card or invoice + success fee on a
# win) a client accepts before the first bid. Lives in bid_payments (no cycle).
AGREEMENT_VERSION = bid_payments.AGREEMENT_VERSION
ERR_TERMS_REQUIRED = "terms_required"

ERR_JOB_NOT_FOUND = "Понудата не е пронајдена."
ERR_WRONG_STATUS = "Оваа акција не е можна во моменталниот статус."
ERR_FILE_NOT_FOUND = "Датотеката не е пронајдена."
ERR_DOC_NOT_FOUND = "Документот не е пронајден."
ERR_DOC_LIMIT = "Достигнат е максималниот број документи."
ERR_CLIENT_NOT_FOUND = "Клиентот не е пронајден."
ERR_ADMIN_CANCELLED = ("Ова барање го откажавме ние. Пишете ни во порталот ако сакате "
                       "повторно да го разгледаме.")
ERR_TOO_MANY_REOPENS = "Барањето е повторно отворено премногу пати. Пишете ни во порталот."
ERR_REOPEN_COOLDOWN = "Барањето е штотуку откажано. Обидете се повторно за неколку минути."
ERR_TOO_MANY_BEGINS = "Денес започнавте премногу барања. Обидете се утре или пишете ни."
ERR_PAYMENT_START = "Плаќањето не може да започне. Обидете се повторно."
ERR_PAYMENT_INCOMPLETE = "Уплатата не е завршена."
ERR_SESSION_MISMATCH = "Уплатата не припаѓа на оваа понуда."
ERR_SUCCESS_FEE_NOT_AUTHORISED = "Надоместот за успех не е овластен."
ERR_NO_CARD_FOR_INVOICE = "Нема картичка: издадете фактура и означете ја како фактурирана."
ERR_PCT_MISSING = ("Процентот за надоместот за успех не е поставен. Внесете го надоместот "
                   "директно.")
ERR_ESTIMATED_VALUE = ("Вредноста е проценета (не е од понудата или договорот). Внесете ја "
                       "вистинската вредност за првата година или надоместот.")
ERR_INVOICE_ISSUED = ("За оваа понуда е издадена фактура. Платете ја по фактурата; плаќање со "
                      "картичка не е можно.")
ERR_ALREADY_PAID_CARD = ("Понудата е веќе платена со картичка. Ако пристигна и уплата по "
                         "фактурата, потребно е враќање на средствата.")
MSG_NOTICE_SENT = "Известувањето до клиентот е испратено; наплата најрано по седум дена."
MSG_NOTICE_FAILED = ("Известувањето до клиентот НЕ е испратено. Испратете го повторно; седумте "
                     "дена течат од испраќањето. Не наплаќајте пред тоа.")
MSG_NOTICE_NO_JOB = ("Нема поврзана понуда, па известувањето не може да се испрати автоматски. "
                     "Известете го клиентот писмено пред наплата.")
MSG_NOTICE_NO_FEE = "Нема надомест за наплата, па известување за наплата не е испратено."

PHASES: dict[str, tuple[str, str]] = {
    "requested": ("Го примивме барањето. Проверуваме дали тендерот ви одговара.", "us"),
    "payment_required": ("Платете го надоместот за подготовка со картичка или побарајте фактура. "
                         "Со подготовката започнуваме штом ја евидентираме уплатата.", "client"),
    "preparing": ("Ја подготвуваме вашата понуда.", "us"),
    "ready": ("Понудата е подготвена. Прегледајте ги документите и одобрете ги или побарајте "
              "измени.", "client"),
    "changes_requested": ("Ги примивме вашите забелешки и ги внесуваме измените.", "us"),
    "approved": ("Ја одобривте понудата. Потпишете ја со вашиот сертификат, поднесете ја на "
                 "е-набавки и кликнете „Поднесено“.", "client"),
    "submitted": ("Понудата е поднесена. Чекаме одлука од договорниот орган.", "none"),
    "won": ("Честитки, набавката ви е доделена.", "none"),
    "lost": ("Договорниот орган ја додели набавката на друг понудувач.", "none"),
}
_PHASE_TENDER_CANCELLED = ("Договорниот орган ја поништи постапката.", "none")
_PHASE_CANCELLED = ("Барањето е откажано.", "none")

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "requested": frozenset({"payment_required", "preparing", "cancelled"}),
    "payment_required": frozenset({"payment_required", "preparing", "cancelled"}),
    "preparing": frozenset({"ready", "cancelled"}),
    "ready": frozenset({"ready", "changes_requested", "approved", "submitted", "cancelled"}),
    "changes_requested": frozenset({"ready", "changes_requested", "approved", "submitted",
                                    "cancelled"}),
    "approved": frozenset({"ready", "changes_requested", "submitted", "cancelled"}),
    "submitted": frozenset({"won", "lost", "cancelled"}),
    "won": frozenset({"lost", "cancelled"}),
    "lost": frozenset({"won", "cancelled"}),
    "cancelled": frozenset({"requested", "payment_required", "preparing", "won", "lost"}),
}

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".jpg", ".png", ".p7s",
                      ".xml"}
MAX_FILE_BYTES = 25 * 1024 * 1024
_CHUNK = 1024 * 1024
ERR_EXTENSION = "Дозволени формати: PDF, DOC, DOCX, XLS, XLSX, ZIP, JPG, PNG, P7S, XML."
ERR_TOO_LARGE = "Датотеката е поголема од 25 MB."
# The served Content-Type comes from the allow-listed extension, never from the
# client-supplied multipart header.
MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".p7s": "application/pkcs7-signature",
    ".xml": "application/xml",
}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def is_portal_user(account_type: Optional[str], role: Optional[str]) -> bool:
    if account_type in ("prospect", "managed_client"):
        return True
    return bool(role) and str(role).lower() == "admin"


async def require_portal_user(user=Depends(get_current_user)):
    if not is_portal_user(getattr(user, "account_type", None), getattr(user, "role", None)):
        raise HTTPException(status_code=403,
                            detail="Порталот е достапен само за клиенти на услугата.")
    return user


def today_skopje() -> date:
    return datetime.now(ZoneInfo("Europe/Skopje")).date()


def phase_for(status: str, outcome: Optional[str]) -> tuple[str, str]:
    if status == "cancelled":
        return _PHASE_TENDER_CANCELLED if outcome == "cancelled" else _PHASE_CANCELLED
    return PHASES.get(status, _PHASE_CANCELLED)


def _as_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def deadline_info(closing_date: Optional[date], status: str,
                  today: date) -> tuple[Optional[int], Optional[str]]:
    cd = _as_date(closing_date)
    if cd is None:
        return None, None
    days_left = (cd - today).days
    if status not in PRE_SUBMITTED:
        return days_left, None
    if days_left < 0:
        state = "passed"
    elif days_left == 0:
        state = "today"
    elif days_left <= 3:
        state = "soon"
    else:
        state = "ok"
    return days_left, state


def tender_open_for_begin(status: Optional[str], closing_date: Optional[date],
                          today: date) -> bool:
    if status is not None and status.lower() not in ("open", "active"):
        return False
    cd = _as_date(closing_date)
    if cd is not None and cd < today:
        return False
    return True


def can_transition(frm: str, to: str) -> bool:
    return to in ALLOWED_TRANSITIONS.get(frm, frozenset())


def safe_display_name(name: Optional[str]) -> str:
    s = (name or "").replace("\\", "/").split("/")[-1]
    s = "".join(ch for ch in s if unicodedata.category(ch) not in ("Cc", "Cf"))
    s = re.sub(r"\s+", " ", s).strip()[:200].strip()
    if not s or s in (".", ".."):
        return "dokument"
    return s


def allowed_extension(filename: Optional[str]) -> Optional[str]:
    if not filename:
        return None
    ext = os.path.splitext(safe_display_name(filename))[1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else None


def files_root() -> pathlib.Path:
    env = os.getenv("BID_FILES_DIR")
    if env:
        return pathlib.Path(env)
    server = pathlib.Path("/home/ubuntu/nabavkidata")
    if server.is_dir():
        return server / "storage" / "bid_files"
    return pathlib.Path(__file__).resolve().parent.parent / "storage" / "bid_files"


def resolve_storage_path(rel: str) -> pathlib.Path:
    root = files_root().resolve()
    p = (root / rel).resolve()
    if p == root or root not in p.parents:
        raise ValueError("storage path escapes the files root")
    return p


def _ser(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _get(row: Mapping, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def job_summary(row: Mapping, today: date) -> dict:
    status = row["status"]
    outcome = _get(row, "outcome")
    phase_text, whose_move = phase_for(status, outcome)
    closing = _as_date(_get(row, "closing_date"))
    days_left, deadline_state = deadline_info(closing, status, today)
    fee = _get(row, "prep_fee_mkd")
    est = _get(row, "estimated_value_mkd")
    return {
        "id": _ser(row["id"]),
        "tender_id": row["tender_id"],
        "tender_title": _get(row, "tender_title"),
        "procuring_entity": _get(row, "procuring_entity"),
        "closing_date": _ser(closing),
        "estimated_value_mkd": float(est) if est is not None else None,
        "status": status,
        "outcome": outcome,
        "phase_text": phase_text,
        "whose_move": whose_move,
        "days_left": days_left,
        "deadline_state": deadline_state,
        "prep_fee_mkd": int(fee) if fee is not None else None,
        "free": bool(_get(row, "free", False)),
        "unread_messages": int(_get(row, "unread_messages", 0) or 0),
        "files_pending_review": int(_get(row, "files_pending_review", 0) or 0),
        "created_at": _ser(_get(row, "created_at")),
        "updated_at": _ser(_get(row, "updated_at")),
    }


def _ics_escape(s: Optional[str]) -> str:
    s = s or ""
    s = s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return s.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def _ics_fold(line: str) -> str:
    if len(line.encode("utf-8")) <= 75:
        return line
    parts: list[str] = []
    cur, cur_len, limit = "", 0, 75
    for ch in line:
        n = len(ch.encode("utf-8"))
        if cur_len + n > limit:
            parts.append(cur)
            cur, cur_len, limit = "", 0, 74  # continuation lines carry a leading space
        cur += ch
        cur_len += n
    parts.append(cur)
    return "\r\n ".join(parts)


def build_ics(events: list[dict], now: datetime) -> str:
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NabavkiData//Rokovi//MK",
             "CALSCALE:GREGORIAN", "X-WR-CALNAME:" + _ics_escape("НабавкиДата — рокови")]
    for ev in events:
        d = _as_date(ev["date"])
        if d is None:
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev['uid']}@nabavkidata.com",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
            "SUMMARY:" + _ics_escape(ev.get("summary")),
            "DESCRIPTION:" + _ics_escape(ev.get("description")),
            "URL:" + (ev.get("url") or ""),
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(l) for l in lines) + "\r\n"


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _not_found(detail: str = ERR_JOB_NOT_FOUND) -> HTTPException:
    return HTTPException(status_code=404, detail=detail)


def _wrong_status() -> HTTPException:
    return HTTPException(status_code=409, detail=ERR_WRONG_STATUS)


# ---------------------------------------------------------------------------
# Row -> dict builders
# ---------------------------------------------------------------------------
def _job_detail(row: Mapping, today: date) -> dict:
    d = job_summary(row, today)
    status = row["status"]
    pct = _get(row, "success_fee_pct")
    visible = int(_get(row, "files_visible", 0) or 0)
    d.update({
        "success_fee_pct": float(pct) if pct is not None else None,
        "invoice_number": _get(row, "invoice_number"),
        "invoice_issued_at": _ser(_get(row, "invoice_issued_at")),
        "paid_at": _ser(_get(row, "paid_at")),
        "published_at": _ser(_get(row, "published_at")),
        "approved_at": _ser(_get(row, "approved_at")),
        "submitted_at": _ser(_get(row, "submitted_at")),
        "outcome_at": _ser(_get(row, "outcome_at")),
        "cancelled_at": _ser(_get(row, "cancelled_at")),
        "cancelled_by": _get(row, "cancelled_by"),
        "cancel_reason": _get(row, "cancel_reason"),
        "client_note": _get(row, "client_note"),
        "can_cancel": status in PRE_SUBMITTED,
        # Sign-and-submit unlocks only once every deliverable is approved.
        "can_mark_submitted": status == "approved",
        # „Одобри сè“ only while nothing is under change request (it would
        # otherwise approve the old version of a file we are still fixing).
        "can_approve_all": status == "ready" and visible > 0,
    })
    return d


def _admin_extra(row: Mapping) -> dict:
    return {
        "user_id": _ser(row["user_id"]),
        "user_email": _get(row, "user_email"),
        "company_name": _get(row, "company_name"),
        "assigned_to": _ser(_get(row, "assigned_to")),
        "assigned_to_email": _get(row, "assigned_to_email"),
        "invoice_number": _get(row, "invoice_number"),
        "paid_at": _ser(_get(row, "paid_at")),
        "paid_via": _get(row, "paid_via"),
        "publish_count": int(_get(row, "publish_count", 0) or 0),
    }


def _admin_job_summary(row: Mapping, today: date) -> dict:
    d = job_summary(row, today)
    d.update(_admin_extra(row))
    return d


def _admin_job_detail(row: Mapping, today: date) -> dict:
    d = _job_detail(row, today)
    d.update(_admin_extra(row))
    d["admin_notes"] = _get(row, "admin_notes")
    d["reopen_count"] = int(_get(row, "reopen_count", 0) or 0)
    return d


def _tender_summary(row: Mapping) -> dict:
    est = _get(row, "estimated_value_mkd")
    return {
        "tender_id": row["tender_id"],
        "title": _get(row, "tender_title"),
        "procuring_entity": _get(row, "procuring_entity"),
        "closing_date": _ser(_as_date(_get(row, "closing_date"))),
        "estimated_value_mkd": float(est) if est is not None else None,
        "status": _get(row, "tender_status"),
    }


def _bid_file(row: Mapping, admin: bool = False) -> dict:
    d = {
        "id": _ser(row["id"]),
        "kind": row["kind"],
        "title": row["title"],
        "original_name": row["original_name"],
        "mime": _get(row, "mime"),
        "size_bytes": int(_get(row, "size_bytes", 0) or 0),
        "approval_status": row["approval_status"],
        "client_comment": _get(row, "client_comment"),
        "reviewed_at": _ser(_get(row, "reviewed_at")),
        "created_at": _ser(_get(row, "created_at")),
    }
    if admin:
        d["client_visible"] = bool(_get(row, "client_visible", False))
        d["updated_at"] = _ser(_get(row, "updated_at"))
    return d


def _message(row: Mapping) -> dict:
    role = row["sender_role"]
    return {
        "id": _ser(row["id"]),
        "job_id": _ser(_get(row, "job_id")),
        "sender_role": role,
        "sender_name": ADMIN_SENDER_NAME if role == "admin" else _get(row, "sender_full_name"),
        "body": row["body"],
        "created_at": _ser(_get(row, "created_at")),
        "read_by_client_at": _ser(_get(row, "read_by_client_at")),
        "read_by_admin_at": _ser(_get(row, "read_by_admin_at")),
    }


def card_window_open(row: Mapping) -> bool:
    """The client may pay by card / ask for an invoice: fee due, not paid, not free."""
    return (not bool(_get(row, "free", False)) and _get(row, "paid_at") is None
            and row["status"] in ("requested", "payment_required")
            and int(_get(row, "prep_fee_mkd", 0) or 0) > 0)


def card_payment_allowed(row: Mapping) -> bool:
    """Card only while no фактура has been issued for this job (paying both ways
    would need a refund)."""
    return card_window_open(row) and not _get(row, "invoice_number")


def _success_fee(win: Optional[Mapping]) -> Optional[dict]:
    if not win:
        return None
    fee = _get(win, "success_fee_mkd")
    fy = _get(win, "first_year_value_mkd")
    return {
        "status": win["status"],
        "fee_mkd": int(fee) if fee is not None else None,
        "first_year_value_mkd": float(fy) if fy is not None else None,
        "charge_not_before": _ser(_get(win, "charge_not_before")),
        "stripe": bool(_get(win, "stripe_invoice_id")),
    }


def _payment(row: Mapping, win: Optional[Mapping] = None) -> dict:
    pct = _get(row, "success_fee_pct")
    fee = _get(row, "prep_fee_mkd")
    free = bool(_get(row, "free", False))
    paid_at = _get(row, "paid_at")
    return {
        "required": (not free) and paid_at is None
                    and row["status"] in ("requested", "payment_required"),
        "free": free,
        "prep_fee_mkd": int(fee) if fee is not None else None,
        "success_fee_pct": float(pct) if pct is not None else None,
        "invoice_number": _get(row, "invoice_number"),
        "invoice_issued_at": _ser(_get(row, "invoice_issued_at")),
        "paid_at": _ser(paid_at),
        "invoice_file_name": _get(row, "invoice_file_name"),
        "paid_via": _get(row, "paid_via"),
        "invoice_requested_at": _ser(_get(row, "invoice_requested_at")),
        "can_pay_card": bid_payments.card_payments_enabled() and card_payment_allowed(row),
        "success_fee": _success_fee(win),
    }


_WIN_FOR_JOB_SQL = (
    "SELECT status, success_fee_mkd, first_year_value_mkd, charge_not_before, stripe_invoice_id "
    "FROM client_wins WHERE job_id = $1 AND status IN ('confirmed','invoiced') "
    "ORDER BY detected_at DESC LIMIT 1")


def _client_document(row: Mapping, today: date) -> dict:
    exp = _as_date(_get(row, "expires_on"))
    delta = (exp - today).days if exp else None
    return {
        "id": _ser(row["id"]),
        "category": row["category"],
        "title": row["title"],
        "original_name": row["original_name"],
        "mime": _get(row, "mime"),
        "size_bytes": int(_get(row, "size_bytes", 0) or 0),
        "expires_on": _ser(exp),
        "expired": delta is not None and delta < 0,
        "expires_soon": delta is not None and 0 <= delta <= 30,
        "uploaded_by_role": row["uploaded_by_role"],
        "created_at": _ser(_get(row, "created_at")),
        "updated_at": _ser(_get(row, "updated_at")),
    }


_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def _clean_reason(r: Any) -> str:
    """alert_matches reasons are written by the email crons and may carry emojis;
    the portal shows none."""
    return re.sub(r"\s+", " ", _EMOJI_RE.sub("", str(r or ""))).strip()


def _matched(row: Mapping) -> dict:
    est = _get(row, "estimated_value_mkd")
    score = _get(row, "match_score")
    reasons = [c for c in (_clean_reason(r) for r in (_get(row, "match_reasons") or [])) if c]
    return {
        "tender_id": row["tender_id"],
        "title": _get(row, "title"),
        "procuring_entity": _get(row, "procuring_entity"),
        "closing_date": _ser(_as_date(_get(row, "closing_date"))),
        "estimated_value_mkd": float(est) if est is not None else None,
        "match_score": float(score) if score is not None else 0.0,
        "match_reasons": list(reasons),
        "matched_at": _ser(_get(row, "matched_at")),
    }


def _client_info(row: Mapping) -> dict:
    pct = _get(row, "success_fee_pct")
    return {
        "user_id": _ser(row["user_id"]),
        "email": row["email"],
        "full_name": _get(row, "full_name"),
        "company_name": _get(row, "company_name"),
        "account_type": _get(row, "account_type") or "free",
        "free_drafting": bool(_get(row, "free_drafting", False)),
        "prep_fee_mkd": int(_get(row, "prep_fee_mkd", 0) or 0),
        "success_fee_pct": float(pct) if pct is not None else 0.0,
        "terms_agreed_at": _ser(_get(row, "terms_agreed_at")),
        "agreement_version": _get(row, "agreement_version"),
        "has_card": bool(_get(row, "stripe_mandate_pm_id")),
        "card_brand": _get(row, "stripe_card_brand"),
        "card_last4": _get(row, "stripe_card_last4"),
        "success_fee_authorised_at": _ser(_get(row, "success_fee_authorised_at")),
        "success_fee_authorised_via": _get(row, "success_fee_authorised_via"),
        "success_fee_authorised_ref": _get(row, "success_fee_authorised_ref"),
    }


def success_fee_missing(info: Optional[Mapping]) -> Optional[list[str]]:
    """None when publishing is allowed; else the missing pieces (subset of
    ["terms", "card"]) of an unauthorised success fee. info carries the user's
    success_fee_authorised_at, terms_agreed_at, agreement_version,
    stripe_mandate_pm_id and the job's success_fee_pct."""
    if not info:
        return None
    pct = _get(info, "success_fee_pct")
    if pct is None or Decimal(str(pct)) <= 0:
        return None
    if _get(info, "success_fee_authorised_at") is not None:
        return None
    missing: list[str] = []
    if not terms_accepted(_get(info, "terms_agreed_at"), _get(info, "agreement_version")):
        missing.append("terms")
    if not _get(info, "stripe_mandate_pm_id"):
        missing.append("card")
    return missing


def publish_blocked_text(missing: Optional[list[str]]) -> Optional[str]:
    if missing is None:
        return None
    parts = {"terms": "прифаќање на актуелните услови", "card": "зачувана картичка"}
    what = " и ".join(parts[m] for m in missing if m in parts)
    base = "Надоместот за успех не е овластен"
    if what:
        base += f": недостасува {what}"
    return base + ". Или евидентирајте писмено овластување."


_PUBLISH_GATE_SQL = (
    "SELECT u.user_id, u.success_fee_authorised_at, u.terms_agreed_at, u.agreement_version, "
    "u.stripe_mandate_pm_id, j.success_fee_pct FROM bid_jobs j "
    "JOIN users u ON u.user_id = j.user_id WHERE j.id = $1")


def _event(row: Mapping) -> dict:
    detail = _get(row, "detail")
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except ValueError:
            detail = None
    return {
        "event": row["event"],
        "kind": row["kind"],
        "actor_role": _get(row, "actor_role"),
        "created_at": _ser(_get(row, "created_at")),
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
_TENDER_COLS = ("t.title AS tender_title, t.procuring_entity, t.closing_date, "
                "t.estimated_value_mkd, t.status AS tender_status")
_FILE_COUNTS = (
    "(SELECT COUNT(*) FROM bid_job_files f WHERE f.job_id = j.id AND f.client_visible "
    " AND f.approval_status = 'pending') AS files_pending_review, "
    "(SELECT COUNT(*) FROM bid_job_files f WHERE f.job_id = j.id AND f.client_visible) "
    " AS files_visible"
)
CLIENT_JOB_SQL = f"""
    SELECT j.*, {_TENDER_COLS},
           (SELECT COUNT(*) FROM bid_messages m WHERE m.job_id = j.id
             AND m.sender_role = 'admin' AND m.read_by_client_at IS NULL) AS unread_messages,
           {_FILE_COUNTS}
    FROM bid_jobs j
    LEFT JOIN tenders t ON t.tender_id = j.tender_id
"""
ADMIN_JOB_SQL = f"""
    SELECT j.*, {_TENDER_COLS},
           (SELECT COUNT(*) FROM bid_messages m WHERE m.job_id = j.id
             AND m.sender_role = 'client' AND m.read_by_admin_at IS NULL) AS unread_messages,
           {_FILE_COUNTS},
           u.email AS user_email, u.company_name, a.email AS assigned_to_email
    FROM bid_jobs j
    JOIN users u ON u.user_id = j.user_id
    LEFT JOIN users a ON a.user_id = j.assigned_to
    LEFT JOIN tenders t ON t.tender_id = j.tender_id
"""
MESSAGE_SQL = """
    SELECT m.*, su.full_name AS sender_full_name
    FROM bid_messages m
    LEFT JOIN users su ON su.user_id = m.sender_user_id
"""


async def _client_job_row(conn, job_id: uuid.UUID, user_id) -> Mapping:
    row = await conn.fetchrow(CLIENT_JOB_SQL + " WHERE j.id = $1 AND j.user_id = $2",
                              job_id, user_id)
    if not row:
        raise _not_found()
    return row


async def _admin_job_row(conn, job_id: uuid.UUID) -> Mapping:
    row = await conn.fetchrow(ADMIN_JOB_SQL + " WHERE j.id = $1", job_id)
    if not row:
        raise _not_found()
    return row


async def _audit(conn, job_id, event: str, actor_role: str, actor_id=None,
                 detail: Optional[dict] = None) -> None:
    await conn.execute(
        "INSERT INTO bid_job_events (job_id, kind, event, actor_role, actor_user_id, detail) "
        "VALUES ($1,'audit',$2,$3,$4,$5::jsonb)",
        job_id, event, actor_role, actor_id, json.dumps(detail) if detail is not None else None,
    )


async def _transition(conn, job_id: uuid.UUID, from_statuses, to: str, *,
                      actor_role: str, actor_id=None, set_sql: str = "", args: tuple = (),
                      extra_where: str = "", event: Optional[str] = None,
                      detail: Optional[dict] = None, owner_id=None) -> Mapping:
    """Single guarded UPDATE. set_sql/extra_where use placeholders from $4 on (args)."""
    froms = [f for f in from_statuses if can_transition(f, to)]
    params: list[Any] = [job_id, froms, to, *args]
    owner_clause = ""
    if owner_id is not None:
        params.append(owner_id)
        owner_clause = f" AND user_id = ${len(params)}"
    sql = (f"UPDATE bid_jobs SET status = $3, updated_at = NOW()"
           f"{(', ' + set_sql) if set_sql else ''} "
           f"WHERE id = $1 AND status = ANY($2::text[]){owner_clause}"
           f"{(' AND ' + extra_where) if extra_where else ''} RETURNING *")
    row = await conn.fetchrow(sql, *params)
    if not row:
        exists = await conn.fetchval(
            "SELECT 1 FROM bid_jobs WHERE id = $1" + (" AND user_id = $2" if owner_id else ""),
            *([job_id, owner_id] if owner_id else [job_id]),
        )
        if not exists:
            raise _not_found()
        raise _wrong_status()
    await _audit(conn, job_id, event or to, actor_role, actor_id, detail)
    return row


# Moved to services.bid_payments (shared with the Stripe return leg / webhook).
_promote_user = bid_payments.promote_user


async def _fetch_messages(conn, user_id, job_id: Optional[uuid.UUID]) -> list[dict]:
    if job_id is None:
        rows = await conn.fetch(
            MESSAGE_SQL + " WHERE m.user_id = $1 AND m.job_id IS NULL ORDER BY m.created_at ASC",
            user_id)
    else:
        rows = await conn.fetch(
            MESSAGE_SQL + " WHERE m.user_id = $1 AND m.job_id = $2 ORDER BY m.created_at ASC",
            user_id, job_id)
    return [_message(r) for r in rows]


async def _mark_read(conn, user_id, job_id: Optional[uuid.UUID], reader: str) -> None:
    if reader == "client":
        col, sender = "read_by_client_at", "admin"
    else:
        col, sender = "read_by_admin_at", "client"
    thread = "m.job_id IS NULL" if job_id is None else "m.job_id = $2"
    args = [user_id] if job_id is None else [user_id, job_id]
    await conn.execute(
        f"UPDATE bid_messages m SET {col} = NOW() WHERE m.user_id = $1 AND {thread} "
        f"AND m.sender_role = '{sender}' AND m.{col} IS NULL",
        *args,
    )


async def _insert_message(conn, user_id, job_id: Optional[uuid.UUID], sender_role: str,
                          sender_id, body: str) -> dict:
    row = await conn.fetchrow(
        "INSERT INTO bid_messages (user_id, job_id, sender_role, sender_user_id, body) "
        "VALUES ($1,$2,$3,$4,$5) RETURNING id",
        user_id, job_id, sender_role, sender_id, body,
    )
    full = await conn.fetchrow(MESSAGE_SQL + " WHERE m.id = $1", row["id"])
    return _message(full)


def _clean_body(body: str) -> str:
    b = (body or "").strip()
    if not b:
        raise HTTPException(status_code=400, detail="Пораката е празна.")
    if len(b) > 5000:
        raise HTTPException(status_code=400, detail="Пораката е предолга.")
    return b


async def _check_client_message_rate(conn, user_id) -> None:
    n = await conn.fetchval(
        "SELECT COUNT(*) FROM bid_messages WHERE user_id = $1 AND sender_role = 'client' "
        "AND created_at > NOW() - INTERVAL '1 hour'",
        user_id,
    )
    if (n or 0) >= MAX_CLIENT_MESSAGES_PER_HOUR:
        raise HTTPException(status_code=429, detail="Премногу пораки. Обидете се подоцна.")


LEAD_REASON = "Побаравте понуда за овој тендер"
KEYWORD_REASON_PREFIX = "Клучен збор: "

# Candidates for "Тендери за мене", one row per tender (best score wins):
#  1. alert_matches written by the alert crons;
#  2. the tender the client asked about on the /usluga or tender-card form
#     (bid_service_leads.tender_id) — so a brand-new client never lands on an
#     empty list;
#  3. a live title match of the client's keyword alerts against currently open
#     tenders, so a new or edited alert shows results immediately (the crons
#     only match tenders created after their last run).
_MATCHED_SQL = """
    WITH kw AS (
        SELECT DISTINCT LOWER(BTRIM(k)) AS k
        FROM tender_alerts ta
        CROSS JOIN LATERAL jsonb_array_elements_text(
            CASE WHEN jsonb_typeof(ta.criteria->'keywords') = 'array'
                 THEN ta.criteria->'keywords' ELSE '[]'::jsonb END) AS k
        WHERE ta.user_id = $1 AND COALESCE(ta.is_active, TRUE)
          AND char_length(BTRIM(k)) >= 3
        LIMIT 30
    ),
    cand AS (
        SELECT am.tender_id, am.match_score::float8 AS match_score,
               am.match_reasons::text[] AS match_reasons, am.created_at AS matched_at
        FROM alert_matches am
        JOIN tender_alerts ta ON ta.alert_id = am.alert_id AND ta.user_id = $1
        UNION ALL
        SELECT l.tender_id, 100.0::float8, ARRAY['""" + LEAD_REASON + """']::text[],
               l.created_at::timestamptz
        FROM bid_service_leads l
        WHERE l.user_id = $1 AND l.tender_id IS NOT NULL
        UNION ALL
        SELECT t.tender_id, 40.0::float8, ARRAY['""" + KEYWORD_REASON_PREFIX + """' || kw.k]::text[],
               NOW()
        FROM kw
        JOIN tenders t ON t.closing_date >= $2
         AND t.title ILIKE '%' || replace(replace(replace(kw.k, '\\', '\\\\'), '%', '\\%'), '_', '\\_') || '%'
    )
    SELECT * FROM (
        SELECT DISTINCT ON (t.tender_id)
               t.tender_id, t.title, t.procuring_entity, t.closing_date, t.estimated_value_mkd,
               c.match_score, c.match_reasons, c.matched_at
        FROM cand c
        JOIN tenders t ON t.tender_id = c.tender_id
        WHERE (t.closing_date IS NULL OR t.closing_date >= $2)
          AND (t.status IS NULL OR LOWER(t.status) IN ('open','active'))
          AND NOT EXISTS (SELECT 1 FROM bid_jobs j WHERE j.user_id = $1 AND j.tender_id = t.tender_id)
        ORDER BY t.tender_id, c.match_score DESC
    ) x
    ORDER BY x.closing_date ASC NULLS LAST
    LIMIT $3
"""


async def _matched_tenders(conn, user_id, today: date, limit: int) -> list[dict]:
    rows = await conn.fetch(_MATCHED_SQL, user_id, today, limit)
    return [_matched(r) for r in rows]


# ---------------------------------------------------------------------------
# File storage
# ---------------------------------------------------------------------------
async def _save_upload(upload: UploadFile, subdir: str) -> tuple[str, int, str, str, Optional[str]]:
    """Stream the upload to disk. Returns (rel_path, size, ext, original_name, mime)."""
    original = safe_display_name(upload.filename)
    ext = allowed_extension(original)
    if not ext:
        raise HTTPException(status_code=400, detail=ERR_EXTENSION)
    rel = f"{subdir}/{uuid.uuid4().hex}{ext}"
    path = resolve_storage_path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with open(path, "wb") as fh:
            while True:
                chunk = await upload.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    raise HTTPException(status_code=413, detail=ERR_TOO_LARGE)
                fh.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    mime = mime_for(ext)
    return rel, size, ext, original, mime


def _remove_file(rel: Optional[str]) -> None:
    if not rel:
        return
    try:
        resolve_storage_path(rel).unlink(missing_ok=True)
    except (ValueError, OSError):
        pass


def mime_for(ext_or_name: Optional[str]) -> str:
    """Content-Type from the allow-listed extension (never from the client)."""
    ext = os.path.splitext(ext_or_name or "")[1].lower() or (ext_or_name or "").lower()
    return MIME_BY_EXTENSION.get(ext, "application/octet-stream")


def _file_response(rel: str, mime: Optional[str], original_name: str) -> FileResponse:
    try:
        path = resolve_storage_path(rel)
    except ValueError:
        raise _not_found(ERR_FILE_NOT_FOUND)
    if not path.is_file():
        raise _not_found(ERR_FILE_NOT_FOUND)
    # The stored name ends in the allow-listed extension; derive the type from it
    # so a forged multipart Content-Type is never echoed back.
    return FileResponse(path, media_type=mime_for(rel), filename=original_name)


def remove_user_company_files(user_id) -> None:
    """Erase a client's company-library directory (used when the user is deleted)."""
    try:
        target = resolve_storage_path(f"company/{uuid.UUID(str(user_id))}")
    except (ValueError, OSError):
        return
    shutil.rmtree(target, ignore_errors=True)


def _title_from(original: str, title: Optional[str]) -> str:
    t = (title or "").strip()
    if not t:
        t = os.path.splitext(original)[0].strip() or original
    return t[:300]


def _parse_date(value: Optional[str]) -> Optional[date]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Невалиден датум.")


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class BeginBody(BaseModel):
    tender_id: str = Field(..., min_length=1, max_length=100)
    client_note: Optional[str] = Field(None, max_length=2000)
    # True when the client ticked „ги прифаќам условите“ in the confirm dialog.
    accept_terms: bool = False


class AdminCreateJobBody(BaseModel):
    user_id: uuid.UUID
    tender_id: str = Field(..., min_length=1, max_length=100)
    client_note: Optional[str] = Field(None, max_length=2000)


class AgreementBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=20)


class KeywordsBody(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=20)


class CommentBody(BaseModel):
    comment: str = Field(..., min_length=1, max_length=2000)


class CancelBody(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)


class MessageBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


class DocumentPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    category: Optional[str] = None
    expires_on: Optional[date] = None


class AdminJobPatch(BaseModel):
    admin_notes: Optional[str] = Field(None, max_length=10000)
    prep_fee_mkd: Optional[int] = Field(None, ge=0, le=10_000_000)


class InvoiceBody(BaseModel):
    prep_fee_mkd: int = Field(..., ge=1, le=10_000_000)
    invoice_number: str = Field(..., min_length=1, max_length=50)


class MarkPaidBody(BaseModel):
    paid_at: Optional[date] = None


class OutcomeBody(BaseModel):
    outcome: str = Field(..., pattern="^(won|lost|cancelled)$")


class AssignBody(BaseModel):
    assigned_to: Optional[uuid.UUID] = None


class SessionBody(BaseModel):
    session_id: str = Field(..., min_length=10, max_length=255)


class AuthoriseBody(BaseModel):
    reference: str = Field(..., min_length=3, max_length=120)


class ConfirmWinBody(BaseModel):
    first_year_value_mkd: Optional[float] = Field(None, ge=0, le=1e13)
    success_fee_mkd: Optional[int] = Field(None, ge=0, le=2_000_000_000)
    notes: Optional[str] = Field(None, max_length=5000)
    create_stripe_invoice: bool = True


class DismissWinBody(BaseModel):
    notes: Optional[str] = Field(None, max_length=5000)


class MarkInvoicedBody(BaseModel):
    invoice_number: Optional[str] = Field(None, max_length=50)


class ClientPatch(BaseModel):
    free_drafting: Optional[bool] = None
    prep_fee_mkd: Optional[int] = Field(None, ge=0, le=10_000_000)
    success_fee_pct: Optional[float] = Field(None, ge=0, le=100)
    company_name: Optional[str] = Field(None, max_length=500)


# ===========================================================================
# Client endpoints
# ===========================================================================
def terms_accepted(terms_agreed_at: Any, agreement_version: Optional[str]) -> bool:
    return terms_agreed_at is not None and agreement_version == AGREEMENT_VERSION


async def _open_tender_or_raise(conn, tender_id: str) -> Mapping:
    tender = await conn.fetchrow(
        "SELECT tender_id, status, closing_date FROM tenders WHERE tender_id = $1", tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Тендерот не е пронајден.")
    return tender


async def _existing_job(conn, uid, tender_id: str) -> Optional[Mapping]:
    return await conn.fetchrow(
        "SELECT id, status, outcome, cancelled_by, reopen_count, "
        "(cancelled_at IS NOT NULL AND cancelled_at > NOW() - make_interval(mins => $3)) "
        "AS recently_cancelled FROM bid_jobs WHERE user_id = $1 AND tender_id = $2",
        uid, tender_id, REOPEN_COOLDOWN_MINUTES)


def _is_live(existing: Optional[Mapping]) -> bool:
    """An active job, or one whose tender procedure was cancelled (outcome set):
    returned as-is. Only a request-cancelled job (outcome NULL) can be reopened."""
    return bool(existing) and (existing["status"] != "cancelled"
                               or existing["outcome"] is not None)


async def _create_or_reopen(conn, uid, tender_id: str, note: Optional[str],
                            existing: Optional[Mapping], *, actor_role: str, actor_id,
                            free_drafting: bool, prefs: Optional[Mapping]):
    """Insert a new job or reopen a cancelled one (caller holds a transaction).
    Returns the job id, or None when a concurrent begin won the race."""
    # A client's begin waits at the fee gate (card or invoice); an admin-opened
    # job starts at 'requested' (we confirm the fit and fee first).
    unpaid_status = "payment_required" if actor_role == "client" else "requested"
    if existing:
        job = await conn.fetchrow(
            "SELECT paid_at, free FROM bid_jobs WHERE id = $1 FOR UPDATE", existing["id"])
        to = "preparing" if (job["paid_at"] or job["free"] or free_drafting) else unpaid_status
        make_free = bool(job["free"] or (free_drafting and job["paid_at"] is None))
        # A client may reopen only what the client cancelled; admins reopen anything.
        guard = "outcome IS NULL" + (" AND cancelled_by = 'client'" if actor_role == "client" else "")
        await _transition(
            conn, existing["id"], ["cancelled"], to,
            actor_role=actor_role, actor_id=actor_id,
            owner_id=uid if actor_role == "client" else None,
            set_sql=("reopen_count = reopen_count + 1, cancelled_at = NULL, "
                     "cancelled_by = NULL, cancel_reason = NULL, approved_at = NULL, "
                     "free = $4, client_note = COALESCE($5, client_note), "
                     "paid_via = COALESCE(paid_via, $6)"),
            args=(make_free, note, "free" if make_free else None), extra_where=guard,
            detail={"action": "reopen"},
        )
        return existing["id"]
    status = "preparing" if free_drafting else unpaid_status
    job_id = await conn.fetchval(
        """
        INSERT INTO bid_jobs (user_id, tender_id, status, prep_fee_mkd,
                              success_fee_pct, free, client_note, paid_via)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (user_id, tender_id) DO NOTHING
        RETURNING id
        """,
        uid, tender_id, status,
        prefs["prep_fee_mkd"] if prefs else None,
        prefs["success_fee_pct"] if prefs else None,
        free_drafting, note, "free" if free_drafting else None,
    )
    if job_id is not None:
        await _audit(conn, job_id, status, actor_role, actor_id, {"action": "begin"})
    return job_id


async def _check_begin_limits(conn, user, existing: Optional[Mapping]) -> None:
    if existing:  # a reopen
        if existing["cancelled_by"] == "admin":
            raise HTTPException(status_code=409, detail=ERR_ADMIN_CANCELLED)
        if int(existing["reopen_count"] or 0) >= MAX_REOPENS:
            raise HTTPException(status_code=409, detail=ERR_TOO_MANY_REOPENS)
        if existing["recently_cancelled"]:
            raise HTTPException(status_code=429, detail=ERR_REOPEN_COOLDOWN)
    account_type = getattr(user, "account_type", None)
    limit = MAX_BEGINS_PER_DAY.get(account_type or "", MAX_BEGINS_PER_DAY_DEFAULT)
    recent = await conn.fetchval(
        "SELECT COUNT(*) FROM bid_job_events e JOIN bid_jobs j ON j.id = e.job_id "
        "WHERE j.user_id = $1 AND e.kind = 'audit' AND e.actor_role = 'client' "
        "AND e.detail->>'action' IN ('begin','reopen') "
        "AND e.created_at > NOW() - INTERVAL '1 day'",
        user.user_id)
    if (recent or 0) >= limit:
        raise HTTPException(status_code=429, detail=ERR_TOO_MANY_BEGINS)


@router.post("/jobs")
async def begin_job(body: BeginBody, background: BackgroundTasks,
                    user=Depends(require_portal_user)):
    tender_id = body.tender_id.strip()
    if not tender_id:
        raise HTTPException(status_code=400, detail="Невалиден тендер.")
    note = (body.client_note or "").strip() or None
    today = today_skopje()
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        tender = await _open_tender_or_raise(conn, tender_id)
        existing = await _existing_job(conn, uid, tender_id)
        if _is_live(existing):
            row = await _client_job_row(conn, existing["id"], uid)
            return _begin_response(row, today, created=False)
        if not tender_open_for_begin(tender["status"], tender["closing_date"], today):
            raise HTTPException(status_code=409, detail="Рокот за поднесување на овој тендер истече.")
        prefs = await conn.fetchrow(
            "SELECT prep_fee_mkd, success_fee_pct, free_drafting, terms_agreed_at, "
            "agreement_version FROM users WHERE user_id = $1", uid)
        await _check_begin_limits(conn, user, existing)
        accepted = bool(prefs) and terms_accepted(prefs["terms_agreed_at"],
                                                  prefs["agreement_version"])
        if not accepted and not body.accept_terms:
            # The frontend catches this code and shows the terms confirmation.
            raise HTTPException(status_code=409, detail=ERR_TERMS_REQUIRED)
        fee = prefs["prep_fee_mkd"] if prefs else None
        # Free drafting, or a client whose agreed fee is zero: no fee gate.
        free_job = bool(prefs and prefs["free_drafting"]) or (fee is not None and int(fee) <= 0)

        async with conn.transaction():
            if not accepted:
                await conn.execute(
                    "UPDATE users SET terms_agreed_at = NOW(), agreement_version = $2, "
                    "updated_at = NOW() WHERE user_id = $1", uid, AGREEMENT_VERSION)
                await bid_payments.refresh_success_fee_authorisation(conn, uid)
            job_id = await _create_or_reopen(conn, uid, tender_id, note, existing,
                                             actor_role="client", actor_id=uid,
                                             free_drafting=free_job, prefs=prefs)
            if job_id is None:  # concurrent begin won the race
                other = await conn.fetchval(
                    "SELECT id FROM bid_jobs WHERE user_id = $1 AND tender_id = $2",
                    uid, tender_id)
                row = await _client_job_row(conn, other, uid)
                return _begin_response(row, today, created=False)
            if free_job:
                await _promote_user(conn, uid)
        row = await _client_job_row(conn, job_id, uid)
    background.add_task(bid_notifications.notify, str(job_id), "job_requested")
    return _begin_response(row, today, created=True)


def _begin_response(row: Mapping, today: date, *, created: bool) -> dict:
    return {"job": job_summary(row, today), "created": created,
            "payment_required": row["status"] == "payment_required"}


@router.get("/agreement")
async def get_agreement(user=Depends(require_portal_user)):
    """The client's own fees and whether the current service terms are accepted."""
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT prep_fee_mkd, success_fee_pct, free_drafting, terms_agreed_at, "
            "agreement_version FROM users WHERE user_id = $1", user.user_id)
    row = row or {}
    pct = _get(row, "success_fee_pct")
    fee = _get(row, "prep_fee_mkd")
    return {
        "prep_fee_mkd": int(fee) if fee is not None else None,
        "success_fee_pct": float(pct) if pct is not None else None,
        "free_drafting": bool(_get(row, "free_drafting", False)),
        "terms_agreed_at": _ser(_get(row, "terms_agreed_at")),
        "agreement_version": _get(row, "agreement_version"),
        "current_version": AGREEMENT_VERSION,
        "accepted": terms_accepted(_get(row, "terms_agreed_at"), _get(row, "agreement_version")),
    }


@router.post("/agreement/accept")
async def accept_agreement(body: AgreementBody, user=Depends(require_portal_user)):
    if body.version != AGREEMENT_VERSION:
        raise HTTPException(status_code=409,
                            detail="Условите се променија. Освежете ја страницата.")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET terms_agreed_at = NOW(), agreement_version = $2, "
            "updated_at = NOW() WHERE user_id = $1", user.user_id, AGREEMENT_VERSION)
        authorised = await bid_payments.refresh_success_fee_authorisation(conn, user.user_id)
    return {**(await get_agreement(user)), "success_fee_authorised": authorised}


# --- Card payment (Stripe Checkout) and invoice choice --------------------
async def _owned_job(conn, job_id: uuid.UUID, uid) -> Mapping:
    return await _client_job_row(conn, job_id, uid)


async def _payment_response(conn, job_id: uuid.UUID, uid, **extra) -> dict:
    row = await _client_job_row(conn, job_id, uid)
    win = await conn.fetchrow(_WIN_FOR_JOB_SQL, job_id)
    return {**extra, "job": _job_detail(row, today_skopje()), "payment": _payment(row, win)}


@router.post("/jobs/{job_id}/pay-prep")
async def pay_prep_fee(job_id: uuid.UUID, user=Depends(require_portal_user)):
    """Stripe hosted Checkout for the prep fee. The amount comes from the job."""
    if not bid_payments.card_payments_enabled():
        raise HTTPException(status_code=503, detail=bid_payments.ERR_CARD_UNAVAILABLE)
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await _owned_job(conn, job_id, uid)
        if not card_window_open(row):
            raise _wrong_status()
        if _get(row, "invoice_number"):
            raise HTTPException(status_code=409, detail=ERR_INVOICE_ISSUED)
        prefs = await conn.fetchrow(
            "SELECT terms_agreed_at, agreement_version FROM users WHERE user_id = $1", uid)
        if not prefs or not terms_accepted(prefs["terms_agreed_at"], prefs["agreement_version"]):
            raise HTTPException(status_code=409, detail=ERR_TERMS_REQUIRED)
    try:
        # conn=None: no DB connection is held while Stripe answers.
        url = await bid_payments.create_prep_checkout(None, row, uid)
    except Exception:
        logger.exception("prep-fee checkout failed: job=%s", job_id)
        raise HTTPException(status_code=502, detail=ERR_PAYMENT_START)
    return {"url": url}


@router.post("/jobs/{job_id}/prep-complete")
async def prep_complete(job_id: uuid.UUID, body: SessionBody, user=Depends(require_portal_user)):
    """Return leg of the prep-fee Checkout. The session is verified server-side;
    the webhook does the same, and mark_job_paid makes both idempotent."""
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _owned_job(conn, job_id, uid)
    try:
        session = await bid_payments.retrieve_session(body.session_id)
    except Exception:
        raise HTTPException(status_code=400, detail=ERR_SESSION_MISMATCH)
    md = bid_payments._metadata(session)
    if md.get("job_id") != str(job_id):
        raise HTTPException(status_code=400, detail=ERR_SESSION_MISMATCH)
    try:
        res = await bid_payments.complete_prep_session(session, expected_user_id=uid)
    except (bid_payments.PaymentVerificationError, LookupError):
        raise HTTPException(status_code=400, detail=ERR_SESSION_MISMATCH)
    if res.get("reason") == "not_paid":
        raise HTTPException(status_code=402, detail=ERR_PAYMENT_INCOMPLETE)
    async with pool.acquire() as conn:
        out = await _payment_response(conn, job_id, uid)
    return {"paid": bool(res.get("paid")), "reason": res.get("reason"),
            "account_promoted": bool(res.get("promoted")), **out}


@router.post("/jobs/{job_id}/choose-invoice")
async def choose_invoice(job_id: uuid.UUID, background: BackgroundTasks,
                         user=Depends(require_portal_user)):
    """„Платам со фактура“: we issue an invoice and mark the job paid by hand."""
    uid = user.user_id
    first = False
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            job = await conn.fetchrow(
                "SELECT id, status, free, paid_at, prep_fee_mkd, invoice_requested_at "
                "FROM bid_jobs WHERE id = $1 AND user_id = $2 FOR UPDATE", job_id, uid)
            if not job:
                raise _not_found()
            if job["invoice_requested_at"] is None:
                if not card_window_open(job):
                    raise _wrong_status()
                await conn.execute(
                    "UPDATE bid_jobs SET invoice_requested_at = COALESCE(invoice_requested_at, NOW()), "
                    "updated_at = NOW() WHERE id = $1", job_id)
                await _audit(conn, job_id, "invoice_requested", "client", uid)
                first = True
        out = await _payment_response(conn, job_id, uid)
    if first:
        background.add_task(bid_notifications.notify, str(job_id), "invoice_requested")
    return out


_BILLING_SQL = (
    "SELECT stripe_mandate_pm_id, stripe_card_brand, stripe_card_last4, terms_agreed_at, "
    "agreement_version, success_fee_pct, success_fee_authorised_at, success_fee_authorised_via "
    "FROM users WHERE user_id = $1")


def _billing_status(row: Optional[Mapping]) -> dict:
    row = row or {}
    pct = _get(row, "success_fee_pct")
    return {
        "has_card": bool(_get(row, "stripe_mandate_pm_id")),
        "card_brand": _get(row, "stripe_card_brand"),
        "card_last4": _get(row, "stripe_card_last4"),
        "terms_accepted": terms_accepted(_get(row, "terms_agreed_at"),
                                         _get(row, "agreement_version")),
        "current_version": AGREEMENT_VERSION,
        "success_fee_pct": float(pct) if pct is not None else None,
        "success_fee_authorised": _get(row, "success_fee_authorised_at") is not None,
        "success_fee_authorised_at": _ser(_get(row, "success_fee_authorised_at")),
        "success_fee_authorised_via": _get(row, "success_fee_authorised_via"),
        "card_payments_enabled": bid_payments.card_payments_enabled(),
    }


@router.get("/billing/status")
async def billing_status(user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_BILLING_SQL, user.user_id)
    return _billing_status(row)


@router.post("/billing/setup-checkout")
async def billing_setup_checkout(user=Depends(require_portal_user)):
    """Stripe hosted 'setup' Checkout: save (or replace) the card for the success fee."""
    if not bid_payments.card_payments_enabled():
        raise HTTPException(status_code=503, detail=bid_payments.ERR_CARD_UNAVAILABLE)
    try:
        url = await bid_payments.create_setup_checkout(None, user.user_id)
    except Exception:
        logger.exception("setup checkout failed: user=%s", user.user_id)
        raise HTTPException(status_code=502, detail=ERR_PAYMENT_START)
    return {"url": url}


@router.post("/billing/setup-complete")
async def billing_setup_complete(body: SessionBody, user=Depends(require_portal_user)):
    try:
        session = await bid_payments.retrieve_session(body.session_id)
    except Exception:
        raise HTTPException(status_code=400, detail=ERR_SESSION_MISMATCH)
    try:
        res = await bid_payments.complete_setup_session(session, expected_user_id=user.user_id)
    except (bid_payments.PaymentVerificationError, LookupError):
        raise HTTPException(status_code=400, detail=ERR_SESSION_MISMATCH)
    if not res.get("saved"):
        raise HTTPException(status_code=402, detail="Картичката не е зачувана.")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_BILLING_SQL, user.user_id)
    return _billing_status(row)


@router.get("/jobs")
async def list_my_jobs(user=Depends(require_portal_user)):
    today = today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(CLIENT_JOB_SQL + " WHERE j.user_id = $1", user.user_id)
    jobs = [job_summary(r, today) for r in rows]
    yours = [j for j in jobs if j["whose_move"] == "client"]
    pre = [j for j in jobs if j["whose_move"] != "client" and j["status"] in PRE_SUBMITTED]
    rest = [j for j in jobs if j["whose_move"] != "client" and j["status"] not in PRE_SUBMITTED]
    by_deadline = lambda j: (j["closing_date"] is None, j["closing_date"] or "")  # noqa: E731
    yours.sort(key=by_deadline)
    pre.sort(key=by_deadline)
    rest.sort(key=lambda j: j["updated_at"] or "", reverse=True)
    return {"jobs": yours + pre + rest}


@router.get("/jobs/by-tender")
async def job_for_tender(tender_id: str = Query(..., min_length=1, max_length=100),
                         user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(CLIENT_JOB_SQL + " WHERE j.user_id = $1 AND j.tender_id = $2",
                                  user.user_id, tender_id.strip())
    return {"job": job_summary(row, today_skopje()) if row else None}


@router.get("/jobs/{job_id}")
async def get_my_job(job_id: uuid.UUID, user=Depends(require_portal_user)):
    today = today_skopje()
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _client_job_row(conn, job_id, uid)  # 404 before marking anything read
        await _mark_read(conn, uid, job_id, "client")
        row = await _client_job_row(conn, job_id, uid)
        files = await conn.fetch(
            "SELECT * FROM bid_job_files WHERE job_id = $1 AND client_visible ORDER BY created_at",
            job_id)
        messages = await _fetch_messages(conn, uid, job_id)
        win = await conn.fetchrow(_WIN_FOR_JOB_SQL, job_id)
    return {
        "job": _job_detail(row, today),
        "tender": _tender_summary(row),
        "files": [_bid_file(f) for f in files],
        "messages": messages,
        "payment": _payment(row, win),
    }


@router.get("/jobs/{job_id}/files/{file_id}/download")
async def download_my_job_file(job_id: uuid.UUID, file_id: uuid.UUID,
                               user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        f = await conn.fetchrow(
            "SELECT f.storage_path, f.mime, f.original_name FROM bid_job_files f "
            "JOIN bid_jobs j ON j.id = f.job_id "
            "WHERE f.id = $1 AND f.job_id = $2 AND j.user_id = $3 AND f.client_visible",
            file_id, job_id, user.user_id)
    if not f:
        raise _not_found(ERR_FILE_NOT_FOUND)
    return _file_response(f["storage_path"], f["mime"], f["original_name"])


@router.get("/jobs/{job_id}/invoice")
async def download_my_invoice(job_id: uuid.UUID, user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT invoice_file_path, invoice_file_name FROM bid_jobs "
            "WHERE id = $1 AND user_id = $2", job_id, user.user_id)
    if not row:
        raise _not_found()
    if not row["invoice_file_path"]:
        raise _not_found(ERR_FILE_NOT_FOUND)
    return _file_response(row["invoice_file_path"], None, row["invoice_file_name"] or "faktura.pdf")


async def _visible_file_for_review(conn, job_id: uuid.UUID, file_id: uuid.UUID, uid) -> Mapping:
    job = await conn.fetchrow(
        "SELECT id, status FROM bid_jobs WHERE id = $1 AND user_id = $2 FOR UPDATE", job_id, uid)
    if not job:
        raise _not_found()
    f = await conn.fetchrow(
        "SELECT id FROM bid_job_files WHERE id = $1 AND job_id = $2 AND client_visible",
        file_id, job_id)
    if not f:
        raise _not_found(ERR_FILE_NOT_FOUND)
    if job["status"] not in REVIEWABLE:
        raise _wrong_status()
    return job


@router.post("/jobs/{job_id}/files/{file_id}/approve")
async def approve_file(job_id: uuid.UUID, file_id: uuid.UUID, background: BackgroundTasks,
                       user=Depends(require_portal_user)):
    uid = user.user_id
    transitioned = False
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            job = await _visible_file_for_review(conn, job_id, file_id, uid)
            frow = await conn.fetchrow(
                "UPDATE bid_job_files SET approval_status = 'approved', reviewed_at = NOW(), "
                "updated_at = NOW() WHERE id = $1 RETURNING *", file_id)
            await _audit(conn, job_id, "file_approved", "client", uid, {"file_id": str(file_id)})
            if job["status"] in ("ready", "changes_requested"):
                remaining = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM bid_job_files WHERE job_id = $1 "
                    "AND client_visible AND approval_status <> 'approved')", job_id)
                if not remaining:
                    await _transition(conn, job_id, [job["status"]], "approved",
                                      actor_role="client", actor_id=uid, owner_id=uid,
                                      set_sql="approved_at = NOW()")
                    transitioned = True
        row = await _client_job_row(conn, job_id, uid)
    if transitioned:
        background.add_task(bid_notifications.notify, str(job_id), "approved")
    return {"file": _bid_file(frow), "job": job_summary(row, today_skopje())}


@router.post("/jobs/{job_id}/files/{file_id}/request-changes")
async def request_file_changes(job_id: uuid.UUID, file_id: uuid.UUID, body: CommentBody,
                               background: BackgroundTasks, user=Depends(require_portal_user)):
    uid = user.user_id
    comment = body.comment.strip()
    if not comment:
        raise HTTPException(status_code=400, detail="Опишете ги измените што ги барате.")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            job = await _visible_file_for_review(conn, job_id, file_id, uid)
            frow = await conn.fetchrow(
                "UPDATE bid_job_files SET approval_status = 'changes_requested', "
                "client_comment = $2, reviewed_at = NOW(), updated_at = NOW() "
                "WHERE id = $1 RETURNING *", file_id, comment)
            await _audit(conn, job_id, "file_changes_requested", "client", uid,
                         {"file_id": str(file_id)})
            if job["status"] == "changes_requested":
                await conn.execute(
                    "UPDATE bid_jobs SET updated_at = NOW() WHERE id = $1", job_id)
            else:
                await _transition(conn, job_id, [job["status"]], "changes_requested",
                                  actor_role="client", actor_id=uid, owner_id=uid,
                                  set_sql="approved_at = NULL")
        row = await _client_job_row(conn, job_id, uid)
    # The key is per publish cycle, so a second file in the same round sends nothing.
    background.add_task(bid_notifications.notify, str(job_id), "changes_requested")
    return {"file": _bid_file(frow), "job": job_summary(row, today_skopje())}


@router.post("/jobs/{job_id}/approve-all")
async def approve_all(job_id: uuid.UUID, background: BackgroundTasks,
                      user=Depends(require_portal_user)):
    uid = user.user_id
    transitioned = False
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            job = await conn.fetchrow(
                "SELECT id, status FROM bid_jobs WHERE id = $1 AND user_id = $2 FOR UPDATE",
                job_id, uid)
            if not job:
                raise _not_found()
            # Only from 'ready': in 'changes_requested' a file is being fixed and
            # approving everything would approve its old version.
            if job["status"] not in ("ready", "approved"):
                raise _wrong_status()
            if job["status"] != "approved":
                visible = await conn.fetchval(
                    "SELECT COUNT(*) FROM bid_job_files WHERE job_id = $1 AND client_visible",
                    job_id)
                if not visible:
                    raise _wrong_status()
                await conn.execute(
                    "UPDATE bid_job_files SET approval_status = 'approved', reviewed_at = NOW(), "
                    "updated_at = NOW() WHERE job_id = $1 AND client_visible "
                    "AND approval_status = 'pending'", job_id)
                pending = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM bid_job_files WHERE job_id = $1 "
                    "AND client_visible AND approval_status <> 'approved')", job_id)
                if pending:
                    raise _wrong_status()
                await _transition(conn, job_id, [job["status"]], "approved",
                                  actor_role="client", actor_id=uid, owner_id=uid,
                                  set_sql="approved_at = NOW()", detail={"action": "approve_all"})
                transitioned = True
        row = await _client_job_row(conn, job_id, uid)
    if transitioned:
        background.add_task(bid_notifications.notify, str(job_id), "approved")
    return {"job": job_summary(row, today_skopje())}


@router.post("/jobs/{job_id}/mark-submitted")
async def mark_submitted(job_id: uuid.UUID, background: BackgroundTasks,
                         user=Depends(require_portal_user)):
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # The client signs and submits only an approved bid; the admin
            # endpoint below stays unrestricted as the escape hatch.
            await _transition(conn, job_id, ["approved"], "submitted",
                              actor_role="client", actor_id=uid, owner_id=uid,
                              set_sql="submitted_at = NOW()",
                              extra_where="published_at IS NOT NULL")
        row = await _client_job_row(conn, job_id, uid)
    background.add_task(bid_notifications.notify, str(job_id), "submitted")
    return {"job": job_summary(row, today_skopje())}


@router.post("/jobs/{job_id}/cancel")
async def cancel_my_job(job_id: uuid.UUID, background: BackgroundTasks,
                        body: Optional[CancelBody] = None, user=Depends(require_portal_user)):
    uid = user.user_id
    reason = ((body.reason if body else None) or "").strip() or None
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _transition(conn, job_id, PRE_SUBMITTED, "cancelled",
                              actor_role="client", actor_id=uid, owner_id=uid,
                              set_sql="cancelled_at = NOW(), cancelled_by = 'client', "
                                      "cancel_reason = $4",
                              args=(reason,), detail={"reason": reason} if reason else None)
        row = await _client_job_row(conn, job_id, uid)
    background.add_task(bid_notifications.notify, str(job_id), "cancelled_by_client")
    return {"job": job_summary(row, today_skopje())}


@router.get("/jobs/{job_id}/messages")
async def get_job_messages(job_id: uuid.UUID, user=Depends(require_portal_user)):
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _client_job_row(conn, job_id, uid)
        await _mark_read(conn, uid, job_id, "client")
        messages = await _fetch_messages(conn, uid, job_id)
    return {"messages": messages}


@router.post("/jobs/{job_id}/messages")
async def post_job_message(job_id: uuid.UUID, body: MessageBody, background: BackgroundTasks,
                           user=Depends(require_portal_user)):
    uid = user.user_id
    text = _clean_body(body.body)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _client_job_row(conn, job_id, uid)
        await _check_client_message_rate(conn, uid)
        msg = await _insert_message(conn, uid, job_id, "client", uid, text)
    background.add_task(bid_notifications.notify_message, msg["id"])
    return {"message": msg}


@router.get("/messages")
async def get_general_messages(user=Depends(require_portal_user)):
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _mark_read(conn, uid, None, "client")
        messages = await _fetch_messages(conn, uid, None)
    return {"messages": messages}


@router.post("/messages")
async def post_general_message(body: MessageBody, background: BackgroundTasks,
                               user=Depends(require_portal_user)):
    uid = user.user_id
    text = _clean_body(body.body)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _check_client_message_rate(conn, uid)
        msg = await _insert_message(conn, uid, None, "client", uid, text)
    background.add_task(bid_notifications.notify_message, msg["id"])
    return {"message": msg}


# --- Company document library ---------------------------------------------
_DOC_ORDER = ("ORDER BY array_position(ARRAY['" + "','".join(DOC_CATEGORIES)
              + "']::text[], category::text), created_at DESC")


@router.get("/documents")
async def list_documents(user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM client_documents WHERE user_id = $1 {_DOC_ORDER}", user.user_id)
    today = today_skopje()
    return {"documents": [_client_document(r, today) for r in rows]}


@router.post("/documents")
async def upload_document(file: UploadFile = File(...), category: str = Form(...),
                          title: Optional[str] = Form(None), expires_on: Optional[str] = Form(None),
                          user=Depends(require_portal_user)):
    if category not in DOC_CATEGORIES:
        raise HTTPException(status_code=400, detail="Невалидна категорија.")
    exp = _parse_date(expires_on)
    if title is not None and len(title.strip()) > 300:
        raise HTTPException(status_code=400, detail="Насловот е предолг.")
    uid = user.user_id
    quota = MAX_DOCUMENT_BYTES.get(getattr(user, "account_type", None) or "",
                                   MAX_DOCUMENT_BYTES_DEFAULT)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        # Cheap early reject before the upload is written to disk.
        count = await conn.fetchval("SELECT COUNT(*) FROM client_documents WHERE user_id = $1", uid)
        if (count or 0) >= MAX_DOCUMENTS_PER_USER:
            raise HTTPException(status_code=400, detail=ERR_DOC_LIMIT)
        rel, size, _ext, original, mime = await _save_upload(file, f"company/{uid}")
        try:
            async with conn.transaction():
                # Serialise this user's uploads so parallel requests cannot pass
                # the count/byte checks together.
                await conn.execute("SELECT 1 FROM users WHERE user_id = $1 FOR UPDATE", uid)
                used = await conn.fetchrow(
                    "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS bytes "
                    "FROM client_documents WHERE user_id = $1", uid)
                if int(used["n"] or 0) >= MAX_DOCUMENTS_PER_USER:
                    raise HTTPException(status_code=400, detail=ERR_DOC_LIMIT)
                if int(used["bytes"] or 0) + size > quota:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Достигнат е максималниот простор за документи "
                               f"({quota // (1024 * 1024)} MB). Избришете стари документи.")
                row = await conn.fetchrow(
                    """
                    INSERT INTO client_documents (user_id, category, title, storage_path,
                                                  original_name, mime, size_bytes, expires_on,
                                                  uploaded_by_role)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'client') RETURNING *
                    """,
                    uid, category, _title_from(original, title), rel, original[:255],
                    mime, size, exp)
        except BaseException:
            _remove_file(rel)
            raise
    return {"document": _client_document(row, today_skopje())}


@router.patch("/documents/{doc_id}")
async def update_document(doc_id: uuid.UUID, body: DocumentPatch,
                          user=Depends(require_portal_user)):
    fields = body.model_fields_set
    sets: list[str] = []
    args: list[Any] = [doc_id, user.user_id]
    if "title" in fields:
        t = (body.title or "").strip()
        if not t:
            raise HTTPException(status_code=400, detail="Насловот е задолжителен.")
        args.append(t[:300])
        sets.append(f"title = ${len(args)}")
    if "category" in fields:
        if body.category not in DOC_CATEGORIES:
            raise HTTPException(status_code=400, detail="Невалидна категорија.")
        args.append(body.category)
        sets.append(f"category = ${len(args)}")
    if "expires_on" in fields:
        args.append(body.expires_on)
        sets.append(f"expires_on = ${len(args)}")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        if sets:
            row = await conn.fetchrow(
                f"UPDATE client_documents SET {', '.join(sets)}, updated_at = NOW() "
                f"WHERE id = $1 AND user_id = $2 RETURNING *", *args)
        else:
            row = await conn.fetchrow(
                "SELECT * FROM client_documents WHERE id = $1 AND user_id = $2", doc_id,
                user.user_id)
    if not row:
        raise _not_found(ERR_DOC_NOT_FOUND)
    return {"document": _client_document(row, today_skopje())}


@router.get("/documents/{doc_id}/download")
async def download_document(doc_id: uuid.UUID, user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT storage_path, mime, original_name FROM client_documents "
            "WHERE id = $1 AND user_id = $2", doc_id, user.user_id)
    if not row:
        raise _not_found(ERR_DOC_NOT_FOUND)
    return _file_response(row["storage_path"], row["mime"], row["original_name"])


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: uuid.UUID, user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rel = await conn.fetchval(
            "DELETE FROM client_documents WHERE id = $1 AND user_id = $2 RETURNING storage_path",
            doc_id, user.user_id)
    if rel is None:
        raise _not_found(ERR_DOC_NOT_FOUND)
    _remove_file(rel)
    return {"deleted": True}


# --- Portal home, matched tenders, deadlines, calendar --------------------
@router.get("/portal/summary")
async def portal_summary(user=Depends(require_portal_user)):
    today = today_skopje()
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(CLIENT_JOB_SQL + " WHERE j.user_id = $1", uid)
        unread = await conn.fetchrow(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE job_id IS NULL) AS general "
            "FROM bid_messages WHERE user_id = $1 AND sender_role = 'admin' "
            "AND read_by_client_at IS NULL", uid)
        matched = await _matched_tenders(conn, uid, today, 5)
        prof = await conn.fetchrow(
            "SELECT account_type, company_name FROM users WHERE user_id = $1", uid)
    jobs = [job_summary(r, today) for r in rows]
    by_deadline = lambda j: (j["closing_date"] is None, j["closing_date"] or "")  # noqa: E731
    your_move = sorted([j for j in jobs if j["whose_move"] == "client"], key=by_deadline)
    active = sorted([j for j in jobs if j["status"] not in TERMINAL and j["whose_move"] != "client"],
                    key=by_deadline)
    return {
        "account_type": (prof["account_type"] if prof else None)
                        or getattr(user, "account_type", None) or "free",
        "company_name": (prof["company_name"] if prof else None)
                        or getattr(user, "company_name", None),
        "your_move": your_move,
        "active_jobs": active,
        "counts": {"your_move": len(your_move), "active": len(active), "total": len(jobs)},
        "unread_messages": int(unread["total"] or 0) if unread else 0,
        "unread_general": int(unread["general"] or 0) if unread else 0,
        "matched_tenders": matched,
        "first_run": len(jobs) == 0,
    }


@router.get("/portal/matched")
async def portal_matched(limit: int = Query(50, ge=1, le=100),
                         user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        tenders = await _matched_tenders(conn, user.user_id, today_skopje(), limit)
    return {"tenders": tenders}


@router.get("/portal/unread")
async def portal_unread(user=Depends(require_portal_user)):
    """Cheap unread counters for the portal navigation badge (fetched on navigation)."""
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        unread = await conn.fetchrow(
            "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE job_id IS NULL) AS general "
            "FROM bid_messages WHERE user_id = $1 AND sender_role = 'admin' "
            "AND read_by_client_at IS NULL", user.user_id)
    total = int(unread["total"] or 0) if unread else 0
    general = int(unread["general"] or 0) if unread else 0
    return {"unread_messages": total, "unread_general": general, "unread_jobs": total - general}


MAX_KEYWORDS = 20
PORTAL_ALERT_NAME = "Следење (портал)"


def clean_keywords(raw: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for k in raw or []:
        kw = re.sub(r"\s+", " ", str(k or "")).strip()[:60].strip()
        if len(kw) < 3 or kw.lower() in seen:
            continue
        seen.add(kw.lower())
        out.append(kw)
        if len(out) >= MAX_KEYWORDS:
            break
    return out


async def _portal_alert(conn, uid) -> Optional[Mapping]:
    """The client's first keyword alert (the one /qualify creates), edited from the portal."""
    return await conn.fetchrow(
        "SELECT alert_id, criteria FROM tender_alerts WHERE user_id = $1 "
        "AND alert_type = 'keyword' ORDER BY created_at ASC LIMIT 1", uid)


def _alert_keywords(row: Optional[Mapping]) -> list[str]:
    if not row:
        return []
    crit = row["criteria"]
    if isinstance(crit, str):
        try:
            crit = json.loads(crit) if crit else {}
        except ValueError:
            crit = {}
    kws = (crit or {}).get("keywords") if isinstance(crit, dict) else None
    return [str(k) for k in kws] if isinstance(kws, list) else []


@router.get("/portal/keywords")
async def get_portal_keywords(user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await _portal_alert(conn, user.user_id)
    return {"keywords": _alert_keywords(row)}


@router.put("/portal/keywords")
async def set_portal_keywords(body: KeywordsBody, user=Depends(require_portal_user)):
    """Keywords that drive „Тендери за мене“ (and the alert crons)."""
    kws = clean_keywords(body.keywords)
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await _portal_alert(conn, uid)
            if row:
                await conn.execute(
                    "UPDATE tender_alerts SET criteria = jsonb_set(COALESCE(criteria, '{}'::jsonb), "
                    "'{keywords}', $2::jsonb), is_active = TRUE, updated_at = NOW() "
                    "WHERE alert_id = $1", row["alert_id"], json.dumps(kws, ensure_ascii=False))
            elif kws:
                await conn.execute(
                    "INSERT INTO tender_alerts (user_id, name, alert_type, criteria) "
                    "VALUES ($1, $2, 'keyword', $3::jsonb)",
                    uid, PORTAL_ALERT_NAME, json.dumps({"keywords": kws}, ensure_ascii=False))
    return {"keywords": kws}


@router.get("/deadlines")
async def deadlines(user=Depends(require_portal_user)):
    today = today_skopje()
    uid = user.user_id
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        jobs = await conn.fetch(
            """
            SELECT j.id, j.tender_id, j.status, t.title, t.procuring_entity, t.closing_date
            FROM bid_jobs j JOIN tenders t ON t.tender_id = j.tender_id
            WHERE j.user_id = $1 AND j.status NOT IN ('won','lost','cancelled')
              AND t.closing_date IS NOT NULL AND t.closing_date >= $2
            """,
            uid, today - timedelta(days=30))
        matched = await conn.fetch(
            "SELECT * FROM (" + _MATCHED_SQL.replace("LIMIT $3", "") + ") y "
            "WHERE y.closing_date IS NOT NULL ORDER BY y.closing_date ASC LIMIT $3",
            uid, today, 20)
    items = [{
        "date": _ser(_as_date(r["closing_date"])), "kind": "job", "job_id": _ser(r["id"]),
        "tender_id": r["tender_id"], "title": r["title"],
        "procuring_entity": r["procuring_entity"], "status": r["status"],
    } for r in jobs]
    items += [{
        "date": _ser(_as_date(r["closing_date"])), "kind": "matched", "job_id": None,
        "tender_id": r["tender_id"], "title": r["title"],
        "procuring_entity": r["procuring_entity"], "status": None,
    } for r in matched]
    items.sort(key=lambda i: i["date"])
    return {"deadlines": items}


def _calendar_payload(token: str) -> dict:
    url = f"{PUBLIC_API}/api/bid-service/calendar/{token}.ics"
    return {"token": token, "url": url, "webcal_url": re.sub(r"^https?://", "webcal://", url)}


@router.get("/calendar-token")
async def get_calendar_token(user=Depends(require_portal_user)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        token = await conn.fetchval("SELECT calendar_token FROM users WHERE user_id = $1",
                                    user.user_id)
        if not token:
            new = secrets.token_urlsafe(24)
            token = await conn.fetchval(
                "UPDATE users SET calendar_token = COALESCE(calendar_token, $2) "
                "WHERE user_id = $1 RETURNING calendar_token", user.user_id, new)
    return _calendar_payload(token)


@router.post("/calendar-token/rotate")
async def rotate_calendar_token(user=Depends(require_portal_user)):
    token = secrets.token_urlsafe(24)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET calendar_token = $2 WHERE user_id = $1",
                           user.user_id, token)
    return _calendar_payload(token)


@router.get("/calendar/{token}.ics")
async def calendar_feed(token: str):
    """Public iCal feed; the unguessable token is the only credential."""
    if not token or len(token) > 64:
        raise HTTPException(status_code=404, detail="Календарот не е пронајден.")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        owner = await conn.fetchrow(
            "SELECT user_id, account_type, role FROM users WHERE calendar_token = $1", token)
        # A former client (downgraded account) stops receiving the feed.
        if not owner or not is_portal_user(owner["account_type"], owner["role"]):
            raise HTTPException(status_code=404, detail="Календарот не е пронајден.")
        uid = owner["user_id"]
        rows = await conn.fetch(
            """
            SELECT j.id, j.tender_id, j.status, j.outcome, t.title, t.closing_date
            FROM bid_jobs j JOIN tenders t ON t.tender_id = j.tender_id
            WHERE j.user_id = $1 AND j.status NOT IN ('cancelled','lost','won')
              AND t.closing_date IS NOT NULL
            ORDER BY t.closing_date
            """,
            uid)
    events = [{
        "uid": f"{r['id']}-deadline",
        "date": _as_date(r["closing_date"]),
        "summary": f"Рок: {r['tender_id']} {(r['title'] or '')[:120]}".strip(),
        "description": phase_for(r["status"], r["outcome"])[0],
        "url": f"{SITE}/portal/bid/{r['id']}",
    } for r in rows]
    body = build_ics(events, datetime.now(timezone.utc))
    return Response(content=body, media_type="text/calendar",  # Starlette appends "; charset=utf-8"
                    headers={"Cache-Control": "private, max-age=900"})


# ===========================================================================
# Admin endpoints
# ===========================================================================
async def _admin_summary(conn, today: date) -> dict:
    rows = await conn.fetch("SELECT status, COUNT(*) AS n FROM bid_jobs GROUP BY status")
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        if r["status"] in counts:
            counts[r["status"]] = int(r["n"])
    overdue = await conn.fetchval(
        "SELECT COUNT(*) FROM bid_jobs j JOIN tenders t ON t.tender_id = j.tender_id "
        "WHERE j.status = ANY($1::text[]) AND t.closing_date < $2",
        list(PRE_SUBMITTED), today)
    unread = await conn.fetchval(
        "SELECT COUNT(*) FROM bid_messages WHERE sender_role = 'client' "
        "AND read_by_admin_at IS NULL")
    return {
        "counts": counts,
        "needs_us": sum(counts[s] for s in NEEDS_US),
        "needs_client": sum(counts[s] for s in NEEDS_CLIENT),
        "overdue": int(overdue or 0),
        "unread_messages": int(unread or 0),
    }


@router.get("/admin/jobs")
async def admin_list_jobs(status: str = Query("open"), assigned_to: Optional[str] = Query(None),
                          user_id: Optional[uuid.UUID] = Query(None),
                          q: Optional[str] = Query(None, max_length=200),
                          limit: int = Query(200, ge=1, le=500),
                          admin=Depends(require_admin)):
    where: list[str] = []
    args: list[Any] = []
    if status == "open":
        where.append("j.status NOT IN ('won','lost','cancelled')")
    elif status == "needs_us":
        args.append(list(NEEDS_US))
        where.append(f"j.status = ANY(${len(args)}::text[])")
    elif status == "needs_client":
        args.append(list(NEEDS_CLIENT))
        where.append(f"j.status = ANY(${len(args)}::text[])")
    elif status in STATUSES:
        args.append(status)
        where.append(f"j.status = ${len(args)}")
    elif status != "all":
        raise HTTPException(status_code=400, detail="Невалиден филтер за статус.")
    if assigned_to:
        if assigned_to == "me":
            args.append(admin.user_id)
        else:
            try:
                args.append(uuid.UUID(assigned_to))
            except ValueError:
                raise HTTPException(status_code=400, detail="Невалиден корисник.")
        where.append(f"j.assigned_to = ${len(args)}")
    if user_id:
        args.append(user_id)
        where.append(f"j.user_id = ${len(args)}")
    if q and q.strip():
        args.append(f"%{_like_escape(q.strip())}%")
        n = len(args)
        where.append(f"(j.tender_id ILIKE ${n} ESCAPE '\\' OR t.title ILIKE ${n} ESCAPE '\\' "
                     f"OR u.company_name ILIKE ${n} ESCAPE '\\' OR u.email ILIKE ${n} ESCAPE '\\')")
    args.append(list(NEEDS_US))
    needs_us_n = len(args)
    args.append(limit)
    limit_n = len(args)
    sql = (
        "SELECT * FROM (" + ADMIN_JOB_SQL.replace("SELECT j.*,", "SELECT COUNT(*) OVER () AS total_count, j.*,", 1)
        + (" WHERE " + " AND ".join(where) if where else "")
        + f") x ORDER BY (x.status = ANY(${needs_us_n}::text[])) DESC, x.closing_date ASC NULLS LAST, "
          f"x.updated_at DESC LIMIT ${limit_n}"
    )
    today = today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        summary = await _admin_summary(conn, today)
    total = int(rows[0]["total_count"]) if rows else 0
    return {"jobs": [_admin_job_summary(r, today) for r in rows], "total": total,
            "summary": summary}


@router.post("/admin/jobs")
async def admin_create_job(body: AdminCreateJobBody, admin=Depends(require_admin)):
    """Open (or reopen) a bid job for a client, e.g. for a lead who asked by phone.
    Same fee snapshot and status rules as the client's begin; no admin email."""
    tender_id = body.tender_id.strip()
    if not tender_id:
        raise HTTPException(status_code=400, detail="Невалиден тендер.")
    note = (body.client_note or "").strip() or None
    uid = body.user_id
    today = today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        prefs = await conn.fetchrow(
            "SELECT prep_fee_mkd, success_fee_pct, free_drafting, account_type FROM users "
            "WHERE user_id = $1", uid)
        if not prefs:
            raise _not_found(ERR_CLIENT_NOT_FOUND)
        tender = await _open_tender_or_raise(conn, tender_id)
        existing = await _existing_job(conn, uid, tender_id)
        if _is_live(existing):
            return await _admin_job_response(conn, existing["id"], created=False)
        if not tender_open_for_begin(tender["status"], tender["closing_date"], today):
            raise HTTPException(status_code=409, detail="Рокот за поднесување на овој тендер истече.")
        async with conn.transaction():
            # The client needs portal access to see the job.
            if prefs["account_type"] == "free":
                await conn.execute(
                    "UPDATE users SET account_type = 'prospect', updated_at = NOW() "
                    "WHERE user_id = $1 AND account_type = 'free'", uid)
            job_id = await _create_or_reopen(conn, uid, tender_id, note, existing,
                                             actor_role="admin", actor_id=admin.user_id,
                                             free_drafting=bool(prefs["free_drafting"]),
                                             prefs=prefs)
            if job_id is None:
                job_id = await conn.fetchval(
                    "SELECT id FROM bid_jobs WHERE user_id = $1 AND tender_id = $2",
                    uid, tender_id)
                return await _admin_job_response(conn, job_id, created=False)
        return await _admin_job_response(conn, job_id, created=True)


@router.get("/admin/summary", dependencies=[Depends(require_admin)])
async def admin_summary():
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        return await _admin_summary(conn, today_skopje())


async def _client_info_row(conn, user_id) -> Optional[Mapping]:
    return await conn.fetchrow(
        "SELECT user_id, email, full_name, company_name, account_type, free_drafting, "
        "prep_fee_mkd, success_fee_pct, terms_agreed_at, agreement_version, "
        "stripe_mandate_pm_id, stripe_card_brand, stripe_card_last4, "
        "success_fee_authorised_at, success_fee_authorised_via, success_fee_authorised_ref "
        "FROM users WHERE user_id = $1", user_id)


@router.get("/admin/jobs/{job_id}", dependencies=[Depends(require_admin)])
async def admin_get_job(job_id: uuid.UUID):
    today = today_skopje()
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        first = await _admin_job_row(conn, job_id)
        uid = first["user_id"]
        await _mark_read(conn, uid, job_id, "admin")
        row = await _admin_job_row(conn, job_id)
        files = await conn.fetch(
            "SELECT * FROM bid_job_files WHERE job_id = $1 ORDER BY created_at", job_id)
        messages = await _fetch_messages(conn, uid, job_id)
        client = await _client_info_row(conn, uid)
        docs = await conn.fetch(
            f"SELECT * FROM client_documents WHERE user_id = $1 {_DOC_ORDER}", uid)
        events = await conn.fetch(
            "SELECT * FROM bid_job_events WHERE job_id = $1 ORDER BY created_at DESC, id DESC "
            "LIMIT 200", job_id)
        win = await conn.fetchrow(_WIN_FOR_JOB_SQL, job_id)
        gate = await conn.fetchrow(_PUBLISH_GATE_SQL, job_id)
    job = _admin_job_detail(row, today)
    missing = success_fee_missing(gate)
    # [] = terms + card both present, flag not stamped yet: publish self-heals it.
    job["publish_blocked_reason"] = publish_blocked_text(missing) if missing else None
    return {
        "job": job,
        "tender": _tender_summary(row),
        "files": [_bid_file(f, admin=True) for f in files],
        "messages": messages,
        "client": _client_info(client) if client else None,
        "client_documents": [_client_document(d, today) for d in docs],
        "events": [_event(e) for e in events],
        "payment": _payment(row, win),
    }


async def _admin_job_response(conn, job_id: uuid.UUID, **extra) -> dict:
    row = await _admin_job_row(conn, job_id)
    return {"job": _admin_job_summary(row, today_skopje()), **extra}


@router.patch("/admin/jobs/{job_id}")
async def admin_update_job(job_id: uuid.UUID, body: AdminJobPatch, admin=Depends(require_admin)):
    fields = body.model_fields_set
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            job = await conn.fetchrow(
                "SELECT id, paid_at, prep_fee_mkd, invoice_number FROM bid_jobs "
                "WHERE id = $1 FOR UPDATE", job_id)
            if not job:
                raise _not_found()
            if "prep_fee_mkd" in fields and body.prep_fee_mkd is not None:
                if job["paid_at"] is not None:
                    raise HTTPException(status_code=409,
                                        detail="Надоместокот не може да се менува по уплатата.")
                if job["invoice_number"] is not None:
                    # The portal must keep showing the invoiced amount; a new fee
                    # goes through POST /invoice with a new invoice number.
                    raise HTTPException(status_code=409, detail=(
                        "Фактурата е веќе издадена. За нов износ издадете нова фактура."))
                await conn.execute(
                    "UPDATE bid_jobs SET prep_fee_mkd = $2, updated_at = NOW() WHERE id = $1",
                    job_id, body.prep_fee_mkd)
                await _audit(conn, job_id, "fee_updated", "admin", admin.user_id,
                             {"from": job["prep_fee_mkd"], "to": body.prep_fee_mkd})
            if "admin_notes" in fields:
                notes = (body.admin_notes or "").strip() or None
                await conn.execute(
                    "UPDATE bid_jobs SET admin_notes = $2, updated_at = NOW() WHERE id = $1",
                    job_id, notes)
                await _audit(conn, job_id, "notes_updated", "admin", admin.user_id)
        return await _admin_job_response(conn, job_id)


@router.post("/admin/jobs/{job_id}/invoice")
async def admin_issue_invoice(job_id: uuid.UUID, body: InvoiceBody, background: BackgroundTasks,
                              admin=Depends(require_admin)):
    number = body.invoice_number.strip()
    if not number:
        raise HTTPException(status_code=400, detail="Внесете број на фактура.")
    stale_invoice_file: Optional[str] = None
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            prev = await conn.fetchrow(
                "SELECT invoice_number, invoice_file_path FROM bid_jobs WHERE id = $1 FOR UPDATE",
                job_id)
            await _transition(conn, job_id, ["requested", "payment_required"], "payment_required",
                              actor_role="admin", actor_id=admin.user_id,
                              set_sql="prep_fee_mkd = $4, invoice_number = $5, "
                                      "invoice_issued_at = NOW()",
                              args=(body.prep_fee_mkd, number), event="invoice_issued",
                              detail={"invoice_number": number, "prep_fee_mkd": body.prep_fee_mkd})
            if prev and prev["invoice_file_path"] and prev["invoice_number"] != number:
                # A re-issued invoice must not show the previous invoice's PDF.
                stale_invoice_file = prev["invoice_file_path"]
                await conn.execute(
                    "UPDATE bid_jobs SET invoice_file_path = NULL, invoice_file_name = NULL "
                    "WHERE id = $1", job_id)
        resp = await _admin_job_response(conn, job_id)
    _remove_file(stale_invoice_file)
    # The key includes the invoice number: a corrected number emails the client
    # once more; re-issuing the same number does not.
    background.add_task(bid_notifications.notify, str(job_id), "invoice_issued")
    return resp


@router.post("/admin/jobs/{job_id}/invoice-file")
async def admin_upload_invoice_file(job_id: uuid.UUID, file: UploadFile = File(...),
                                    admin=Depends(require_admin)):
    """Attach the invoice PDF so the client can download it from the portal."""
    if allowed_extension(file.filename) != ".pdf":
        raise HTTPException(status_code=400, detail="Фактурата мора да биде PDF.")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT invoice_number, invoice_file_path FROM bid_jobs WHERE id = $1", job_id)
        if not job:
            raise _not_found()
        if not job["invoice_number"]:
            raise HTTPException(status_code=409, detail="Прво издадете фактура.")
        rel, _size, _ext, original, _mime = await _save_upload(file, f"jobs/{job_id}")
        try:
            async with conn.transaction():
                old = await conn.fetchval(
                    "SELECT invoice_file_path FROM bid_jobs WHERE id = $1 FOR UPDATE", job_id)
                await conn.execute(
                    "UPDATE bid_jobs SET invoice_file_path = $2, invoice_file_name = $3, "
                    "updated_at = NOW() WHERE id = $1", job_id, rel, original[:255])
                await _audit(conn, job_id, "invoice_file_uploaded", "admin", admin.user_id,
                             {"name": original[:255]})
        except BaseException:
            _remove_file(rel)
            raise
        resp = await _admin_job_response(conn, job_id)
    if old and old != rel:
        _remove_file(old)
    return resp


@router.get("/admin/jobs/{job_id}/invoice-file", dependencies=[Depends(require_admin)])
async def admin_download_invoice_file(job_id: uuid.UUID):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT invoice_file_path, invoice_file_name FROM bid_jobs WHERE id = $1", job_id)
    if not row or not row["invoice_file_path"]:
        raise _not_found(ERR_FILE_NOT_FOUND)
    return _file_response(row["invoice_file_path"], None, row["invoice_file_name"] or "faktura.pdf")


@router.post("/admin/jobs/{job_id}/mark-paid")
async def admin_mark_paid(job_id: uuid.UUID, background: BackgroundTasks,
                          body: Optional[MarkPaidBody] = None, admin=Depends(require_admin)):
    paid = body.paid_at if body else None
    # Noon Skopje time, so the date never shifts when rendered in any timezone.
    paid_at = datetime.combine(paid, time(12, 0), tzinfo=ZoneInfo("Europe/Skopje")) if paid else None
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                result = await bid_payments.mark_job_paid(
                    conn, job_id, "invoice", paid_at=paid_at, actor_role="admin",
                    actor_id=admin.user_id)
            except LookupError:
                raise _not_found()
            duplicate = result.get("reason") == "duplicate"
            if (not result["changed"] and not duplicate
                    and result.get("reason") != "already_paid"):
                raise _wrong_status()
        if duplicate:
            # Committed: the duplicate_payment audit row stays. Background tasks do
            # not run on an error response, so the admin alert is sent here.
            await bid_payments.notify_paid(str(job_id), result, "invoice")
            raise HTTPException(status_code=409, detail=ERR_ALREADY_PAID_CARD)
        resp = await _admin_job_response(conn, job_id, account_promoted=result["promoted"])
    background.add_task(bid_payments.notify_paid, str(job_id), result, "invoice")
    return resp


@router.post("/admin/jobs/{job_id}/mark-free")
async def admin_mark_free(job_id: uuid.UUID, background: BackgroundTasks,
                          admin=Depends(require_admin)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await _transition(conn, job_id, ["requested", "payment_required"], "preparing",
                                    actor_role="admin", actor_id=admin.user_id,
                                    set_sql="free = TRUE, paid_via = 'free'", event="marked_free")
            promoted = await _promote_user(conn, row["user_id"])
        resp = await _admin_job_response(conn, job_id, account_promoted=promoted)
    background.add_task(bid_notifications.notify, str(job_id), "preparing")
    return resp


@router.post("/admin/jobs/{job_id}/files")
async def admin_upload_file(job_id: uuid.UUID, file: UploadFile = File(...),
                            kind: str = Form(...), title: Optional[str] = Form(None),
                            admin=Depends(require_admin)):
    if kind not in FILE_KINDS:
        raise HTTPException(status_code=400, detail="Невалиден тип на документ.")
    if title is not None and len(title.strip()) > 300:
        raise HTTPException(status_code=400, detail="Насловот е предолг.")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM bid_jobs WHERE id = $1", job_id)
        if status is None:
            raise _not_found()
        if status in TERMINAL:
            raise _wrong_status()
        rel, size, _ext, original, mime = await _save_upload(file, f"jobs/{job_id}")
        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO bid_job_files (job_id, kind, title, storage_path, original_name,
                                               mime, size_bytes, uploaded_by)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *
                    """,
                    job_id, kind, _title_from(original, title), rel, original[:255],
                    mime, size, admin.user_id)
                await _audit(conn, job_id, "file_uploaded", "admin", admin.user_id,
                             {"file_id": str(row["id"]), "kind": kind, "title": row["title"]})
        except BaseException:
            _remove_file(rel)
            raise
    return {"file": _bid_file(row, admin=True)}


@router.get("/admin/jobs/{job_id}/files/{file_id}/download", dependencies=[Depends(require_admin)])
async def admin_download_file(job_id: uuid.UUID, file_id: uuid.UUID):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        f = await conn.fetchrow(
            "SELECT storage_path, mime, original_name FROM bid_job_files "
            "WHERE id = $1 AND job_id = $2", file_id, job_id)
    if not f:
        raise _not_found(ERR_FILE_NOT_FOUND)
    return _file_response(f["storage_path"], f["mime"], f["original_name"])


@router.delete("/admin/jobs/{job_id}/files/{file_id}")
async def admin_delete_file(job_id: uuid.UUID, file_id: uuid.UUID, admin=Depends(require_admin)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "DELETE FROM bid_job_files WHERE id = $1 AND job_id = $2 "
                "RETURNING storage_path, title", file_id, job_id)
            if not row:
                raise _not_found(ERR_FILE_NOT_FOUND)
            await _audit(conn, job_id, "file_deleted", "admin", admin.user_id,
                         {"file_id": str(file_id), "title": row["title"]})
    _remove_file(row["storage_path"])
    return {"deleted": True}


@router.post("/admin/jobs/{job_id}/publish")
async def admin_publish(job_id: uuid.UUID, background: BackgroundTasks,
                        admin=Depends(require_admin)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            status = await conn.fetchval(
                "SELECT status FROM bid_jobs WHERE id = $1 FOR UPDATE", job_id)
            if status is None:
                raise _not_found()
            if status not in PUBLISHABLE:
                raise _wrong_status()
            gate = await conn.fetchrow(_PUBLISH_GATE_SQL, job_id)
            missing = success_fee_missing(gate)
            if missing is not None and gate:
                # Terms + card may both be present without the flag set yet.
                if await bid_payments.refresh_success_fee_authorisation(conn, gate["user_id"]):
                    missing = None
            if missing is not None:
                raise HTTPException(status_code=409, detail={
                    "code": "success_fee_not_authorised",
                    "message": ERR_SUCCESS_FEE_NOT_AUTHORISED,
                    "missing": missing,
                })
            n = await conn.fetchval("SELECT COUNT(*) FROM bid_job_files WHERE job_id = $1", job_id)
            if not n:
                raise HTTPException(status_code=400, detail="Нема прикачени документи.")
            await conn.execute(
                "UPDATE bid_job_files SET client_visible = TRUE, approval_status = CASE "
                "WHEN approval_status = 'changes_requested' THEN 'pending' ELSE approval_status END, "
                "updated_at = NOW() WHERE job_id = $1", job_id)
            await _transition(conn, job_id, PUBLISHABLE, "ready",
                              actor_role="admin", actor_id=admin.user_id,
                              set_sql="published_at = NOW(), publish_count = publish_count + 1, "
                                      "approved_at = NULL",
                              event="published", detail={"files": int(n)})
        resp = await _admin_job_response(conn, job_id)
    background.add_task(bid_notifications.notify, str(job_id), "ready")
    return resp


@router.post("/admin/jobs/{job_id}/mark-submitted")
async def admin_mark_submitted(job_id: uuid.UUID, admin=Depends(require_admin)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _transition(conn, job_id, REVIEWABLE, "submitted",
                              actor_role="admin", actor_id=admin.user_id,
                              set_sql="submitted_at = NOW()",
                              extra_where="published_at IS NOT NULL")
        return await _admin_job_response(conn, job_id)


@router.post("/admin/jobs/{job_id}/outcome")
async def admin_set_outcome(job_id: uuid.UUID, body: OutcomeBody, background: BackgroundTasks,
                            admin=Depends(require_admin)):
    outcome = body.outcome
    if outcome == "cancelled":
        set_sql = ("outcome = $4, outcome_at = NOW(), cancelled_at = NOW(), "
                   "cancelled_by = 'admin'")
        kind = "tender_cancelled"
    else:
        set_sql = ("outcome = $4, outcome_at = NOW(), cancelled_at = NULL, cancelled_by = NULL, "
                   "cancel_reason = NULL")
        kind = outcome
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _transition(conn, job_id, ["submitted", "won", "lost", "cancelled"], outcome,
                              actor_role="admin", actor_id=admin.user_id,
                              set_sql=set_sql, args=(outcome,),
                              extra_where="(status <> 'cancelled' OR outcome IS NOT NULL)",
                              detail={"action": "outcome", "outcome": outcome})
            if outcome == "won":
                await _record_admin_win(conn, job_id)
        resp = await _admin_job_response(conn, job_id)
    background.add_task(bid_notifications.notify, str(job_id), kind)
    return resp


_WIN_SOURCE_SQL = """
    SELECT j.*, u.company_name, u.success_fee_pct AS u_pct, t.title, t.procuring_entity,
           t.actual_value_mkd, t.estimated_value_mkd, t.contract_duration
    FROM bid_jobs j JOIN users u ON u.user_id = j.user_id
    LEFT JOIN tenders t ON t.tender_id = j.tender_id
    WHERE j.id = $1
"""


async def _record_admin_win(conn, job_id: uuid.UUID) -> None:
    """outcome=won by an admin: a 'suspected' client_wins row for /admin/wins
    (the admin then confirms the value and fee). Never duplicates."""
    src = await conn.fetchrow(_WIN_SOURCE_SQL, job_id)
    if not src:
        return
    company = _get(src, "company_name") or ""
    row = client_wins.build_win_row(src, {"success_fee_pct": _get(src, "u_pct")}, src,
                                    company or None, 1, None)
    await conn.fetchval(client_wins.INSERT_WIN_SQL, *client_wins.win_insert_args(row))


@router.post("/admin/jobs/{job_id}/assign")
async def admin_assign(job_id: uuid.UUID, body: AssignBody, admin=Depends(require_admin)):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        if body.assigned_to is not None:
            ok = await conn.fetchval(
                "SELECT 1 FROM users WHERE user_id = $1 AND LOWER(role) = 'admin'",
                body.assigned_to)
            if not ok:
                raise HTTPException(status_code=400, detail="Корисникот не е член на тимот.")
        async with conn.transaction():
            res = await conn.fetchval(
                "UPDATE bid_jobs SET assigned_to = $2, updated_at = NOW() WHERE id = $1 RETURNING id",
                job_id, body.assigned_to)
            if res is None:
                raise _not_found()
            await _audit(conn, job_id, "assigned", "admin", admin.user_id,
                         {"assigned_to": str(body.assigned_to) if body.assigned_to else None})
        return await _admin_job_response(conn, job_id)


@router.post("/admin/jobs/{job_id}/cancel")
async def admin_cancel(job_id: uuid.UUID, background: BackgroundTasks,
                       body: Optional[CancelBody] = None, admin=Depends(require_admin)):
    reason = ((body.reason if body else None) or "").strip() or None
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _transition(conn, job_id, PRE_SUBMITTED, "cancelled",
                              actor_role="admin", actor_id=admin.user_id,
                              set_sql="cancelled_at = NOW(), cancelled_by = 'admin', "
                                      "cancel_reason = $4",
                              args=(reason,), detail={"reason": reason} if reason else None)
        resp = await _admin_job_response(conn, job_id)
    background.add_task(bid_notifications.notify, str(job_id), "cancelled_by_admin")
    return resp


@router.post("/admin/jobs/{job_id}/messages")
async def admin_post_job_message(job_id: uuid.UUID, body: MessageBody,
                                 background: BackgroundTasks, admin=Depends(require_admin)):
    text = _clean_body(body.body)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        owner = await conn.fetchval("SELECT user_id FROM bid_jobs WHERE id = $1", job_id)
        if owner is None:
            raise _not_found()
        msg = await _insert_message(conn, owner, job_id, "admin", admin.user_id, text)
    background.add_task(bid_notifications.notify_message, msg["id"])
    return {"message": msg}


async def _require_client(conn, user_id: uuid.UUID) -> None:
    if not await conn.fetchval("SELECT 1 FROM users WHERE user_id = $1", user_id):
        raise _not_found(ERR_CLIENT_NOT_FOUND)


@router.get("/admin/clients/{user_id}/messages", dependencies=[Depends(require_admin)])
async def admin_get_client_messages(user_id: uuid.UUID):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _require_client(conn, user_id)
        await _mark_read(conn, user_id, None, "admin")
        messages = await _fetch_messages(conn, user_id, None)
    return {"messages": messages}


@router.post("/admin/clients/{user_id}/messages")
async def admin_post_client_message(user_id: uuid.UUID, body: MessageBody,
                                    background: BackgroundTasks, admin=Depends(require_admin)):
    text = _clean_body(body.body)
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        await _require_client(conn, user_id)
        msg = await _insert_message(conn, user_id, None, "admin", admin.user_id, text)
    background.add_task(bid_notifications.notify_message, msg["id"])
    return {"message": msg}


@router.get("/admin/inbox", dependencies=[Depends(require_admin)])
async def admin_inbox():
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH th AS (
                SELECT m.user_id, m.job_id, MAX(m.created_at) AS last_message_at,
                       COUNT(*) FILTER (WHERE m.sender_role = 'client'
                                        AND m.read_by_admin_at IS NULL) AS unread_count
                FROM bid_messages m
                GROUP BY m.user_id, m.job_id
            )
            SELECT th.*, u.email AS user_email, u.company_name, j.tender_id,
                   t.title AS tender_title, lm.body AS last_body,
                   lm.sender_role AS last_sender_role
            FROM th
            JOIN users u ON u.user_id = th.user_id
            LEFT JOIN bid_jobs j ON j.id = th.job_id
            LEFT JOIN tenders t ON t.tender_id = j.tender_id
            LEFT JOIN LATERAL (
                SELECT m2.body, m2.sender_role FROM bid_messages m2
                WHERE m2.user_id = th.user_id AND m2.job_id IS NOT DISTINCT FROM th.job_id
                ORDER BY m2.created_at DESC LIMIT 1
            ) lm ON TRUE
            ORDER BY (th.unread_count > 0) DESC, th.last_message_at DESC
            LIMIT 200
            """)
        total_unread = await conn.fetchval(
            "SELECT COUNT(*) FROM bid_messages WHERE sender_role = 'client' "
            "AND read_by_admin_at IS NULL")
    threads = [{
        "user_id": _ser(r["user_id"]),
        "user_email": r["user_email"],
        "company_name": r["company_name"],
        "job_id": _ser(r["job_id"]),
        "tender_id": r["tender_id"],
        "tender_title": r["tender_title"],
        "last_message_at": _ser(r["last_message_at"]),
        "last_body": (r["last_body"] or "")[:140],
        "last_sender_role": r["last_sender_role"],
        "unread_count": int(r["unread_count"] or 0),
    } for r in rows]
    return {"threads": threads, "total_unread": int(total_unread or 0)}


@router.patch("/admin/clients/{user_id}", dependencies=[Depends(require_admin)])
async def admin_update_client(user_id: uuid.UUID, body: ClientPatch):
    fields = body.model_fields_set
    sets: list[str] = []
    args: list[Any] = [user_id]
    if "free_drafting" in fields and body.free_drafting is not None:
        args.append(body.free_drafting)
        sets.append(f"free_drafting = ${len(args)}")
    if "prep_fee_mkd" in fields and body.prep_fee_mkd is not None:
        args.append(body.prep_fee_mkd)
        sets.append(f"prep_fee_mkd = ${len(args)}")
    if "success_fee_pct" in fields and body.success_fee_pct is not None:
        args.append(round(body.success_fee_pct, 2))
        sets.append(f"success_fee_pct = ${len(args)}")
    if "company_name" in fields:
        args.append((body.company_name or "").strip() or None)
        sets.append(f"company_name = ${len(args)}")
    promoted = False
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _require_client(conn, user_id)
            if sets:
                await conn.execute(
                    f"UPDATE users SET {', '.join(sets)}, updated_at = NOW() WHERE user_id = $1",
                    *args)
            if body.free_drafting:
                promoted = await _promote_user(conn, user_id)
        client = await _client_info_row(conn, user_id)
    return {"client": _client_info(client), "account_promoted": promoted}


@router.post("/admin/clients/{user_id}/authorise-success-fee")
async def admin_authorise_success_fee(user_id: uuid.UUID, body: AuthoriseBody,
                                      admin=Depends(require_admin)):
    """Written/offline authorisation (invoice clients without a card)."""
    ref = body.reference.strip()
    if len(ref) < 3:
        raise HTTPException(status_code=400, detail="Внесете референца (број на договор).")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        done = await conn.fetchval(
            "UPDATE users SET success_fee_authorised_at = COALESCE(success_fee_authorised_at, NOW()), "
            "success_fee_authorised_via = COALESCE(success_fee_authorised_via, 'offline'), "
            "success_fee_authorised_ref = COALESCE(success_fee_authorised_ref, $2), "
            "updated_at = NOW() WHERE user_id = $1 RETURNING user_id", user_id, ref)
        if done is None:
            raise _not_found(ERR_CLIENT_NOT_FOUND)
        client = await _client_info_row(conn, user_id)
    return {"client": _client_info(client)}


# --- Client wins (success-fee pipeline) ------------------------------------
WIN_STATUSES = ("suspected", "confirmed", "invoiced", "dismissed")
_WIN_SQL = """
    SELECT w.*, u.email, u.company_name, (u.stripe_mandate_pm_id IS NOT NULL) AS has_card
    FROM client_wins w JOIN users u ON u.user_id = w.user_id
"""


def _num(v: Any) -> Optional[float]:
    return float(v) if v is not None else None


def _win(row: Mapping) -> dict:
    fee = _get(row, "success_fee_mkd")
    months = _get(row, "contract_months")
    return {
        "id": _ser(row["id"]),
        "job_id": _ser(_get(row, "job_id")),
        "user_id": _ser(row["user_id"]),
        "email": _get(row, "email"),
        "company_name": _get(row, "company_name"),
        "tender_id": row["tender_id"],
        "tender_title": _get(row, "tender_title"),
        "procuring_entity": _get(row, "procuring_entity"),
        "matched_name": _get(row, "matched_name"),
        "match_score": _num(_get(row, "match_score")),
        "contract_value_mkd": _num(_get(row, "contract_value_mkd")),
        "value_source": _get(row, "value_source"),
        "contract_months": int(months) if months is not None else None,
        "first_year_value_mkd": _num(_get(row, "first_year_value_mkd")),
        "success_fee_pct": _num(_get(row, "success_fee_pct")),
        "prep_fee_credit_mkd": int(_get(row, "prep_fee_credit_mkd", 0) or 0),
        "success_fee_mkd": int(fee) if fee is not None else None,
        "status": row["status"],
        "detected_at": _ser(_get(row, "detected_at")),
        "confirmed_at": _ser(_get(row, "confirmed_at")),
        "notice_sent_at": _ser(_get(row, "notice_sent_at")),
        "charge_not_before": _ser(_get(row, "charge_not_before")),
        "stripe_invoice_id": _get(row, "stripe_invoice_id"),
        "invoice_number": _get(row, "invoice_number"),
        "invoiced_at": _ser(_get(row, "invoiced_at")),
        "notes": _get(row, "notes"),
        "has_card": bool(_get(row, "has_card", False)),
    }


async def _win_row(conn, win_id: uuid.UUID) -> Mapping:
    row = await conn.fetchrow(_WIN_SQL + " WHERE w.id = $1", win_id)
    if not row:
        raise _not_found("Победата не е пронајдена.")
    return row


@router.get("/admin/wins", dependencies=[Depends(require_admin)])
async def admin_list_wins(status: Optional[str] = Query(None)):
    if status and status not in WIN_STATUSES:
        raise HTTPException(status_code=400, detail="Невалиден филтер за статус.")
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(_WIN_SQL + " WHERE w.status = $1 ORDER BY w.detected_at DESC "
                                    "LIMIT 500", status)
        else:
            rows = await conn.fetch(_WIN_SQL + " ORDER BY w.detected_at DESC LIMIT 500")
        summ = await conn.fetchrow(
            "SELECT COUNT(*) FILTER (WHERE status = 'suspected') AS suspected, "
            "COUNT(*) FILTER (WHERE status = 'confirmed') AS confirmed, "
            "COUNT(*) FILTER (WHERE status = 'invoiced') AS invoiced, "
            "COUNT(*) FILTER (WHERE status = 'dismissed') AS dismissed, "
            "COALESCE(SUM(success_fee_mkd) FILTER (WHERE status = 'suspected'), 0) "
            "  AS pipeline_fee_mkd, "
            "COALESCE(SUM(success_fee_mkd) FILTER (WHERE status IN ('confirmed','invoiced')), 0) "
            "  AS confirmed_fee_mkd "
            "FROM client_wins")
    summ = summ or {}
    summary = {k: int(_get(summ, k, 0) or 0) for k in
               ("suspected", "confirmed", "invoiced", "dismissed", "pipeline_fee_mkd",
                "confirmed_fee_mkd")}
    return {"wins": [_win(r) for r in rows], "summary": summary}


@router.post("/admin/wins/{win_id}/confirm")
async def admin_confirm_win(win_id: uuid.UUID, body: ConfirmWinBody, background: BackgroundTasks,
                            admin=Depends(require_admin)):
    """Confirm a win: 7-day notice to the client and, with a card on file, a DRAFT
    Stripe invoice. Nothing is finalised or charged from code."""
    fields = body.model_fields_set
    notes = (body.notes or "").strip() or None if "notes" in fields else None
    job_won = False
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            win = await conn.fetchrow(
                "SELECT w.*, u.stripe_customer_id, u.stripe_mandate_pm_id FROM client_wins w "
                "JOIN users u ON u.user_id = w.user_id WHERE w.id = $1 FOR UPDATE OF w", win_id)
            if not win:
                raise _not_found("Победата не е пронајдена.")
            if win["status"] != "suspected":
                raise _wrong_status()
            fy = body.first_year_value_mkd if "first_year_value_mkd" in fields else None
            if body.success_fee_mkd is not None:
                fee = int(body.success_fee_mkd)
            elif win["success_fee_pct"] is None:
                # compute_success_fee would silently treat a missing pct as 0 %.
                raise HTTPException(status_code=400, detail=ERR_PCT_MISSING)
            elif fy is not None:
                fee = client_wins.compute_success_fee(fy, win["success_fee_pct"],
                                                      win["prep_fee_credit_mkd"])
            elif win["value_source"] == "estimated":
                # No cap: never bill on the buyer's estimate without a human check.
                raise HTTPException(status_code=400, detail=ERR_ESTIMATED_VALUE)
            else:
                fee = win["success_fee_mkd"]
            if fee is None:
                raise HTTPException(status_code=400,
                                    detail="Внесете вредност за првата година или надомест.")
            row = await conn.fetchrow(
                "UPDATE client_wins SET status = 'confirmed', "
                "first_year_value_mkd = COALESCE($2, first_year_value_mkd), "
                "value_source = CASE WHEN $2::numeric IS NULL THEN value_source ELSE 'admin' END, "
                "success_fee_mkd = $3, notes = COALESCE($4, notes), confirmed_at = NOW(), "
                "confirmed_by = $5, notice_sent_at = NULL, charge_not_before = NULL, "
                "updated_at = NOW() "
                "WHERE id = $1 AND status = 'suspected' RETURNING *",
                win_id, Decimal(str(fy)) if fy is not None else None, fee, notes, admin.user_id)
            if not row:
                raise _wrong_status()
            job_id = win["job_id"]
            if job_id is not None:
                jstatus = await conn.fetchval(
                    "SELECT status FROM bid_jobs WHERE id = $1 FOR UPDATE", job_id)
                if jstatus in ("submitted", "lost"):
                    await _transition(
                        conn, job_id, [jstatus], "won", actor_role="admin", actor_id=admin.user_id,
                        set_sql=("outcome = $4, outcome_at = NOW(), cancelled_at = NULL, "
                                 "cancelled_by = NULL, cancel_reason = NULL"),
                        args=("won",), detail={"action": "win_confirmed", "win_id": str(win_id)})
                    job_won = True
                await _audit(conn, job_id, "win_confirmed", "admin", admin.user_id,
                             {"win_id": str(win_id), "success_fee_mkd": fee})

    invoice = {"created": False, "stripe_invoice_id": None, "message": ""}
    cust, pm = win["stripe_customer_id"], win["stripe_mandate_pm_id"]
    if not body.create_stripe_invoice:
        invoice["message"] = "Stripe фактура не е побарана."
    elif fee <= 0:
        invoice["message"] = "Нема надомест за наплата."
    elif not (cust and pm):
        invoice["message"] = ERR_NO_CARD_FOR_INVOICE
    else:
        try:
            inv_id = await bid_payments.create_success_fee_invoice(
                customer=cust, payment_method=pm, fee_mkd=fee, pct=row["success_fee_pct"],
                tender_title=row["tender_title"], win_id=win_id, job_id=job_id)
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE client_wins SET stripe_invoice_id = $2, updated_at = NOW() "
                    "WHERE id = $1", win_id, inv_id)
            invoice.update(created=True, stripe_invoice_id=inv_id,
                           message=("Нацрт-фактура е креирана во Stripe. Испратете ја од Stripe "
                                    "по истекот на седумте дена."))
        except Exception as e:
            logger.exception("success-fee invoice failed: win=%s", win_id)
            invoice["message"] = f"Stripe фактурата не е креирана: {e}"[:500]
    if job_id is not None and job_won:
        background.add_task(bid_notifications.notify, str(job_id), "won")
    notice = await _send_success_fee_notice(pool, win_id, job_id, fee)
    async with pool.acquire() as conn:
        out = await _win_row(conn, win_id)
    return {"win": _win(out), "invoice": invoice, "notice": notice}


async def _send_success_fee_notice(pool, win_id: uuid.UUID, job_id, fee) -> dict:
    """The 7-day notice runs from the email actually going out: notice_sent_at
    and charge_not_before are stamped only after notify() returns True. A failed
    send releases its dedupe claim, so the admin can resend."""
    if fee is None or int(fee) <= 0:
        return {"sent": False, "message": MSG_NOTICE_NO_FEE}
    if job_id is None:
        return {"sent": False, "message": MSG_NOTICE_NO_JOB}
    sent = await bid_notifications.notify(str(job_id), "success_fee_notice", extra=str(win_id))
    if not sent:
        return {"sent": False, "message": MSG_NOTICE_FAILED}
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE client_wins SET notice_sent_at = NOW(), "
            "charge_not_before = NOW() + INTERVAL '7 days', updated_at = NOW() "
            "WHERE id = $1 AND notice_sent_at IS NULL", win_id)
        await _audit(conn, job_id, "success_fee_notice", "system", None,
                     {"win_id": str(win_id), "success_fee_mkd": int(fee)})
    return {"sent": True, "message": MSG_NOTICE_SENT}


@router.post("/admin/wins/{win_id}/send-notice")
async def admin_send_win_notice(win_id: uuid.UUID, admin=Depends(require_admin)):
    """Resend the success-fee notice of a confirmed win whose first send failed."""
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        win = await _win_row(conn, win_id)
    if win["status"] != "confirmed" or win["notice_sent_at"] is not None:
        raise _wrong_status()
    notice = await _send_success_fee_notice(pool, win_id, win["job_id"], win["success_fee_mkd"])
    async with pool.acquire() as conn:
        out = await _win_row(conn, win_id)
    return {"win": _win(out), "notice": notice}


@router.post("/admin/wins/{win_id}/dismiss")
async def admin_dismiss_win(win_id: uuid.UUID, body: Optional[DismissWinBody] = None,
                            admin=Depends(require_admin)):
    notes = ((body.notes if body else None) or "").strip() or None
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            inv_id = await conn.fetchval(
                "SELECT COALESCE(stripe_invoice_id, '') FROM client_wins "
                "WHERE id = $1 AND status IN ('suspected','confirmed') FOR UPDATE", win_id)
            done = None
            if inv_id is not None:
                done = await conn.fetchval(
                    "UPDATE client_wins SET status = 'dismissed', dismissed_at = NOW(), "
                    "notes = COALESCE($2, notes), updated_at = NOW() "
                    "WHERE id = $1 AND status IN ('suspected','confirmed') RETURNING id",
                    win_id, notes)
        if done is None:
            await _win_row(conn, win_id)  # 404 when missing
            raise _wrong_status()
    message = None
    if inv_id:
        # A leftover draft could be sent from the Dashboard by mistake: delete it.
        if await bid_payments.delete_success_fee_invoice(inv_id):
            message = f"Нацрт-фактурата {inv_id} е избришана во Stripe."
        else:
            message = (f"Нацрт-фактурата {inv_id} не можеше да се избрише автоматски. "
                       "Избришете ја во Stripe.")
    async with pool.acquire() as conn:
        out = await _win_row(conn, win_id)
    return {"win": _win(out), "message": message}


@router.post("/admin/wins/{win_id}/mark-invoiced")
async def admin_mark_win_invoiced(win_id: uuid.UUID, body: Optional[MarkInvoicedBody] = None,
                                  admin=Depends(require_admin)):
    number = ((body.invoice_number if body else None) or "").strip() or None
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        done = await conn.fetchval(
            "UPDATE client_wins SET status = 'invoiced', invoiced_at = NOW(), "
            "invoice_number = COALESCE($2, invoice_number), updated_at = NOW() "
            "WHERE id = $1 AND status = 'confirmed' RETURNING id", win_id, number)
        if done is None:
            await _win_row(conn, win_id)
            raise _wrong_status()
        out = await _win_row(conn, win_id)
    return {"win": _win(out)}


@router.get("/admin/clients/{user_id}/documents", dependencies=[Depends(require_admin)])
async def admin_client_documents(user_id: uuid.UUID):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM client_documents WHERE user_id = $1 {_DOC_ORDER}", user_id)
    today = today_skopje()
    return {"documents": [_client_document(r, today) for r in rows]}


@router.get("/admin/clients/{user_id}/documents/{doc_id}/download",
            dependencies=[Depends(require_admin)])
async def admin_download_client_document(user_id: uuid.UUID, doc_id: uuid.UUID):
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT storage_path, mime, original_name FROM client_documents "
            "WHERE id = $1 AND user_id = $2", doc_id, user_id)
    if not row:
        raise _not_found(ERR_DOC_NOT_FOUND)
    return _file_response(row["storage_path"], row["mime"], row["original_name"])


@router.get("/admin/team", dependencies=[Depends(require_admin)])
async def admin_team():
    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, email, full_name FROM users WHERE LOWER(role) = 'admin' "
            "ORDER BY email")
    return {"admins": [{"user_id": _ser(r["user_id"]), "email": r["email"],
                        "full_name": r["full_name"]} for r in rows]}
