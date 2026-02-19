#!/bin/bash
# Quick script to generate e-Pazar embeddings with logging

cd "$(dirname "$0")"

echo "Starting e-Pazar embedding generation..."
echo "Date: $(date)"
echo "Working directory: $(pwd)"
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Check current status before running
echo "=== Current Status ==="
PGPASSWORD="$DB_PASS" psql \
    -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
    -U nabavki_user \
    -d nabavkidata \
    -c "SELECT COUNT(*) as without_embeddings FROM epazar_tenders e WHERE NOT EXISTS (SELECT 1 FROM embeddings emb WHERE emb.tender_id = 'epazar_' || e.tender_id);"

echo ""
echo "=== Starting Embedding Generation ==="
echo "This will take approximately 10-20 minutes for 900 tenders..."
echo ""

# Run the embedding script
python3 embed_epazar.py --batch-size 50

echo ""
echo "=== Final Status ==="
PGPASSWORD="$DB_PASS" psql \
    -h nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com \
    -U nabavki_user \
    -d nabavkidata \
    -c "SELECT COUNT(*) as total_epazar_embeddings FROM embeddings WHERE tender_id LIKE 'epazar_%';"

echo ""
echo "Done! Check logs/embed_epazar.log for detailed output."
echo "Date: $(date)"
