"""
Parser for OpenData PowerBI DSR payloads.
Extracts aggregate statistics from cached query responses.

Usage:
    python scraper/scripts/opendata_parser.py          # parses all categories
    python scraper/scripts/opendata_parser.py contracts  # parses specific category
"""

import json
import pathlib
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "opendata_cache"

# Field name translations (Macedonian -> English)
FIELD_TRANSLATIONS = {
    "Категорија на ЕО": "entity_category",
    "вкупно договори": "total_contracts",
    "вкупна вредност на склучени договори": "total_contract_value",
    "Постапка за ЈН": "procedure_type",
    "Вид на договор": "contract_type",
    "Година": "year",
    "Месец": "month",
    "Датум на склучување на договор": "contract_date",
    "вкупно огласи": "total_announcements",
    "вкупна проценета вредност на огласи": "total_estimated_value",
    "Тип на оглас": "announcement_type",
    "вкупно аукции": "total_auctions",
    "вкупно понуди": "total_bids",
    "вкупно откажани": "total_cancelled",
    "Причина за откажување": "cancellation_reason",
    "корисници": "users_count",
    "Тип на корисник": "user_type",
    "Регион": "region",
}


def translate_field(field: str) -> str:
    """Translate Macedonian field name to English."""
    return FIELD_TRANSLATIONS.get(field, field.replace(" ", "_").lower())


def parse_dsr_response(data: Dict) -> List[Dict[str, Any]]:
    """
    Parse PowerBI DSR response and extract rows.
    Returns list of dicts with field->value mappings.
    """
    results = []

    try:
        dsr = data.get("results", [{}])[0].get("result", {}).get("data", {}).get("dsr", {})
        descriptor = data.get("results", [{}])[0].get("result", {}).get("data", {}).get("descriptor", {})

        # Get field names from descriptor
        select_fields = descriptor.get("Select", [])
        field_names = {s.get("Value"): s.get("Name", "").split(".")[-1] for s in select_fields}

        # Parse DS (DataSet) entries
        for ds in dsr.get("DS", []):
            # PH contains the actual data
            for ph in ds.get("PH", []):
                # DM0 usually contains subtotals, DM1 contains detailed rows
                for dm_key in ["DM0", "DM1", "G0", "G1"]:
                    if dm_key in ph:
                        for row in ph[dm_key]:
                            # S contains schema, C contains values
                            schema = row.get("S", [])
                            values = row.get("C", [])

                            # Handle different value formats
                            if isinstance(values, dict):
                                # Single value case
                                row_data = {}
                                for k, v in values.items():
                                    field = field_names.get(k, k)
                                    row_data[translate_field(field)] = v
                                if row_data:
                                    results.append(row_data)
                            elif isinstance(values, list):
                                # Multiple values case
                                row_data = {}
                                for i, val in enumerate(values):
                                    if i < len(schema):
                                        field_key = schema[i].get("N", f"col_{i}")
                                        field = field_names.get(field_key, field_key)
                                    else:
                                        field = f"col_{i}"
                                    row_data[translate_field(field)] = val
                                if row_data:
                                    results.append(row_data)

                            # Also check for direct field mappings
                            for key in ["M0", "M1", "M2", "G0", "G1"]:
                                if key in row and key not in ["S", "C"]:
                                    field = field_names.get(key, key)
                                    results.append({translate_field(field): row[key]})

    except Exception as e:
        print(f"Error parsing DSR: {e}")

    return results


def aggregate_stats(rows: List[Dict], category: str) -> Dict[str, Any]:
    """
    Aggregate parsed rows into meaningful statistics.
    """
    stats = {
        "category": category,
        "total_rows_parsed": len(rows),
        "timestamp": datetime.utcnow().isoformat(),
        "aggregations": {}
    }

    # Collect unique keys and their values
    for row in rows:
        for key, value in row.items():
            if key not in stats["aggregations"]:
                stats["aggregations"][key] = []
            if isinstance(value, (int, float)):
                stats["aggregations"][key].append({"type": "numeric", "value": value})
            elif isinstance(value, str):
                stats["aggregations"][key].append({"type": "string", "value": value})

    return stats


