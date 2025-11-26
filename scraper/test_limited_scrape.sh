#!/bin/bash
# Limited test scrape - runs for max 2 minutes or until 3 items are scraped

cd /Users/tamsar/Downloads/nabavkidata/scraper
source venv/bin/activate

echo "Starting limited test scrape (max 3 items, 2 minute timeout)..."
echo "=================================================="

# Run scraper with item count limit
timeout 120 scrapy crawl nabavki -s CLOSESPIDER_ITEMCOUNT=3 -o test_output.json 2>&1 | grep -E "(INFO|WARNING|ERROR|scraped|Closing spider)" | tail -100

echo ""
echo "=================================================="
echo "Test scrape completed (or timed out)"
echo ""

# Check results
if [ -f test_output.json ]; then
    python3 << 'PYTHON_EOF'
import json
import sys

try:
    with open('test_output.json', 'r') as f:
        items = json.load(f)

    count = len(items)
    print(f"Items scraped: {count}")
    print("=" * 50)

    for i, item in enumerate(items[:3], 1):
        print(f"\nItem {i}:")
        print(f"  Tender ID: {item.get('tender_id', 'N/A')}")
        print(f"  Title: {item.get('title', 'N/A')[:70]}")
        print(f"  Closing Date: {item.get('closing_date', 'N/A')}")
        print(f"  Estimated Value: {item.get('estimated_value_mkd', 'N/A')} MKD")
        print(f"  CPV Code: {item.get('cpv_code', 'N/A')}")
        print(f"  Procuring Entity: {item.get('procuring_entity', 'N/A')[:50]}")
        print(f"  Contact Person: {item.get('contact_person', 'N/A')}")
        print(f"  Contact Email: {item.get('contact_email', 'N/A')}")
        print(f"  Contact Phone: {item.get('contact_phone', 'N/A')}")

except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")
    print("File might be incomplete or malformed")
except FileNotFoundError:
    print("No test_output.json file found")
except Exception as e:
    print(f"Error: {e}")
PYTHON_EOF
else
    echo "No test_output.json file created - scraper may not have completed any items"
fi
