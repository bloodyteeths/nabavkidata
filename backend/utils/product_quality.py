"""
Product items quality filters — canonical source of truth.

Two-tier filtering for product_items queries:
- strict: For price calculations, AI recommendations (exclude legal clauses)
- moderate: For display/search (exclude obvious garbage)

If you need these filters in ai/rag_query.py or ai/agents/,
use the local copy _product_quality_filter() defined there.
"""


def product_quality_filter(alias: str = "pi", level: str = "moderate") -> str:
    """
    Return SQL WHERE clause fragment for product_items quality filtering.

    Args:
        alias: Table alias for product_items (e.g. "pi", "p", or "" for no alias)
        level: "strict" or "moderate"

    Returns:
        SQL string to append to WHERE clause (starts with AND)
    """
    col = f"{alias}." if alias else ""

    moderate = f"""
            AND {col}extraction_confidence >= 0.5
            AND LENGTH({col}name) BETWEEN 5 AND 200
            AND {col}name !~ '^[0-9]+\\.'"""

    if level == "moderate":
        return moderate

    # strict — adds lettered-item exclusion, ALL-CAPS heading exclusion,
    # and 21 Macedonian legal/admin clause patterns
    strict_extra = f"""
            AND {col}name !~ '^[а-яА-Яa-zA-Z]\\)'
            AND {col}name !~ '^[А-Ш\\s]{{10,}}$'
            AND UPPER({col}name) NOT LIKE '%ПОДНЕСУВАЊЕ%ПОНУДИ%'
            AND UPPER({col}name) NOT LIKE '%ЕВАЛУАЦИЈА%'
            AND UPPER({col}name) NOT LIKE '%КРИТЕРИУМ%ИЗБОР%'
            AND UPPER({col}name) NOT LIKE '%СКЛУЧУВАЊЕ%ДОГОВОР%'
            AND UPPER({col}name) NOT LIKE '%ПРАВО НА ЖАЛБА%'
            AND UPPER({col}name) NOT LIKE '%ЗАДОЛЖИТЕЛНИ ЕЛЕМЕНТИ%'
            AND UPPER({col}name) NOT LIKE '%УТВРДУВАЊЕ СПОСОБНОСТ%'
            AND UPPER({col}name) NOT LIKE '%ПОДГОТОВКА НА ПОНУДАТА%'
            AND UPPER({col}name) NOT LIKE '%ОПШТИ ИНФОРМАЦИИ%'
            AND UPPER({col}name) NOT LIKE '%ПОЈАСНУВАЊЕ%ИЗМЕНУВАЊЕ%'
            AND UPPER({col}name) NOT LIKE '%ТЕНДЕРСКА%ДОКУМЕНТАЦИЈА%'
            AND UPPER({col}name) NOT LIKE '%ДОГОВОРНИОТ ОРГАН%'
            AND UPPER({col}name) NOT LIKE '%ЕКОНОМСКИОТ ОПЕРАТОР%'
            AND UPPER({col}name) NOT LIKE '%ЖАЛИТЕЛОТ%'
            AND UPPER({col}name) NOT LIKE '%НЕУСОГЛАСЕНОСТИ%'
            AND UPPER({col}name) NOT LIKE '%ОБЈАВУВАЊЕ%ОГЛАС%'
            AND UPPER({col}name) NOT LIKE '%ИЗВЕСТУВАЊ%'
            AND UPPER({col}name) NOT LIKE '%ОДЛУКАТА ЗА ИЗБОР%'
            AND UPPER({col}name) NOT LIKE '%ВКУПНИОТ ИЗНОС%'
            AND UPPER({col}name) NOT LIKE '%ВО ОДНОС НА%'
            AND UPPER({col}name) NOT LIKE '%ДОКОЛКУ ИМА%'"""

    return moderate + strict_extra