def parse_category(category: str) -> Dict[str, Any]:
    """
    Parse all query files for a category and return aggregated stats.
    """
    cache_dir = CACHE_ROOT / category
    if not cache_dir.exists():
        return {"error": f"Cache directory not found: {cache_dir}"}

    all_rows = []
    query_count = 0

    # Parse all query files
    for query_file in cache_dir.glob("query_*.json"):
        query_count += 1
        try:
            with open(query_file) as f:
                data = json.load(f)
            rows = parse_dsr_response(data)
            all_rows.extend(rows)
        except Exception as e:
            print(f"Error parsing {query_file}: {e}")

    # Also extract totals from specific structures
    totals = extract_totals(cache_dir)

    return {
        "category": category,
        "query_files_parsed": query_count,
        "rows_extracted": len(all_rows),
        "totals": totals,
        "by_category": extract_by_dimension(all_rows, category),
        "raw_rows": all_rows[:50]  # Keep sample for debugging
    }


def extract_totals(cache_dir: pathlib.Path) -> Dict[str, Any]:
    """
    Extract total counts from query files.
    """
    totals = {}

    for query_file in cache_dir.glob("query_*.json"):
        try:
            with open(query_file) as f:
                data = json.load(f)

            # Look for single-value totals
            dsr = data.get("results", [{}])[0].get("result", {}).get("data", {}).get("dsr", {})
            descriptor = data.get("results", [{}])[0].get("result", {}).get("data", {}).get("descriptor", {})

            select_fields = descriptor.get("Select", [])

            for ds in dsr.get("DS", []):
                for ph in ds.get("PH", []):
                    for dm_key in ["DM0"]:
                        if dm_key in ph:
                            for row in ph[dm_key]:
                                # Check for direct field values (like M0: 22975)
                                for key in ["M0", "M1", "M2"]:
                                    if key in row:
                                        # Find the field name
                                        for sf in select_fields:
                                            if sf.get("Value") == key:
                                                name = sf.get("Name", "").split(".")[-1]
                                                totals[translate_field(name)] = row[key]

        except Exception as e:
            continue

    return totals


def extract_by_dimension(rows: List[Dict], category: str) -> Dict[str, List]:
    """
    Group data by common dimensions.
    """
    by_dimension = {}

    # Common dimension fields
    dimension_fields = ["entity_category", "procedure_type", "contract_type",
                       "announcement_type", "user_type", "region", "year", "cancellation_reason"]

    for row in rows:
        for dim in dimension_fields:
            if dim in row:
                if dim not in by_dimension:
                    by_dimension[dim] = []
                # Look for associated numeric values
                numeric_vals = {k: v for k, v in row.items()
                              if isinstance(v, (int, float)) and k != dim}
                by_dimension[dim].append({
                    "label": row[dim],
                    **numeric_vals
                })

    return by_dimension


def save_stats_for_db(category: str, stats: Dict) -> List[Dict]:
    """
    Convert parsed stats into records ready for opendata_stats table.
    """
    records = []
    timestamp = datetime.utcnow()

    # Save totals
    if stats.get("totals"):
        records.append({
            "stat_id": str(uuid.uuid4()),
            "category": category,
            "stat_key": "totals",
            "stat_value": stats["totals"],
            "fetched_at": timestamp.isoformat()
        })

    # Save by-dimension breakdowns
    for dim, values in stats.get("by_category", {}).items():
        if values:
            records.append({
                "stat_id": str(uuid.uuid4()),
                "category": category,
                "stat_key": f"by_{dim}",
                "stat_value": values,
                "fetched_at": timestamp.isoformat()
            })

    return records


def main(args: List[str]) -> None:
    categories = args if args else ["announcements", "contracts", "auctions", "cancellations", "users"]

    all_stats = {}
    all_records = []

    for cat in categories:
        print(f"\n=== Parsing {cat} ===")
        stats = parse_category(cat)
        all_stats[cat] = stats

        print(f"  Query files: {stats.get('query_files_parsed', 0)}")
        print(f"  Rows extracted: {stats.get('rows_extracted', 0)}")
        print(f"  Totals: {stats.get('totals', {})}")

        # Convert to DB records
        records = save_stats_for_db(cat, stats)
        all_records.extend(records)
        print(f"  DB records: {len(records)}")

    # Save combined output
    output_file = CACHE_ROOT / "parsed_stats.json"
    with open(output_file, "w") as f:
        json.dump({
            "parsed_at": datetime.utcnow().isoformat(),
            "categories": all_stats,
            "db_records": all_records
        }, f, indent=2, ensure_ascii=False)

    print(f"\n=== Summary ===")
    print(f"Total DB records: {len(all_records)}")
    print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    main(sys.argv[1:])
