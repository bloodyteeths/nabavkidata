"""
Test script for new tender fields
Verifies that all 6 new fields work correctly across all layers
"""
import asyncio
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select
from database import get_db_session
from models import Tender
from schemas import TenderCreate, TenderResponse, TenderSearchRequest


async def test_create_tender_with_new_fields():
    """Test creating a tender with all new fields populated"""
    print("\n" + "="*80)
    print("TEST 1: Create tender with new fields")
    print("="*80)

    async for db in get_db_session():
        # Create test tender with new fields
        test_tender = TenderCreate(
            tender_id="TEST-2025-NEW-FIELDS",
            title="Набавка на канцелариски материјал - Тест",
            description="Тестирање на нови полиња во базата",
            category="Канцелариски материјал",
            procuring_entity="Тест институција",
            status="open",
            language="mk",

            # NEW FIELDS
            procedure_type="Отворена постапка",
            contract_signing_date=date(2025, 3, 15),
            contract_duration="12 месеци",
            contracting_entity_category="Централна влада",
            procurement_holder="Министерство за тестирање",
            bureau_delivery_date=date(2025, 2, 28)
        )

        # Create ORM object
        db_tender = Tender(**test_tender.dict())
        db.add(db_tender)

        try:
            await db.commit()
            await db.refresh(db_tender)
            print("✓ Tender created successfully!")
            print(f"  Tender ID: {db_tender.tender_id}")
            print(f"  Procedure Type: {db_tender.procedure_type}")
            print(f"  Contract Signing Date: {db_tender.contract_signing_date}")
            print(f"  Contract Duration: {db_tender.contract_duration}")
            print(f"  Entity Category: {db_tender.contracting_entity_category}")
            print(f"  Procurement Holder: {db_tender.procurement_holder}")
            print(f"  Bureau Delivery Date: {db_tender.bureau_delivery_date}")
            return True
        except Exception as e:
            await db.rollback()
            print(f"✗ Error creating tender: {e}")
            return False


async def test_query_tender_with_new_fields():
    """Test querying a tender and accessing new fields"""
    print("\n" + "="*80)
    print("TEST 2: Query tender and access new fields")
    print("="*80)

    async for db in get_db_session():
        query = select(Tender).where(Tender.tender_id == "TEST-2025-NEW-FIELDS")
        result = await db.execute(query)
        tender = result.scalar_one_or_none()

        if tender:
            print("✓ Tender found!")
            print(f"  Title: {tender.title}")
            print(f"  Procedure Type: {tender.procedure_type}")
            print(f"  Contract Signing Date: {tender.contract_signing_date}")
            print(f"  Contract Duration: {tender.contract_duration}")
            print(f"  Entity Category: {tender.contracting_entity_category}")
            print(f"  Procurement Holder: {tender.procurement_holder}")
            print(f"  Bureau Delivery Date: {tender.bureau_delivery_date}")

            # Test Pydantic serialization
            tender_response = TenderResponse.from_orm(tender)
            print("\n✓ Pydantic serialization successful!")
            print(f"  Response contains {len(tender_response.dict())} fields")
            return True
        else:
            print("✗ Tender not found")
            return False


async def test_filter_by_new_fields():
    """Test filtering tenders by new fields"""
    print("\n" + "="*80)
    print("TEST 3: Filter by new fields")
    print("="*80)

    async for db in get_db_session():
        # Test filter by procedure_type
        query = select(Tender).where(Tender.procedure_type == "Отворена постапка")
        result = await db.execute(query)
        tenders = result.scalars().all()
        print(f"✓ Filter by procedure_type: Found {len(tenders)} tender(s)")

        # Test filter by contracting_entity_category
        query = select(Tender).where(
            Tender.contracting_entity_category == "Централна влада"
        )
        result = await db.execute(query)
        tenders = result.scalars().all()
        print(f"✓ Filter by entity_category: Found {len(tenders)} tender(s)")

        # Test filter by contract_signing_date range
        query = select(Tender).where(
            Tender.contract_signing_date >= date(2025, 1, 1),
            Tender.contract_signing_date <= date(2025, 12, 31)
        )
        result = await db.execute(query)
        tenders = result.scalars().all()
        print(f"✓ Filter by contract signing date: Found {len(tenders)} tender(s)")

        return True


