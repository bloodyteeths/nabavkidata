"""
40 Edge Case Tests - Real User Queries for Winning Tenders
Tests what actual users would ask to win tenders and find opportunities.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '../..'))

os.environ.setdefault('DATABASE_URL', os.getenv('DATABASE_URL'))

from db_pool import get_pool
from rag_query import execute_tool

# 40 Real User Queries
USER_QUERIES = [
    # PRICES (10 queries)
    {"id": 1, "q": "Колку чини лаптоп HP EliteBook?", "tools": [("search_product_items", {"keywords": ["лаптоп", "HP", "EliteBook"]})]},
    {"id": 2, "q": "Просечна цена на хартија А4?", "tools": [("get_price_statistics", {"keywords": ["хартија А4"], "stat_type": "all"})]},
    {"id": 3, "q": "Историски цени за инсулин?", "tools": [("search_product_items", {"keywords": ["инсулин"]})]},
    {"id": 4, "q": "Цена на тонер за Canon принтер?", "tools": [("search_product_items", {"keywords": ["тонер", "Canon"]})]},
    {"id": 5, "q": "Колку чинат хируршки ракавици?", "tools": [("search_product_items", {"keywords": ["хируршки ракавици"]})]},
    {"id": 6, "q": "Најниска понуда за гориво дизел?", "tools": [("get_price_statistics", {"keywords": ["дизел", "гориво"], "stat_type": "min"})]},
    {"id": 7, "q": "Price range за канцелариски столици?", "tools": [("get_price_statistics", {"keywords": ["канцелариски столици"], "stat_type": "range"})]},
    {"id": 8, "q": "Што да понудам за антибиотици?", "tools": [("get_recommendations", {"context_type": "pricing", "keywords": ["антибиотици"]})]},
    {"id": 9, "q": "Цени на медицински маски по години?", "tools": [("get_price_statistics", {"keywords": ["маски", "медицински"], "group_by": "year"})]},
    {"id": 10, "q": "Споредба на цени за компјутери 2023 vs 2024?", "tools": [("search_product_items", {"keywords": ["компјутер"]})]},

    # SPECIFICATIONS (5 queries)
    {"id": 11, "q": "Технички спецификации за сервер?", "tools": [("search_bid_documents", {"keywords": ["сервер", "спецификации"]})]},
    {"id": 12, "q": "Барања за медицинска опрема ултразвук?", "tools": [("search_bid_documents", {"keywords": ["ултразвук", "спецификации"]})]},
    {"id": 13, "q": "Квалитет стандарди за храна во болници?", "tools": [("search_bid_documents", {"keywords": ["храна", "болница", "стандарди"]})]},
    {"id": 14, "q": "Минимални барања за возила?", "tools": [("search_bid_documents", {"keywords": ["возила", "барања", "спецификации"]})]},
    {"id": 15, "q": "ISO сертификати потребни за IT тендери?", "tools": [("search_bid_documents", {"keywords": ["ISO", "сертификат", "IT"]})]},

    # CLOSING DATES (5 queries)
    {"id": 16, "q": "Тендери со рок оваа недела?", "tools": [("get_top_tenders", {"sort_by": "date_desc", "limit": 20})]},
    {"id": 17, "q": "Активни тендери со рок во јануари 2025?", "tools": [("search_tenders", {"keywords": ["тендер"]})]},
    {"id": 18, "q": "Кои тендери завршуваат наскоро?", "tools": [("get_top_tenders", {"sort_by": "date_desc", "status": "active", "limit": 10})]},
    {"id": 19, "q": "Најнови објавени тендери денес?", "tools": [("get_top_tenders", {"sort_by": "date_desc", "limit": 10})]},
    {"id": 20, "q": "Скорешни тендери за медицинска опрема?", "tools": [("search_tenders", {"keywords": ["медицинска опрема"]})]},

    # COMPETITION ANALYSIS (5 queries)
    {"id": 21, "q": "Кој е главен конкурент на Алкалоид?", "tools": [("analyze_competitors", {"company_name": "Алкалоид", "analysis_type": "head_to_head"})]},
    {"id": 22, "q": "Кои компании најчесто победуваат во IT?", "tools": [("analyze_competitors", {"cpv_code": "72000000", "analysis_type": "top_competitors"})]},
    {"id": 23, "q": "Win rate на Макпетрол?", "tools": [("analyze_competitors", {"company_name": "Макпетрол", "analysis_type": "win_rate"})]},
    {"id": 24, "q": "Кои фирми се натпреваруваат заедно?", "tools": [("analyze_competitors", {"analysis_type": "co_bidding"})]},
    {"id": 25, "q": "Market share за фармацевтски сектор?", "tools": [("analyze_competitors", {"cpv_code": "33600000", "analysis_type": "market_share"})]},

    # INSTITUTIONS (5 queries)
    {"id": 26, "q": "Кажи ми за Министерство за здравство?", "tools": [("get_entity_profile", {"entity_name": "Министерство за здравство"})]},
    {"id": 27, "q": "Колку троши Општина Скопје?", "tools": [("get_entity_profile", {"entity_name": "Скопје"})]},
    {"id": 28, "q": "Профил на ЈЗУ Градска болница?", "tools": [("get_entity_profile", {"entity_name": "Градска болница"})]},
    {"id": 29, "q": "Која институција троши најмногу?", "tools": [("get_statistics", {"stat_type": "institution_spending", "limit": 5})]},
    {"id": 30, "q": "Историја на набавки на МВР?", "tools": [("get_entity_profile", {"entity_name": "МВР"})]},

    # STATISTICS (5 queries)
    {"id": 31, "q": "Која институција објавува најмногу тендери?", "tools": [("get_statistics", {"stat_type": "top_institutions", "limit": 10})]},
    {"id": 32, "q": "Кој победува најчесто?", "tools": [("get_statistics", {"stat_type": "top_winners", "limit": 10})]},
    {"id": 33, "q": "Тендери по години?", "tools": [("get_statistics", {"stat_type": "by_year"})]},
    {"id": 34, "q": "Преглед на пазарот?", "tools": [("get_statistics", {"stat_type": "market_overview"})]},
    {"id": 35, "q": "Топ категории по CPV код?", "tools": [("get_statistics", {"stat_type": "by_category", "limit": 10})]},

    # OPPORTUNITIES (5 queries)
    {"id": 36, "q": "Најголеми тендери во 2024?", "tools": [("get_top_tenders", {"sort_by": "value_desc", "year": 2024, "limit": 10})]},
    {"id": 37, "q": "Тендери за лекови над 10 милиони?", "tools": [("get_top_tenders", {"sort_by": "value_desc", "min_value": 10000000, "limit": 10})]},
    {"id": 38, "q": "Набавки на болници?", "tools": [("get_top_tenders", {"institution_type": "болница", "limit": 10})]},
    {"id": 39, "q": "Тендери на општини оваа година?", "tools": [("get_top_tenders", {"institution_type": "општина", "year": 2025, "limit": 10})]},
    {"id": 40, "q": "Рамковни договори за IT услуги?", "tools": [("search_bid_documents", {"keywords": ["рамковен договор", "IT"]})]},
]

BAD_PATTERNS = [
    # These patterns mean we're telling user to go elsewhere instead of helping
    "препорачувам да отидете на e-nabavki",
    "посетете e-nabavki",
    "проверете на веб",
    "отидете на",
    "не можам да ви помогнам",
    # Generic cop-outs (but NOT "немам податоци" which can be followed by web search results)
]

async def test_tool(conn, tool_name: str, tool_args: dict) -> tuple:
    """Test a single tool call"""
    try:
        result = await execute_tool(tool_name, tool_args, conn)
        # "Не најдов" alone means failure, but "Не најдов во базата, но пронајдов онлајн" means success
        is_fallback_success = "но пронајдов онлајн" in result if result else False
        is_only_not_found = "Не најдов" in result and not is_fallback_success if result else False
        has_data = result and len(result) > 50 and not is_only_not_found
        has_bad = any(p.lower() in result.lower() for p in BAD_PATTERNS) if result else False
        return result, has_data, has_bad
    except Exception as e:
        return str(e), False, False

async def main():
    print("=" * 70)
    print("40 REAL USER QUERY TESTS")
    print("=" * 70)

    pool = await get_pool()
    results = []

    async with pool.acquire() as conn:
        for test in USER_QUERIES:
            print(f"\n[{test['id']:2d}/40] {test['q'][:50]}...")

            for tool_name, tool_args in test['tools']:
                result, has_data, has_bad = await test_tool(conn, tool_name, tool_args)

                status = "✅ DATA" if has_data else "⚠️ EMPTY"
                if has_bad:
                    status = "❌ BAD PATTERN"

                print(f"       {tool_name}: {status} ({len(result) if result else 0} chars)")

                results.append({
                    "id": test['id'],
                    "query": test['q'],
                    "tool": tool_name,
                    "has_data": has_data,
                    "has_bad": has_bad,
                    "length": len(result) if result else 0
                })

                if has_bad and result:
                    for p in BAD_PATTERNS:
                        if p.lower() in result.lower():
                            print(f"       ⚠️ Found: '{p}'")

    await pool.close()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    with_data = sum(1 for r in results if r['has_data'])
    with_bad = sum(1 for r in results if r['has_bad'])
    empty = sum(1 for r in results if not r['has_data'] and not r['has_bad'])

    print(f"✅ With Data: {with_data}/{len(results)}")
    print(f"⚠️ Empty: {empty}/{len(results)}")
    print(f"❌ Bad Patterns: {with_bad}/{len(results)}")

    if empty > 0:
        print("\n--- EMPTY RESULTS ---")
        for r in results:
            if not r['has_data'] and not r['has_bad']:
                print(f"  [{r['id']}] {r['query'][:40]}... ({r['tool']})")

    if with_bad > 0:
        print("\n--- BAD PATTERNS ---")
        for r in results:
            if r['has_bad']:
                print(f"  [{r['id']}] {r['query'][:40]}... ({r['tool']})")

if __name__ == "__main__":
    asyncio.run(main())
