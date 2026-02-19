# How the Financial Bid Extractor Fix Works

## Step-by-Step Walkthrough

Let's trace through exactly how the fixed extractor processes this real-world example:

### Input (Line-by-Line PDF Text)
```
50421200
-4
Николет
Работен
час
1,00
2.000,00
2.000,00
360,00
2.360,00
```

---

## Processing Flow

### Step 1: Detect CPV Code (Line 239)
```python
cpv_match = re.match(r'^(\d{8})\s*$', line)
```
- ✅ Matches line: `"50421200"`
- Result: `cpv_code = "50421200"`
- Advance: `i += 1`

### Step 2: Check for CPV Suffix (Lines 246-251)
```python
suffix_match = re.match(r'^-(\d)\s*$', next_line)
```
- ✅ Matches next line: `"-4"`
- Result: `cpv_code = "50421200-4"`
- Advance: `i += 1`

### Step 3: Collect Item Parts and Numbers (Lines 257-284)
Loop through remaining lines until we hit a stop condition:

| Line | Check | Action |
|------|-------|--------|
| `"Николет"` | `_is_pure_number()` → False | Add to `item_parts` |
| `"Работен"` | `_is_pure_number()` → False | Add to `item_parts` |
| `"час"` | `_is_pure_number()` → False | Add to `item_parts` |
| `"1,00"` | `_is_pure_number()` → True | Add to `numeric_values` |
| `"2.000,00"` | `_is_pure_number()` → True | Add to `numeric_values` |
| `"2.000,00"` | `_is_pure_number()` → True | Add to `numeric_values` |
| `"360,00"` | `_is_pure_number()` → True | Add to `numeric_values` |
| `"2.360,00"` | `_is_pure_number()` → True | Add to `numeric_values` |

**Result:**
- `item_parts = ["Николет", "Работен", "час"]`
- `numeric_values = ["1,00", "2.000,00", "2.000,00", "360,00", "2.360,00"]`

### Step 4: Identify Unit Keywords (Lines 292-295)
```python
for idx, part in enumerate(item_parts):
    if self._looks_like_unit(part):
        unit_indices.append(idx)
```

Check each part:
- idx=0: `"Николет"` → Not a unit keyword
- idx=1: `"Работен"` → ✅ Unit keyword! (matches 'работен')
- idx=2: `"час"` → ✅ Unit keyword! (matches 'час')

**Result:** `unit_indices = [1, 2]`

### Step 5: Find Consecutive Unit Group (Lines 297-312)

```python
unit_start = unit_indices[-1]  # Start at last unit (index 2)

# Check backwards for consecutive indices
for idx in range(len(unit_indices) - 2, -1, -1):  # idx goes from 0 to -1
    if unit_indices[idx] == unit_start - 1:
        unit_start = unit_indices[idx]
    else:
        break
```

**Iteration:**
- idx=0: Check if `unit_indices[0] (1) == unit_start - 1 (1)`
  - ✅ YES! They're consecutive
  - Update: `unit_start = 1`

**Result:**
- `unit_start = 1`
- `unit_indices[-1] = 2`

### Step 6: Extract Unit and Name (Lines 310-312)

```python
item_unit = ' '.join(item_parts[unit_start:unit_indices[-1] + 1])
# item_parts[1:3] = ["Работен", "час"]

item_name = ' '.join(item_parts[:unit_start])
# item_parts[0:1] = ["Николет"]
```

**Result:**
- `item_unit = "Работен час"`
- `item_name = "Николет"`

### Step 7: Parse Numeric Values (Line 322, then 503-520)

```python
item = self._create_item_from_values(
    cpv_code="50421200-4",
    name="Николет",
    values=["1,00", "2.000,00", "2.000,00", "360,00", "2.360,00"],
    ...
)
```

Inside `_create_item_from_values`:

1. **Parse each value** with `_parse_mkd_number()`:
   - `"1,00"` → Remove nothing, replace comma → `"1.00"` → `Decimal(1.00)`
   - `"2.000,00"` → Remove dot, replace comma → `"2000.00"` → `Decimal(2000.00)`
   - etc.

2. **Assign to fields** (lines 497-503):
   ```python
   if len(parsed_values) >= 5:
       item.quantity = float(parsed_values[0])           # 1.00
       item.unit_price_mkd = parsed_values[1]            # 2000.00
       item.total_price_mkd = parsed_values[2]           # 2000.00
       item.vat_amount_mkd = parsed_values[3]            # 360.00
       item.total_with_vat_mkd = parsed_values[4]        # 2360.00
   ```

### Step 8: Add Unit to Item (Lines 330-332)

```python
if item_unit:
    item.unit = item_unit  # "Работен час"
```

### Step 9: Add to Bid Items (Line 333)

```python
bid.items.append(item)
```

---

## Final Result

```python
BidItem(
    cpv_code="50421200-4",
    name="Николет",
    unit="Работен час",
    quantity=1.0,
    unit_price_mkd=Decimal('2000.00'),
    total_price_mkd=Decimal('2000.00'),
    vat_amount_mkd=Decimal('360.00'),
    total_with_vat_mkd=Decimal('2360.00'),
    lot_number=None,
    lot_description=None,
    item_number=1,
    raw_text="50421200-4 | Николет | 1,00 | 2.000,00 | 2.000,00 | 360,00 | 2.360,00"
)
```

---

## Key Improvements

### 1. Multi-Word Unit Handling
**Before:** Would match "Работен" and stop → name would be empty
**After:** Identifies both "Работен" and "час" as consecutive units → combines them

### 2. Proper Name Extraction
**Before:** Everything after first unit keyword was lost
**After:** Everything BEFORE the unit group is the name

### 3. Number Format Handling
Already worked, but worth noting:
- Macedonian format: `2.000,00` (dot = thousands, comma = decimal)
- Converted to: `2000.00`

### 4. Robust Fallbacks
If name is empty but CPV exists → creates item with CPV as name
If unit can't be extracted → tries to extract from name later
If numbers are missing → partial data still saved

---

## Edge Cases Handled

### Case 1: Unit in Middle of Name
```
Работен
Николет
час
```
Result: Uses LAST consecutive group → unit = "час", name = "Работен Николет"

### Case 2: No Unit Found
```
Николет
Special Item
```
Result: unit_indices = [], name = "Николет Special Item", unit = None

### Case 3: Only Unit, No Name
```
Работен
час
```
Result: name = "", but fallback creates name = "Item 50421200-4"

### Case 4: Non-Consecutive Units
```
парче
Николет
час
```
Result: unit_indices = [0, 2], not consecutive → unit = "час", name = "парче Николет"

---

## Testing

Run the test file to validate:
```bash
python test_financial_bid_fix.py
```

Expected output:
```
=== Extraction Results ===
Tender ID: 123/2024
Procuring Entity: Тест Компанија
Number of items: 1
Confidence: 0.XX

=== Item 1 ===
CPV Code: 50421200-4
Name: Николет
Unit: Работен час
Quantity: 1.0
Unit Price: 2000.00
Total Price: 2000.00
VAT: 360.00
Total with VAT: 2360.00

=== All Tests Passed! ===
✓ Financial bid extractor is working correctly!
✓ Successfully extracted 1 item(s) from line-by-line PDF text
```
