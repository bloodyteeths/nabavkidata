"""
Plan Configuration - Single source of truth for all subscription tiers
NabavkiData Macedonian Tender Intelligence Platform

Pricing:
- Start: 1,990 MKD / €39 per month
- Pro: 5,990 MKD / €99 per month
- Team: 12,990 MKD / €199 per month
- Enterprise: Custom pricing

Payment Methods:
- MKD: Card only
- EUR: Card + SEPA Direct Debit
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import os


class PlanTier(str, Enum):
    """Subscription tier identifiers"""
    FREE = "free"
    TRIAL = "trial"  # 7-day Pro trial with credits
    START = "start"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class ModuleName(str, Enum):
    """Feature module identifiers for access control"""
    BASIC_SEARCH = "basic_search"
    ADVANCED_FILTERS = "advanced_filters"
    RAG_SEARCH = "rag_search"
    DOCUMENT_EXTRACTION = "document_extraction"
    EXPORT_CSV = "export_csv"
    EXPORT_PDF = "export_pdf"
    ANALYTICS = "analytics"
    RISK_ANALYSIS = "risk_analysis"
    COMPETITOR_TRACKING = "competitor_tracking"
    ALERTS = "alerts"
    API_ACCESS = "api_access"
    PRIORITY_SUPPORT = "priority_support"
    TEAM_MANAGEMENT = "team_management"
    CUSTOM_INTEGRATIONS = "custom_integrations"
    DEDICATED_SUPPORT = "dedicated_support"


class AccessLevel(str, Enum):
    """Access level for modules"""
    NONE = "none"
    LIMITED = "limited"
    FULL = "full"
    UNLIMITED = "unlimited"


@dataclass
class UsageLimit:
    """Usage limit configuration"""
    daily: Optional[int] = None  # None = unlimited
    monthly: Optional[int] = None

    def is_unlimited(self) -> bool:
        return self.daily is None and self.monthly is None


@dataclass
class TrialCredits:
    """Trial credit allocation (7-day Pro trial)"""
    ai_messages: int = 50
    document_extractions: int = 15
    exports: int = 5
    competitor_alerts: int = 20


@dataclass
class PlanPricing:
    """Pricing configuration for a plan"""
    mkd_monthly: int  # Macedonian Denar
    eur_monthly: int  # Euro (whole cents for Stripe)
    mkd_yearly: Optional[int] = None  # 2 months free
    eur_yearly: Optional[int] = None

    def __post_init__(self):
        # Default yearly to 10 months price if not specified
        if self.mkd_yearly is None:
            self.mkd_yearly = self.mkd_monthly * 10
        if self.eur_yearly is None:
            self.eur_yearly = self.eur_monthly * 10


@dataclass
class PlanDefinition:
    """Complete plan definition"""
    tier: PlanTier
    name: str
    name_mk: str  # Macedonian name
    description: str
    description_mk: str
    pricing: PlanPricing
    modules: Dict[ModuleName, AccessLevel]
    limits: Dict[str, UsageLimit]
    features: List[str]
    features_mk: List[str]
    badge: Optional[str] = None
    badge_mk: Optional[str] = None
    is_popular: bool = False
    trial_days: int = 0


# ==============================================================================
# PLAN DEFINITIONS
# ==============================================================================

FREE_PLAN = PlanDefinition(
    tier=PlanTier.FREE,
    name="Free",
    name_mk="Бесплатен",
    description="Basic access to tender search",
    description_mk="Основен пристап до пребарување на тендери",
    pricing=PlanPricing(mkd_monthly=0, eur_monthly=0),
    modules={
        ModuleName.BASIC_SEARCH: AccessLevel.FULL,
        ModuleName.ADVANCED_FILTERS: AccessLevel.LIMITED,
        ModuleName.RAG_SEARCH: AccessLevel.LIMITED,
        ModuleName.DOCUMENT_EXTRACTION: AccessLevel.NONE,
        ModuleName.EXPORT_CSV: AccessLevel.NONE,
        ModuleName.EXPORT_PDF: AccessLevel.NONE,
        ModuleName.ANALYTICS: AccessLevel.NONE,
        ModuleName.RISK_ANALYSIS: AccessLevel.NONE,
        ModuleName.COMPETITOR_TRACKING: AccessLevel.NONE,
        ModuleName.ALERTS: AccessLevel.LIMITED,
        ModuleName.API_ACCESS: AccessLevel.NONE,
    },
    limits={
        "rag_queries": UsageLimit(daily=3, monthly=None),
        "alerts": UsageLimit(daily=None, monthly=1),
        "exports": UsageLimit(daily=0, monthly=0),
        "document_views": UsageLimit(daily=10, monthly=None),
    },
    features=[
        "Basic tender search",
        "3 AI queries per day",
        "1 saved alert",
        "Email support",
    ],
    features_mk=[
        "Основно пребарување на тендери",
        "3 AI прашања дневно",
        "1 зачувано известување",
        "Поддршка преку е-пошта",
    ],
)

TRIAL_PLAN = PlanDefinition(
    tier=PlanTier.TRIAL,
    name="Pro Trial",
    name_mk="Pro Проба",
    description="7-day Pro trial with credits",
    description_mk="7-дневна Pro проба со кредити",
    pricing=PlanPricing(mkd_monthly=0, eur_monthly=0),
    modules={
        ModuleName.BASIC_SEARCH: AccessLevel.FULL,
        ModuleName.ADVANCED_FILTERS: AccessLevel.FULL,
        ModuleName.RAG_SEARCH: AccessLevel.FULL,
        ModuleName.DOCUMENT_EXTRACTION: AccessLevel.FULL,
        ModuleName.EXPORT_CSV: AccessLevel.FULL,
        ModuleName.EXPORT_PDF: AccessLevel.FULL,
        ModuleName.ANALYTICS: AccessLevel.FULL,
        ModuleName.RISK_ANALYSIS: AccessLevel.FULL,
        ModuleName.COMPETITOR_TRACKING: AccessLevel.FULL,
        ModuleName.ALERTS: AccessLevel.FULL,
        ModuleName.API_ACCESS: AccessLevel.NONE,
    },
    limits={
        "rag_queries": UsageLimit(daily=None, monthly=50),  # Credit-based
        "alerts": UsageLimit(daily=None, monthly=20),
        "exports": UsageLimit(daily=None, monthly=5),
        "document_extractions": UsageLimit(daily=None, monthly=15),
    },
    features=[
        "All Pro features for 7 days",
        "50 AI message credits",
        "15 document extraction credits",
        "5 export credits",
        "20 competitor alert credits",
    ],
    features_mk=[
        "Сите Pro функции за 7 дена",
        "50 кредити за AI пораки",
        "15 кредити за екстракција на документи",
        "5 кредити за извоз",
        "20 кредити за известувања за конкуренти",
    ],
    trial_days=7,
    badge="Trial",
    badge_mk="Проба",
)

START_PLAN = PlanDefinition(
    tier=PlanTier.START,
    name="Start",
    name_mk="Стартуј",
    description="For freelancers and small businesses",
    description_mk="За фриленсери и мали бизниси",
    pricing=PlanPricing(
        mkd_monthly=1990,
        eur_monthly=39,
        mkd_yearly=19900,  # ~2 months free
        eur_yearly=390,
    ),
    modules={
        ModuleName.BASIC_SEARCH: AccessLevel.FULL,
        ModuleName.ADVANCED_FILTERS: AccessLevel.FULL,
        ModuleName.RAG_SEARCH: AccessLevel.FULL,
        ModuleName.DOCUMENT_EXTRACTION: AccessLevel.LIMITED,
        ModuleName.EXPORT_CSV: AccessLevel.FULL,
        ModuleName.EXPORT_PDF: AccessLevel.NONE,
        ModuleName.ANALYTICS: AccessLevel.LIMITED,
        ModuleName.RISK_ANALYSIS: AccessLevel.NONE,
        ModuleName.COMPETITOR_TRACKING: AccessLevel.LIMITED,
        ModuleName.ALERTS: AccessLevel.FULL,
        ModuleName.API_ACCESS: AccessLevel.NONE,
    },
    limits={
        "rag_queries": UsageLimit(daily=15, monthly=None),
        "alerts": UsageLimit(daily=None, monthly=10),
        "exports": UsageLimit(daily=5, monthly=None),
        "document_extractions": UsageLimit(daily=5, monthly=None),
        "competitor_alerts": UsageLimit(daily=None, monthly=5),
    },
    features=[
        "15 AI queries per day",
        "10 saved alerts",
        "CSV export",
        "Basic analytics",
        "5 competitor alerts",
        "Email support",
    ],
    features_mk=[
        "15 AI прашања дневно",
        "10 зачувани известувања",
        "CSV извоз",
        "Основна аналитика",
        "5 известувања за конкуренти",
        "Поддршка преку е-пошта",
    ],
)

PRO_PLAN = PlanDefinition(
    tier=PlanTier.PRO,
    name="Pro",
    name_mk="Про",
    description="For growing companies",
    description_mk="За растечки компании",
    pricing=PlanPricing(
        mkd_monthly=5990,
        eur_monthly=99,
        mkd_yearly=59900,
        eur_yearly=990,
    ),
    modules={
        ModuleName.BASIC_SEARCH: AccessLevel.FULL,
        ModuleName.ADVANCED_FILTERS: AccessLevel.FULL,
        ModuleName.RAG_SEARCH: AccessLevel.FULL,
        ModuleName.DOCUMENT_EXTRACTION: AccessLevel.FULL,
        ModuleName.EXPORT_CSV: AccessLevel.FULL,
        ModuleName.EXPORT_PDF: AccessLevel.FULL,
        ModuleName.ANALYTICS: AccessLevel.FULL,
        ModuleName.RISK_ANALYSIS: AccessLevel.FULL,
        ModuleName.COMPETITOR_TRACKING: AccessLevel.FULL,
        ModuleName.ALERTS: AccessLevel.FULL,
        ModuleName.API_ACCESS: AccessLevel.NONE,
    },
    limits={
        "rag_queries": UsageLimit(daily=50, monthly=None),
        "alerts": UsageLimit(daily=None, monthly=50),
        "exports": UsageLimit(daily=20, monthly=None),
        "document_extractions": UsageLimit(daily=20, monthly=None),
        "competitor_alerts": UsageLimit(daily=None, monthly=20),
    },
    features=[
        "50 AI queries per day",
        "50 saved alerts",
        "CSV & PDF export",
        "Full analytics",
        "Risk analysis",
        "20 competitor alerts",
        "Priority support",
    ],
    features_mk=[
        "50 AI прашања дневно",
        "50 зачувани известувања",
        "CSV и PDF извоз",
        "Целосна аналитика",
        "Анализа на ризик",
        "20 известувања за конкуренти",
        "Приоритетна поддршка",
    ],
    is_popular=True,
    badge="Most Popular",
    badge_mk="Најпопуларен",
)

TEAM_PLAN = PlanDefinition(
    tier=PlanTier.TEAM,
    name="Team",
    name_mk="Тим",
    description="For teams and departments",
    description_mk="За тимови и одделенија",
    pricing=PlanPricing(
        mkd_monthly=12990,
        eur_monthly=199,
        mkd_yearly=129900,
        eur_yearly=1990,
    ),
    modules={
        ModuleName.BASIC_SEARCH: AccessLevel.FULL,
        ModuleName.ADVANCED_FILTERS: AccessLevel.FULL,
        ModuleName.RAG_SEARCH: AccessLevel.UNLIMITED,
        ModuleName.DOCUMENT_EXTRACTION: AccessLevel.UNLIMITED,
        ModuleName.EXPORT_CSV: AccessLevel.UNLIMITED,
        ModuleName.EXPORT_PDF: AccessLevel.UNLIMITED,
        ModuleName.ANALYTICS: AccessLevel.FULL,
        ModuleName.RISK_ANALYSIS: AccessLevel.FULL,
        ModuleName.COMPETITOR_TRACKING: AccessLevel.FULL,
        ModuleName.ALERTS: AccessLevel.UNLIMITED,
        ModuleName.API_ACCESS: AccessLevel.LIMITED,
        ModuleName.TEAM_MANAGEMENT: AccessLevel.FULL,
    },
    limits={
        "rag_queries": UsageLimit(daily=None, monthly=None),  # Unlimited
        "alerts": UsageLimit(daily=None, monthly=None),
        "exports": UsageLimit(daily=None, monthly=None),
        "document_extractions": UsageLimit(daily=None, monthly=None),
        "competitor_alerts": UsageLimit(daily=None, monthly=None),
        "team_members": UsageLimit(daily=None, monthly=5),  # Up to 5 team members
        "api_calls": UsageLimit(daily=100, monthly=None),
    },
    features=[
        "Unlimited AI queries",
        "Unlimited alerts",
        "Unlimited exports",
        "Full analytics & risk analysis",
        "Up to 5 team members",
        "Basic API access (100 calls/day)",
        "Priority support",
    ],
    features_mk=[
        "Неограничени AI прашања",
        "Неограничени известувања",
        "Неограничен извоз",
        "Целосна аналитика и анализа на ризик",
        "До 5 членови на тим",
        "Основен API пристап (100 повици/ден)",
        "Приоритетна поддршка",
    ],
)

ENTERPRISE_PLAN = PlanDefinition(
    tier=PlanTier.ENTERPRISE,
    name="Enterprise",
    name_mk="Претпријатие",
    description="Custom solution for large organizations",
    description_mk="Прилагодено решение за големи организации",
    pricing=PlanPricing(mkd_monthly=0, eur_monthly=0),  # Custom pricing
    modules={
        ModuleName.BASIC_SEARCH: AccessLevel.UNLIMITED,
        ModuleName.ADVANCED_FILTERS: AccessLevel.UNLIMITED,
        ModuleName.RAG_SEARCH: AccessLevel.UNLIMITED,
        ModuleName.DOCUMENT_EXTRACTION: AccessLevel.UNLIMITED,
        ModuleName.EXPORT_CSV: AccessLevel.UNLIMITED,
        ModuleName.EXPORT_PDF: AccessLevel.UNLIMITED,
        ModuleName.ANALYTICS: AccessLevel.UNLIMITED,
        ModuleName.RISK_ANALYSIS: AccessLevel.UNLIMITED,
        ModuleName.COMPETITOR_TRACKING: AccessLevel.UNLIMITED,
        ModuleName.ALERTS: AccessLevel.UNLIMITED,
        ModuleName.API_ACCESS: AccessLevel.UNLIMITED,
        ModuleName.TEAM_MANAGEMENT: AccessLevel.UNLIMITED,
        ModuleName.CUSTOM_INTEGRATIONS: AccessLevel.FULL,
        ModuleName.DEDICATED_SUPPORT: AccessLevel.FULL,
    },
    limits={},  # No limits
    features=[
        "Everything in Team",
        "Unlimited team members",
        "Unlimited API access",
        "Custom integrations",
        "Dedicated account manager",
        "SLA guarantee",
        "On-premise option",
    ],
    features_mk=[
        "Се од Team пакетот",
        "Неограничен број членови на тим",
        "Неограничен API пристап",
        "Прилагодени интеграции",
        "Посветен менаџер на сметка",
        "SLA гаранција",
        "Опција за on-premise",
    ],
    badge="Contact Us",
    badge_mk="Контактирајте не",
)


# ==============================================================================
# PLAN REGISTRY
# ==============================================================================

PLANS: Dict[PlanTier, PlanDefinition] = {
    PlanTier.FREE: FREE_PLAN,
    PlanTier.TRIAL: TRIAL_PLAN,
    PlanTier.START: START_PLAN,
    PlanTier.PRO: PRO_PLAN,
    PlanTier.TEAM: TEAM_PLAN,
    PlanTier.ENTERPRISE: ENTERPRISE_PLAN,
}

# String-based lookup for compatibility
PLANS_BY_NAME: Dict[str, PlanDefinition] = {
    tier.value: plan for tier, plan in PLANS.items()
}

# Trial configuration
TRIAL_DAYS = 7
TRIAL_CREDITS = TrialCredits(
    ai_messages=50,
    document_extractions=15,
    exports=5,
    competitor_alerts=20,
)


# ==============================================================================
# STRIPE PRICE IDS (from environment)
# ==============================================================================

def get_stripe_price_ids() -> Dict[str, Dict[str, Dict[str, Optional[str]]]]:
    """
    Get Stripe price IDs from environment variables.

    Structure: {currency: {tier: {interval: price_id}}}

    Environment variables format:
    - STRIPE_MKD_START_MONTHLY=price_xxx
    - STRIPE_EUR_PRO_YEARLY=price_yyy
    """
    currencies = ["mkd", "eur"]
    tiers = ["start", "pro", "team"]
    intervals = ["monthly", "yearly"]

    price_ids: Dict[str, Dict[str, Dict[str, Optional[str]]]] = {}

    for currency in currencies:
        price_ids[currency] = {}
        for tier in tiers:
            price_ids[currency][tier] = {}
            for interval in intervals:
                env_key = f"STRIPE_{currency.upper()}_{tier.upper()}_{interval.upper()}"
                price_ids[currency][tier][interval] = os.getenv(env_key)

    return price_ids


STRIPE_PRICE_IDS = get_stripe_price_ids()


def get_price_id(tier: str, currency: str = "mkd", interval: str = "monthly") -> Optional[str]:
    """Get Stripe price ID for a plan"""
    currency_lower = currency.lower()
    tier_lower = tier.lower()
    interval_lower = interval.lower()

    return STRIPE_PRICE_IDS.get(currency_lower, {}).get(tier_lower, {}).get(interval_lower)


def get_payment_methods(currency: str) -> List[str]:
    """Get allowed payment methods for a currency"""
    if currency.lower() == "mkd":
        return ["card"]
    elif currency.lower() == "eur":
        return ["card", "sepa_debit"]
    return ["card"]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_plan(tier: str) -> Optional[PlanDefinition]:
    """Get plan definition by tier name"""
    try:
        plan_tier = PlanTier(tier.lower())
        return PLANS.get(plan_tier)
    except ValueError:
        return PLANS_BY_NAME.get(tier.lower())


def get_plan_limits(tier: str) -> Dict[str, UsageLimit]:
    """Get usage limits for a plan tier"""
    plan = get_plan(tier)
    return plan.limits if plan else {}


def get_plan_modules(tier: str) -> Dict[ModuleName, AccessLevel]:
    """Get module access for a plan tier"""
    plan = get_plan(tier)
    return plan.modules if plan else {}


def has_module_access(tier: str, module: ModuleName) -> bool:
    """Check if tier has access to a module"""
    plan = get_plan(tier)
    if not plan:
        return False
    access = plan.modules.get(module, AccessLevel.NONE)
    return access != AccessLevel.NONE


def get_module_access_level(tier: str, module: ModuleName) -> AccessLevel:
    """Get access level for a module in a tier"""
    plan = get_plan(tier)
    if not plan:
        return AccessLevel.NONE
    return plan.modules.get(module, AccessLevel.NONE)


def get_daily_limit(tier: str, limit_type: str) -> Optional[int]:
    """Get daily limit for a specific limit type"""
    limits = get_plan_limits(tier)
    limit = limits.get(limit_type)
    return limit.daily if limit else None


def get_monthly_limit(tier: str, limit_type: str) -> Optional[int]:
    """Get monthly limit for a specific limit type"""
    limits = get_plan_limits(tier)
    limit = limits.get(limit_type)
    return limit.monthly if limit else None


def is_unlimited(tier: str, limit_type: str) -> bool:
    """Check if a limit type is unlimited for a tier"""
    limits = get_plan_limits(tier)
    limit = limits.get(limit_type)
    return limit.is_unlimited() if limit else False


def get_pricing_display(tier: str, currency: str = "mkd") -> str:
    """Get formatted pricing string for display"""
    plan = get_plan(tier)
    if not plan or tier == "enterprise":
        return "Контактирајте не" if currency == "mkd" else "Contact us"

    pricing = plan.pricing
    if currency.lower() == "mkd":
        return f"{pricing.mkd_monthly:,} МКД/месец"
    else:
        return f"€{pricing.eur_monthly}/month"


def get_all_paid_plans() -> List[PlanDefinition]:
    """Get all paid plan definitions (for pricing page)"""
    return [START_PLAN, PRO_PLAN, TEAM_PLAN, ENTERPRISE_PLAN]


def can_upgrade_to(current_tier: str, target_tier: str) -> bool:
    """Check if upgrade from current tier to target is valid"""
    tier_order = ["free", "trial", "start", "pro", "team", "enterprise"]
    try:
        current_idx = tier_order.index(current_tier.lower())
        target_idx = tier_order.index(target_tier.lower())
        return target_idx > current_idx
    except ValueError:
        return False
