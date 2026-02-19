#!/usr/bin/env python3
"""Test the contracts API directly."""
import requests
import json

# DataTables request format
data = {
    "draw": 1,
    "start": 0,
    "length": 10,
    "search": {"value": "", "regex": False},
    "columns": [],
    "order": []
}

# Try different request formats
print("=== Testing Contracts API ===\n")

# Test 1: JSON body
print("Test 1: JSON body")
try:
    resp = requests.post(
        'https://e-nabavki.gov.mk/Services/Contracts.asmx/GetContractsGridData',
        json=data,
        headers={'Content-Type': 'application/json'}
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 2: Form data
print("\nTest 2: Form data")
try:
    form_data = {
        'draw': 1,
        'start': 0,
        'length': 10,
        'search[value]': '',
        'search[regex]': 'false',
    }
    resp = requests.post(
        'https://e-nabavki.gov.mk/Services/Contracts.asmx/GetContractsGridData',
        data=form_data
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 3: Intercept actual browser request
print("\nTest 3: Mimic browser request with session cookies")
try:
    session = requests.Session()
    # First get the main page to get cookies
    session.get('https://e-nabavki.gov.mk/PublicAccess/home.aspx')

    # Then call the API
    resp = session.post(
        'https://e-nabavki.gov.mk/Services/Contracts.asmx/GetContractsGridData',
        json=data,
        headers={
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://e-nabavki.gov.mk/PublicAccess/home.aspx'
        }
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 4: Try with specific DataTables format
print("\nTest 4: Full DataTables format")
try:
    dt_data = {
        "draw": 1,
        "columns": [
            {"data": 0, "name": "", "searchable": True, "orderable": True, "search": {"value": "", "regex": False}},
        ],
        "order": [{"column": 0, "dir": "asc"}],
        "start": 0,
        "length": 10,
        "search": {"value": "", "regex": False}
    }
    resp = requests.post(
        'https://e-nabavki.gov.mk/Services/Contracts.asmx/GetContractsGridData',
        json=dt_data,
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text[:500]}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"\n  recordsTotal: {data.get('recordsTotal')}")
        print(f"  recordsFiltered: {data.get('recordsFiltered')}")
        if data.get('data'):
            print(f"  First record: {data['data'][0]}")
except Exception as e:
    print(f"  Error: {e}")
