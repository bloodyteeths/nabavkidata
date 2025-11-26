# Quick Field Reference - Developer Cheat Sheet

## How to Add a Hidden Field to the UI

### Step 1: Check if field is in API schema
```typescript
// backend/schemas.py
class TenderResponse(TenderBase):
    # Check if field is listed here
    procedure_type: Optional[str] = None  # ✅ Already in API
    contact_person: Optional[str] = None   # ❌ NOT in API - add it first!
```

### Step 2: Add to API schema if missing
```python
# backend/schemas.py - Add to TenderBase
class TenderBase(BaseModel):
    # ... existing fields ...
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
```

### Step 3: Add to frontend TypeScript interface
```typescript
// frontend/lib/api.ts
export interface Tender {
  // ... existing fields ...
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
}
```

### Step 4: Display in UI component
```typescript
// frontend/app/tenders/[id]/page.tsx
{tender.contact_person && (
  <div className="flex items-center gap-2">
    <User className="h-4 w-4" />
    <span>{tender.contact_person}</span>
  </div>
)}
```

---

## Field Quick Reference

### ✅ READY TO USE (In DB, API, just add UI)

| Field | Location in API | Sample Display Code |
|-------|----------------|-------------------|
| `procedure_type` | ✅ `TenderResponse` | `<Badge>{tender.procedure_type}</Badge>` |
| `contract_signing_date` | ✅ `TenderResponse` | `{formatDate(tender.contract_signing_date)}` |
| `contracting_entity_category` | ✅ `TenderResponse` | `<Badge>{tender.contracting_entity_category}</Badge>` |
| `publication_date` | ✅ `TenderResponse` | `{formatDate(tender.publication_date)}` |
| `winner` | ✅ `TenderResponse` | `<span>{tender.winner}</span>` |

### ❌ NEED TO ADD TO API FIRST

| Field | DB Column | Add to Schema | Population |
|-------|-----------|--------------|-----------|
| `contact_person` | ✅ varchar(255) | `TenderBase` | 100% |
| `contact_email` | ✅ varchar(255) | `TenderBase` | 100% |
| `contact_phone` | ✅ varchar(100) | `TenderBase` | 80% |
| `num_bidders` | ✅ integer | `TenderBase` | 5% |
| `has_lots` | ✅ boolean | `TenderBase` | 100% |
| `num_lots` | ✅ integer | `TenderBase` | 0% (broken) |
| `security_deposit_mkd` | ✅ numeric(15,2) | `TenderBase` | 0% (empty) |
| `highest_bid_mkd` | ✅ numeric(18,2) | `TenderBase` | 0% (empty) |
| `lowest_bid_mkd` | ✅ numeric(18,2) | `TenderBase` | 0% (empty) |
| `delivery_location` | ✅ text | `TenderBase` | 0% (empty) |
| `payment_terms` | ✅ text | `TenderBase` | 0% (empty) |

---

## Common Display Patterns

### Badge for Categories/Types
```typescript
{tender.procedure_type && (
  <Badge variant="outline">
    {tender.procedure_type}
  </Badge>
)}
```

### Date Display with Icon
```typescript
{tender.publication_date && (
  <div className="flex items-center gap-2">
    <Calendar className="h-4 w-4" />
    <span>{formatDate(tender.publication_date)}</span>
  </div>
)}
```

### Currency Display
```typescript
{tender.estimated_value_mkd && (
  <div className="flex items-center gap-2">
    <DollarSign className="h-4 w-4" />
    <span>{formatCurrency(tender.estimated_value_mkd)}</span>
  </div>
)}
```

### Contact Information Section
```typescript
<Card>
  <CardHeader>
    <CardTitle>Контакт</CardTitle>
  </CardHeader>
  <CardContent className="space-y-3">
    {tender.contact_person && (
      <div className="flex items-center gap-2">
        <User className="h-4 w-4" />
        <span>{tender.contact_person}</span>
      </div>
    )}
    {tender.contact_email && (
      <div className="flex items-center gap-2">
        <Mail className="h-4 w-4" />
        <a href={`mailto:${tender.contact_email}`} className="text-primary">
          {tender.contact_email}
        </a>
      </div>
    )}
    {tender.contact_phone && (
      <div className="flex items-center gap-2">
        <Phone className="h-4 w-4" />
        <span>{tender.contact_phone}</span>
      </div>
    )}
  </CardContent>
</Card>
```

---

## API Endpoint Reference

### Get Single Tender
```
GET /api/tenders/{tender_id}
Returns: TenderResponse with all exposed fields
```

### Get Tender Bidders
```
GET /api/tenders/by-id/{number}/{year}/bidders
Returns: BiddersListResponse
Fields: company_name, bid_amount_mkd, rank, is_winner
Status: ✅ API works, ❌ NO UI
```

### Get Tender Lots
```
GET /api/tenders/by-id/{number}/{year}/lots
Returns: LotsListResponse
Status: ✅ API works, ❌ NO DATA (tender_lots table empty)
```