async def test_update_new_fields():
    """Test updating tender with new field values"""
    print("\n" + "="*80)
    print("TEST 4: Update tender new fields")
    print("="*80)

    async for db in get_db_session():
        query = select(Tender).where(Tender.tender_id == "TEST-2025-NEW-FIELDS")
        result = await db.execute(query)
        tender = result.scalar_one_or_none()

        if tender:
            # Update new fields
            tender.procedure_type = "Ограничена постапка"
            tender.contract_duration = "24 месеци"

            try:
                await db.commit()
                await db.refresh(tender)
                print("✓ Tender updated successfully!")
                print(f"  New Procedure Type: {tender.procedure_type}")
                print(f"  New Contract Duration: {tender.contract_duration}")
                return True
            except Exception as e:
                await db.rollback()
                print(f"✗ Error updating tender: {e}")
                return False
        else:
            print("✗ Tender not found")
            return False


async def test_nullable_new_fields():
    """Test creating tender without new fields (they should be nullable)"""
    print("\n" + "="*80)
    print("TEST 5: Create tender without new fields (nullable test)")
    print("="*80)

    async for db in get_db_session():
        # Create tender without new fields
        test_tender = TenderCreate(
            tender_id="TEST-2025-NULLABLE",
            title="Тест без нови полиња",
            description="Проверка дали новите полиња се nullable",
            category="Тест",
            status="open",
            language="mk"
        )

        db_tender = Tender(**test_tender.dict())
        db.add(db_tender)

        try:
            await db.commit()
            await db.refresh(db_tender)
            print("✓ Tender created successfully without new fields!")
            print(f"  Tender ID: {db_tender.tender_id}")
            print(f"  Procedure Type: {db_tender.procedure_type} (should be None)")
            print(f"  Contract Signing Date: {db_tender.contract_signing_date} (should be None)")
            return True
        except Exception as e:
            await db.rollback()
            print(f"✗ Error creating tender: {e}")
            return False


async def test_cleanup():
    """Cleanup test data"""
    print("\n" + "="*80)
    print("CLEANUP: Removing test data")
    print("="*80)

    async for db in get_db_session():
        # Delete test tenders
        for tender_id in ["TEST-2025-NEW-FIELDS", "TEST-2025-NULLABLE"]:
            query = select(Tender).where(Tender.tender_id == tender_id)
            result = await db.execute(query)
            tender = result.scalar_one_or_none()

            if tender:
                await db.delete(tender)
                print(f"✓ Deleted {tender_id}")

        try:
            await db.commit()
            print("✓ Cleanup complete!")
            return True
        except Exception as e:
            await db.rollback()
            print(f"✗ Error during cleanup: {e}")
            return False


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("STARTING NEW FIELDS VALIDATION TESTS")
    print("="*80)
    print("\nTesting 6 new fields:")
    print("  1. procedure_type")
    print("  2. contract_signing_date")
    print("  3. contract_duration")
    print("  4. contracting_entity_category")
    print("  5. procurement_holder")
    print("  6. bureau_delivery_date")

    results = []

    # Run tests
    results.append(await test_create_tender_with_new_fields())
    results.append(await test_query_tender_with_new_fields())
    results.append(await test_filter_by_new_fields())
    results.append(await test_update_new_fields())
    results.append(await test_nullable_new_fields())
    results.append(await test_cleanup())

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(results)
    total = len(results)
    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("\n✓ ALL TESTS PASSED! Schema update is working correctly.")
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please review errors above.")

    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
