-- Check e-Pazar embedding status

-- 1. Count total epazar tenders
SELECT 'Total e-Pazar tenders' as metric, COUNT(*) as count
FROM epazar_tenders;

-- 2. Count epazar tenders WITH embeddings
SELECT 'e-Pazar tenders WITH embeddings' as metric, COUNT(*) as count
FROM epazar_tenders e
WHERE EXISTS (
    SELECT 1 FROM embeddings emb
    WHERE emb.tender_id = 'epazar_' || e.tender_id
);

-- 3. Count epazar tenders WITHOUT embeddings
SELECT 'e-Pazar tenders WITHOUT embeddings' as metric, COUNT(*) as count
FROM epazar_tenders e
WHERE NOT EXISTS (
    SELECT 1 FROM embeddings emb
    WHERE emb.tender_id = 'epazar_' || e.tender_id
);

-- 4. Count total epazar embeddings
SELECT 'Total e-Pazar embeddings' as metric, COUNT(*) as count
FROM embeddings
WHERE tender_id LIKE 'epazar_%';

-- 5. Sample epazar embeddings with metadata
SELECT
    tender_id,
    LEFT(chunk_text, 80) as text_preview,
    metadata->>'source' as source,
    metadata->>'contracting_authority' as authority,
    metadata->>'category' as category,
    created_at
FROM embeddings
WHERE tender_id LIKE 'epazar_%'
ORDER BY created_at DESC
LIMIT 5;
