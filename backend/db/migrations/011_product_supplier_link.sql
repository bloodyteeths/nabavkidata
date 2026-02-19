-- Add supplier tracking to product_items
-- This allows the LLM to answer "Who supplies X?" queries

ALTER TABLE product_items
ADD COLUMN IF NOT EXISTS supplier_name VARCHAR(500),
ADD COLUMN IF NOT EXISTS supplier_id UUID,
ADD COLUMN IF NOT EXISTS is_awarded BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS award_date DATE;

-- Create indexes for supplier searches
CREATE INDEX IF NOT EXISTS idx_product_items_supplier ON product_items(supplier_name);
CREATE INDEX IF NOT EXISTS idx_product_items_awarded ON product_items(is_awarded) WHERE is_awarded = TRUE;

-- Backfill supplier_name from tender_bidders where is_winner = TRUE
UPDATE product_items pi
SET supplier_name = tb.company_name,
    is_awarded = TRUE
FROM tender_bidders tb
WHERE pi.tender_id = tb.tender_id
  AND tb.is_winner = TRUE
  AND pi.supplier_name IS NULL;

-- Also try to get from tenders.winner column
UPDATE product_items pi
SET supplier_name = t.winner,
    is_awarded = TRUE
FROM tenders t
WHERE pi.tender_id = t.tender_id
  AND t.winner IS NOT NULL
  AND t.winner != ''
  AND pi.supplier_name IS NULL;

-- Set award_date from tender publication_date for awarded items
UPDATE product_items pi
SET award_date = t.publication_date
FROM tenders t
WHERE pi.tender_id = t.tender_id
  AND pi.is_awarded = TRUE
  AND pi.award_date IS NULL;
