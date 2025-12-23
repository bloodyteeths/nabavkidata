#!/bin/bash
#
# Auto-apply UX fixes to risk-analysis page
# Run this script from the frontend directory
#

FILE="app/risk-analysis/page.tsx"

if [ ! -f "$FILE" ]; then
    echo "Error: $FILE not found. Run this script from the frontend directory."
    exit 1
fi

echo "Backing up original file to ${FILE}.backup..."
cp "$FILE" "${FILE}.backup"

echo "Applying UX fixes..."

# Fix 1: Add target="_blank" to tender detail links (first occurrence)
perl -i -p0e 's|<Link href=\{`\/tenders\/\$\{encodeURIComponent\(tender\.tender_id\)\}`\} className="flex-1">|<Link href={`/tenders/${encodeURIComponent(tender.tender_id)}`} className="flex-1" target="_blank" rel="noopener noreferrer">|g' "$FILE"

# Fix 2: Add target="_blank" to supplier links
perl -i -p0e 's|<Link href=\{`\/suppliers\?search=\$\{encodeURIComponent\(tender\.winner\)\}`\} className="flex-1">|<Link href={`/suppliers?search=${encodeURIComponent(tender.winner)}`} className="flex-1" target="_blank" rel="noopener noreferrer">|g' "$FILE"

# Fix 3: Add target="_blank" to search tab tender link (different pattern - no className)
perl -i -p0e 's|<Link href=\{`\/tenders\/\$\{encodeURIComponent\(t\.tender_id\)\}`\}>|<Link href={`/tenders/${encodeURIComponent(t.tender_id)}`} target="_blank" rel="noopener noreferrer">|g' "$FILE"

# Fix 4: Add target="_blank" to analysis result link
perl -i -p0e 's|<Link href=\{`\/tenders\/\$\{encodeURIComponent\(analysisResult\.tenderId\)\}`\}>|<Link href={`/tenders/${encodeURIComponent(analysisResult.tenderId)}`} target="_blank" rel="noopener noreferrer">|g' "$FILE"

echo "✅ All links now open in new tabs"

# Fix 5: Make card header clickable
# This is more complex, so we'll use a multi-line perl replacement
echo "Making tender card headers clickable..."

# Add onClick and styling to the header div
perl -i -p0e 's|<div className="flex items-start gap-3 mb-3">(\s+<div className="relative w-12 h-12 flex-shrink-0">.*?</div>\s+</div>\s+<div className="flex-1 min-w-0">.*?</div>\s+)</div>|<div className="flex items-start gap-3 mb-3 cursor-pointer hover:bg-muted/50 -m-1 p-1 rounded transition-colors" onClick={() => handleExpand(tender.tender_id)}>$1<div className="flex items-center flex-shrink-0">{isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</div></div>|gs' "$FILE"

# Remove the old expand button from the bottom section
perl -i -p0e 's|<Button variant="ghost" size="sm" onClick=\{\(\) => handleExpand\(tender\.tender_id\)\} className="shrink-0">\s+\{isOpen \? <ChevronUp className="h-4 w-4" \/> : <ChevronDown className="h-4 w-4" \/>\}\s+<\/Button>||g' "$FILE"

echo "✅ Tender card headers are now clickable"

echo ""
echo "All fixes applied successfully!"
echo "Original file backed up to: ${FILE}.backup"
echo ""
echo "Summary of changes:"
echo "  - All tender and supplier links now open in new tabs"
echo "  - Entire tender card header is clickable to expand/collapse"
echo "  - Removed redundant expand button"
echo ""
echo "To undo changes: mv ${FILE}.backup ${FILE}"
