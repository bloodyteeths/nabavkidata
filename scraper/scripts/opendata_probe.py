"""
Quick probe utility for the e-nabavki OpenData PowerBI embeds.

Finds the PowerBI resource keys, pulls the models/exploration payload,
and replays visual queries against the public querydata endpoint.

Usage:
    python scraper/scripts/opendata_probe.py          # fetches all categories
    python scraper/scripts/opendata_probe.py contracts
    python scraper/scripts/opendata_probe.py announcements contracts

Outputs raw JSON into scraper/opendata_cache/<category>/ for later parsing.
"""

import base64
import json
import pathlib
import re
import sys
from typing import Dict, Iterable, List

import requests


ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_ROOT = ROOT / "opendata_cache"

PAGES = {
    "announcements": "https://e-nabavki.gov.mk/opendata-announcements.aspx",
    "contracts": "https://e-nabavki.gov.mk/opendata-contracts.aspx",
    "auctions": "https://e-nabavki.gov.mk/opendata-auctions.aspx",
    "cancellations": "https://e-nabavki.gov.mk/opendata-cancellations.aspx",
    "users": "https://e-nabavki.gov.mk/opendata-users.aspx",
}

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "nabavkidata-opendata-probe/0.1 (+https://nabavkidata.com)",
        "Accept": "text/html,application/json",
    }
)


def decode_resource_key(embed_url: str) -> str:
    """
    The iframe src has a query param `r` which is a base64-encoded JSON:
    {"k": "<report_id>", "t": "<tenant_id>", "c": <cluster>}
    The report_id doubles as the X-PowerBI-ResourceKey header.
    """
    m = re.search(r"[?&]r=([^&#]+)", embed_url)
    if not m:
        raise ValueError("resource param r= not found in iframe src")
    payload = m.group(1)
    padded = payload + "=" * ((4 - len(payload) % 4) % 4)
    decoded = base64.urlsafe_b64decode(padded).decode()
    data = json.loads(decoded)
    return data["k"]


def find_embed_src(html: str) -> str:
    m = re.search(r'<iframe[^>]+src="([^"]+app.powerbi.com/view[^"]+)"', html, re.IGNORECASE)
    if not m:
        raise ValueError("iframe PowerBI src not found")
    return m.group(1)


def fetch_models(report_id: str) -> Dict:
    url = f"https://wabi-west-europe-f-primary-api.analysis.windows.net/public/reports/{report_id}/modelsAndExploration?preferReadOnlySession=true"
    res = SESSION.get(url, headers={"X-PowerBI-ResourceKey": report_id})
    res.raise_for_status()
    return res.json()


def fetch_visual(report_id: str, body: Dict) -> Dict:
    url = "https://wabi-west-europe-f-primary-api.analysis.windows.net/public/reports/querydata?synchronous=true"
    res = SESSION.post(
        url,
        headers={
            "X-PowerBI-ResourceKey": report_id,
            "Content-Type": "application/json",
        },
        data=json.dumps(body),
    )
    res.raise_for_status()
    return res.json()


def iter_visual_queries(models_payload: Dict, report_id: str) -> Iterable[Dict]:
    """
    Yields tuples of (visual_name, body) to be replayed against querydata.
    We keep only table/card/chart visuals that carry a prototype query.
    """
    for section in models_payload.get("exploration", {}).get("sections", []):
        for vc in section.get("visualContainers", []):
            try:
                cfg = json.loads(vc.get("config", "{}"))
                visual_type = cfg.get("singleVisual", {}).get("visualType")
                visual_id = cfg.get("name") or vc.get("id")
            except Exception:
                continue
            if visual_type not in {"tableEx", "card", "clusteredBarChart", "clusteredColumnChart", "pieChart", "donutChart", "treemap", "lineChart", "multiRowCard"}:
                continue
            query_raw = vc.get("query")
            if not query_raw:
                continue
            try:
                parsed_query = json.loads(query_raw)
            except Exception:
                continue

            # Build a querydata payload similar to what the embed sends
            model_id = models_payload.get("models", [{}])[0].get("id")
            dataset_id = models_payload.get("models", [{}])[0].get("dbName")
            body = {
                "version": "1.0.0",
                "queries": [
                    {
                        "Query": parsed_query,
                        "ApplicationContext": {
                            "DatasetId": dataset_id,
                            "Sources": [{"ReportId": report_id, "VisualId": str(visual_id)}],
                        },
                    }
                ],
                "cancelQueries": [],
            }
            if model_id:
                body["modelId"] = model_id
            yield (visual_id, body)


def run_category(category: str) -> None:
    page_url = PAGES[category]
    print(f"[{category}] fetching page: {page_url}")
    html = SESSION.get(page_url).text
    embed_src = find_embed_src(html)
    report_id = decode_resource_key(embed_src)
    print(f"[{category}] report_id/resource_key: {report_id}")

    models = fetch_models(report_id)
    cache_dir = CACHE_ROOT / category
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "modelsAndExploration.json").write_text(json.dumps(models, ensure_ascii=False))

    # Replay all interesting visuals
    for name, body in iter_visual_queries(models, report_id):
        try:
            resp = fetch_visual(report_id, body)
            fname = cache_dir / f"query_{name}.json"
            fname.write_text(json.dumps(resp, ensure_ascii=False))
            print(f"[{category}] saved {fname.name} (len={len(json.dumps(resp))})")
        except Exception as e:
            print(f"[{category}] failed visual {name}: {e}")


def main(args: List[str]) -> None:
    targets = args or list(PAGES.keys())
    for cat in targets:
        if cat not in PAGES:
            print(f"Unknown category: {cat}")
            continue
        run_category(cat)


if __name__ == "__main__":
    main(sys.argv[1:])
