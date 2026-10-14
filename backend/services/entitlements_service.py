"""
Client perks: the single predicate for every paid feature (14 Oct 2026).

NabavkiData is a done-for-you bid service. Perks (alert/digest emails, AI chat
and RAG, AI summaries and bid advice, price intelligence, analytics, exports,
saved-search notifications) belong only to clients we write a bid for:
users.account_type = 'managed_client' (paid a prep fee, or admin free drafting)
and admins. Free users and prospects keep public browsing/search, the /usluga
assessment, the portal matched-tenders list and messaging us.

Pure module: no FastAPI or api.* imports, so crons, middleware and API modules
can all import it without cycles.
"""
from __future__ import annotations

from typing import Any

CLIENT_ACCOUNT_TYPE = "managed_client"
PERK_TIER = "enterprise"
NO_PERK_TIER = "free"


def _field(user: Any, key: str) -> Any:
    """Read a field from an ORM object, a dict or an asyncpg Record."""
    if user is None:
        return None
    if isinstance(user, dict):
        return user.get(key)
    try:
        val = getattr(user, key)
    except AttributeError:
        val = None
    else:
        if not callable(val):
            return val
    try:
        return user[key]
    except (KeyError, IndexError, TypeError):
        return None


def has_client_perks(user: Any) -> bool:
    """True for managed clients and admins; False for anyone else (incl. None)."""
    if user is None:
        return False
    if (_field(user, "account_type") or "") == CLIENT_ACCOUNT_TYPE:
        return True
    return str(_field(user, "role") or "").lower() == "admin"


def effective_tier(user: Any) -> str:
    """Plan tier used by every config/plans.py lookup."""
    return PERK_TIER if has_client_perks(user) else NO_PERK_TIER


def client_perks_sql(alias: str = "u") -> str:
    """SQL boolean expression equivalent to has_client_perks for a users alias."""
    return (f"({alias}.account_type = '{CLIENT_ACCOUNT_TYPE}' "
            f"OR LOWER(COALESCE({alias}.role, '')) = 'admin')")


def client_perks_clause(User):
    """SQLAlchemy equivalent of has_client_perks for the ORM User model."""
    from sqlalchemy import func, or_

    return or_(
        User.account_type == CLIENT_ACCOUNT_TYPE,
        func.lower(func.coalesce(User.role, "")) == "admin",
    )


def perks_required_detail(feature: str = "premium") -> dict:
    """403 detail; error=upgrade_required makes lib/api.ts open the PaywallModal."""
    return {
        "error": "upgrade_required",
        "code": "client_perks_required",
        "feature": feature,
        "message": "Оваа можност е вклучена за клиентите за кои подготвуваме понуди.",
    }
