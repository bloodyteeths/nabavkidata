"""
Middleware package for nabavkidata.com backend
"""
from .rbac import (
    UserRole,
    get_current_user,
    get_current_active_user,
    require_role,
    require_admin,
    RoleChecker,
    create_access_token,
    decode_token,
    get_optional_user,
)

from .entitlements import (
    EntitlementChecker,
    require_module,
    check_usage_limit,
    get_usage_count,
    get_remaining_quota,
    check_trial_credit,
    require_analytics,
    require_risk_analysis,
    require_competitor_tracking,
    require_api_access,
    require_export_pdf,
    require_paid_plan,
)

__all__ = [
    # RBAC
    "UserRole",
    "get_current_user",
    "get_current_active_user",
    "require_role",
    "require_admin",
    "RoleChecker",
    "create_access_token",
    "decode_token",
    "get_optional_user",
    # Entitlements
    "EntitlementChecker",
    "require_module",
    "check_usage_limit",
    "get_usage_count",
    "get_remaining_quota",
    "check_trial_credit",
    "require_analytics",
    "require_risk_analysis",
    "require_competitor_tracking",
    "require_api_access",
    "require_export_pdf",
    "require_paid_plan",
]
