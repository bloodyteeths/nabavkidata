"""
Read-only probe that inspects tables with a `raw_data_json` column and emits
JSON Schema drafts describing what we could store there. It never writes to the
database. Output files go to `devtools/json_schemas/`.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "devtools" / "json_schemas"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_db_url(raw_url: str) -> str:
    """Ensure the URL uses a synchronous PostgreSQL driver for SQLAlchemy."""
    url = make_url(raw_url)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")
    if url.drivername == "postgres":
        url = url.set(drivername="postgresql")
    return str(url)


def infer_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "string"


def merge_properties(props: Dict[str, Dict[str, Any]], sample: Dict[str, Any]) -> None:
    """Accumulate JSON types for each property key from a sample object."""
    for key, value in sample.items():
        detected_type = infer_type(value)
        entry = props.setdefault(key, {"type": set()})
        entry["type"].add(detected_type)


def finalize_properties(props: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert type sets into sorted lists for JSON serialization."""
    finalized: Dict[str, Dict[str, Any]] = {}
    for key, data in props.items():
        types: Iterable[str] = data.get("type", [])
        finalized[key] = {"type": sorted(types)}
    return finalized


def suggested_fields_from_columns(columns: List[Dict[str, Any]], raw_column: str) -> List[Dict[str, str]]:
    """List structured columns that should also be mirrored in raw JSON for auditability."""
    suggestions: List[Dict[str, str]] = []
    for col in columns:
        name = col["column_name"]
        if name == raw_column:
            continue
        if name in {"created_at", "updated_at", "scraped_at"}:
            continue
        suggestions.append(
            {
                "field": name,
                "sql_type": col["data_type"],
                "nullable": col["is_nullable"],
            }
        )
    return suggestions


def fetch_tables_with_raw_json(conn) -> List[Dict[str, str]]:
    result = conn.execute(
        text(
            """
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE column_name = 'raw_data_json'
            ORDER BY table_schema, table_name;
            """
        )
    )
    return [
        {
            "schema": row.table_schema,
            "table": row.table_name,
            "column": row.column_name,
        }
        for row in result
    ]


def fetch_columns(conn, table_schema: str, table_name: str) -> List[Dict[str, str]]:
    result = conn.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position;
            """
        ),
        {"schema": table_schema, "table": table_name},
    )
    return [
        {
            "column_name": row.column_name,
            "data_type": row.data_type,
            "is_nullable": row.is_nullable,
        }
        for row in result
    ]


def load_raw_samples(conn, table_schema: str, table_name: str, column: str, limit: int = 100) -> List[Dict[str, Any]]:
    qualified = f'"{table_schema}"."{table_name}"'
    result = conn.execute(
        text(f"SELECT {column} FROM {qualified} WHERE {column} IS NOT NULL LIMIT :limit"),
        {"limit": limit},
    )
    samples: List[Dict[str, Any]] = []
    for row in result:
        payload = row[0]
        if isinstance(payload, dict):
            samples.append(payload)
    return samples


def build_schema_doc(
    table_schema: str,
    table_name: str,
    column: str,
    samples: List[Dict[str, Any]],
    columns: List[Dict[str, str]],
    db_url: str,
) -> Dict[str, Any]:
    props: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for sample in samples:
        merge_properties(props, sample)

    has_samples = len(samples) > 0
    properties = finalize_properties(props)
    if not properties:
        # No samples present; fall back to structured columns as a baseline of expected fields
        for col in columns:
            name = col["column_name"]
            if name == column:
                continue
            properties[name] = {"type": ["string"]}  # conservative default

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": f"{table_schema}.{table_name}.{column} probe",
        "type": "object",
        "description": "Auto-generated schema guess for future raw JSON capture. Derived from existing samples when available; otherwise uses structured columns as hints.",
        "properties": properties,
        "additionalProperties": True,
        "x_probe_metadata": {
            "table": table_name,
            "schema": table_schema,
            "raw_column": column,
            "sample_count": len(samples),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_url_redacted": make_url(db_url).set(password="***").render_as_string(hide_password=False),
            "fallback_used": not has_samples,
        },
        "x_suggested_fields": suggested_fields_from_columns(columns, column),
    }


def save_schema(table_name: str, column: str, schema_doc: Dict[str, Any]) -> Path:
    filename = OUTPUT_DIR / f"{table_name}_{column}_schema.json"
    filename.write_text(json.dumps(schema_doc, indent=2), encoding="utf-8")
    return filename


def main() -> None:
    raw_url = os.getenv("DATABASE_URL", "postgresql://localhost:5432/nabavkidata")
    db_url = normalize_db_url(raw_url)
    engine = create_engine(db_url, isolation_level="AUTOCOMMIT")

    print(f"[probe] connecting to DB (read-only) via {make_url(db_url).set(password='***')}")

    with engine.connect() as conn:
        conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"))
        tables = fetch_tables_with_raw_json(conn)
        if not tables:
            print("[probe] no raw_data_json columns detected; nothing to do.")
            return

        for entry in tables:
            schema_name = entry["schema"]
            table_name = entry["table"]
            column = entry["column"]
            print(f"[probe] inspecting {schema_name}.{table_name}.{column}")
            columns = fetch_columns(conn, schema_name, table_name)
            samples = load_raw_samples(conn, schema_name, table_name, column)
            schema_doc = build_schema_doc(schema_name, table_name, column, samples, columns, db_url)
            output_path = save_schema(table_name, column, schema_doc)
            print(
                f"[probe] wrote schema for {schema_name}.{table_name}.{column} "
                f"(samples={len(samples)}) -> {output_path}"
            )


if __name__ == "__main__":
    main()