### Get Tender Documents
```
GET /api/tenders/by-id/{number}/{year}/documents
Returns: DocumentsListResponse
Status: ✅ API works, ✅ UI works
```

### Get Supplier Info
```
GET /api/suppliers/{supplier_id}
GET /api/suppliers/search?query={name}
GET /api/suppliers/stats
Status: ✅ API works, ❌ NO UI at /suppliers
```

---

## Database Query Examples

### Check Field Population
```sql
SELECT
  COUNT(*) as total,
  COUNT(contact_person) as has_contact,
  COUNT(procedure_type) as has_procedure,
  COUNT(num_bidders) as has_bidders
FROM tenders;
```

### Find Tenders with Specific Data
```sql
-- Tenders with bidders
SELECT tender_id, title, num_bidders
FROM tenders
WHERE num_bidders > 0;

-- Tenders with contact info
SELECT tender_id, contact_person, contact_email, contact_phone
FROM tenders
WHERE contact_email IS NOT NULL
LIMIT 10;

-- Check lot data
SELECT t.tender_id, t.has_lots, t.num_lots, COUNT(l.lot_id) as actual_lots
FROM tenders t
LEFT JOIN tender_lots l ON t.tender_id = l.tender_id
WHERE t.has_lots = true
GROUP BY t.tender_id, t.has_lots, t.num_lots;
```

---

## Common Gotchas

### 1. Tender ID Format
```
Format: "{number}/{year}"
Example: "19138/2025"

In API path: /tenders/by-id/19138/2025
In query: tender_id = '19138/2025'
```

### 2. NULL vs Empty String
```sql
-- Check for real NULL
WHERE contact_email IS NULL

-- Check for empty or NULL
WHERE contact_email IS NULL OR contact_email = ''

-- Check for data
WHERE contact_email IS NOT NULL AND contact_email != ''
```

### 3. Date Formatting
```typescript
// Frontend date formatting
import { formatDate } from "@/lib/utils";

// Input: "2025-12-31"
// Output: "31.12.2025" (Macedonian format)
```

### 4. Currency Formatting
```typescript
// Frontend currency formatting
import { formatCurrency } from "@/lib/utils";

// Input: 150000
// Output: "150.000 МКД"
```

---

## Field Priority for Implementation

### 🔴 High Priority (User-requested)
1. Contact information (person, email, phone)
2. Procedure type
3. Bidders tab
4. Publication date

### 🟡 Medium Priority (Nice to have)
5. Winner display (awarded tenders)
6. Contracting entity category
7. EUR currency values
8. Actual value (awarded)

### 🟢 Low Priority (Future)
9. Contract duration
10. Lots breakdown (after scraper fix)
11. Amendment history (after scraper fix)
12. Product items (after extraction fix)

---

## Testing Checklist

### Before Adding a New Field to UI

- [ ] Field exists in DB (`\d tenders`)
- [ ] Field has data (`SELECT COUNT(field_name) FROM tenders`)
- [ ] Field is in API schema (`backend/schemas.py`)
- [ ] Field is in TypeScript interface (`frontend/lib/api.ts`)
- [ ] API returns the field (test with curl/Postman)
- [ ] Field displays correctly with sample data
- [ ] Field handles NULL gracefully
- [ ] Mobile responsive layout works

### After Implementation

- [ ] Test with NULL values
- [ ] Test with long strings
- [ ] Test with special characters (Cyrillic)
- [ ] Test on mobile viewport
- [ ] Test field search/filter (if applicable)
- [ ] Check console for errors
- [ ] Verify no TypeScript errors

---

## Common Icons for Fields

```typescript
import {
  User,          // contact_person
  Mail,          // contact_email
  Phone,         // contact_phone
  Building2,     // procuring_entity
  Calendar,      // dates
  DollarSign,    // values
  Tag,           // category, CPV
  FileText,      // documents
  Users,         // bidders
  Trophy,        // winner
  Clock,         // dates/time
  Package,       // items/lots
  ExternalLink,  // source_url
} from "lucide-react";
```

---

## Data Population Quick Reference

| Field | Population % | Notes |
|-------|-------------|-------|
| `tender_id` | 100% | Primary key |
| `title` | 100% | Always populated |
| `description` | 95% | Mostly present |
| `category` | 100% | Always populated |
| `status` | 100% | Always populated |
| `procuring_entity` | 100% | Always populated |
| `procedure_type` | 100% | ⭐ Always populated |
| `contact_person` | 100% | ⭐ Always populated |
| `contact_email` | 100% | ⭐ Always populated |
| `contact_phone` | 80% | Mostly present |
| `estimated_value_mkd` | 90% | Usually present |
| `cpv_code` | 85% | Usually present |
| `publication_date` | 60% | Often missing |
| `num_bidders` | 5% | Rarely populated |
| `winner` | 10% | Only awarded |
| `security_deposit_mkd` | 0% | ❌ Never populated |
| `payment_terms` | 0% | ❌ Never populated |

---

Generated: 2025-11-25
For questions: Check full audit in DB_API_UI_FIELD_MAPPING_AUDIT.md
