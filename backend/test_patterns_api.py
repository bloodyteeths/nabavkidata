"""
Simple API test for bidding pattern endpoint
Tests the endpoint via HTTP requests
"""
import asyncio
import httpx
import json

async def test_api_endpoint():
    """Test the bidding patterns API endpoint"""

    # Note: This requires the FastAPI server to be running
    base_url = "http://localhost:8000"

    # Test company (from our database analysis)
    test_company = "Друштво за промет и услуги АЛКАЛОИД КОНС увоз извоз ДООЕЛ Скопје"

    print("=" * 80)
    print("BIDDING PATTERN API ENDPOINT TEST")
    print("=" * 80)
    print(f"\nTesting endpoint: GET /api/competitors/{{company_name}}/patterns")
    print(f"Company: {test_company}")
    print(f"Analysis period: 24 months (default)")

    endpoint = f"{base_url}/api/competitors/{test_company}/patterns"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\nSending request to: {endpoint}")
            response = await client.get(endpoint)

            print(f"\nStatus Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("\n✓ SUCCESS - Response received:")
                print("\n" + "=" * 80)
                print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
                print("=" * 80)

                # Validate response structure
                print("\n✓ Validating response structure...")
                assert "company_name" in data
                assert "analysis_period" in data
                assert "total_bids" in data
                assert "total_wins" in data
                assert "pricing_pattern" in data
                assert "category_preferences" in data
                assert "size_preferences" in data
                assert "seasonal_activity" in data
                assert "top_competitors" in data
                assert "win_factors" in data

                print(f"  ✓ Company: {data['company_name']}")
                print(f"  ✓ Analysis Period: {data['analysis_period']}")
                print(f"  ✓ Total Bids: {data['total_bids']}")
                print(f"  ✓ Total Wins: {data['total_wins']}")
                print(f"  ✓ Win Rate: {data['overall_win_rate']:.2f}%")

                if data['pricing_pattern']['avg_discount']:
                    print(f"  ✓ Avg Discount: {data['pricing_pattern']['avg_discount']:.2f}%")

                print(f"  ✓ Category Preferences: {len(data['category_preferences'])} categories")
                print(f"  ✓ Size Preferences: {len(data['size_preferences'])} size categories")
                print(f"  ✓ Seasonal Activity: {len(data['seasonal_activity'])} months")
                print(f"  ✓ Top Competitors: {len(data['top_competitors'])} competitors")

                print("\n" + "=" * 80)
                print("✓ ALL TESTS PASSED!")
                print("=" * 80)

            elif response.status_code == 404:
                print(f"\n❌ Company not found: {response.json()['detail']}")
            else:
                print(f"\n❌ Error: {response.text}")

        except httpx.ConnectError:
            print("\n❌ ERROR: Could not connect to API server")
            print("   Make sure the FastAPI server is running:")
            print("   cd backend && source venv/bin/activate && uvicorn main:app --reload")
        except Exception as e:
            print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_endpoint())
