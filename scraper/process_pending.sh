#!/bin/bash
# Convenience script for processing pending documents

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../backend/venv" ]; then
    source ../backend/venv/bin/activate
fi

case "${1:-help}" in
    test)
        echo "=== Testing with 10 documents (dry run) ==="
        python3 process_pending_docs.py --dry-run --limit 10
        ;;

    small)
        echo "=== Processing 50 documents ==="
        python3 process_pending_docs.py --limit 50
        ;;

    batch)
        LIMIT="${2:-100}"
        echo "=== Processing $LIMIT documents ==="
        python3 process_pending_docs.py --limit "$LIMIT"
        ;;

    all)
        echo "=== Processing ALL pending documents ==="
        echo "This will process all 7,369 pending documents in batches of 100"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 process_pending_docs.py --all
        fi
        ;;

    resume)
        echo "=== Resuming from checkpoint ==="
        python3 process_pending_docs.py --resume --all
        ;;

    tender)
        if [ -z "$2" ]; then
            echo "Usage: $0 tender <tender_id>"
            echo "Example: $0 tender 23178/2025"
            exit 1
        fi
        echo "=== Processing tender $2 ==="
        python3 process_pending_docs.py --tender-id "$2"
        ;;

    with-embeddings)
        LIMIT="${2:-100}"
        echo "=== Processing $LIMIT documents with embeddings ==="
        python3 process_pending_docs.py --limit "$LIMIT" --generate-embeddings
        ;;

    stats)
        echo "=== Current Database Statistics ==="
        PGPASSWORD="$DB_PASS" psql \
            -h localhost \
            -U nabavki_user \
            -d nabavkidata \
            -c "SELECT extraction_status, COUNT(*) FROM documents GROUP BY extraction_status ORDER BY COUNT(*) DESC;"
        ;;

    pending)
        echo "=== Pending Documents with URLs ==="
        PGPASSWORD="$DB_PASS" psql \
            -h localhost \
            -U nabavki_user \
            -d nabavkidata \
            -c "SELECT COUNT(*) as count FROM documents WHERE extraction_status='pending' AND file_url IS NOT NULL AND file_url <> '';"
        ;;

    checkpoint)
        if [ -f "/tmp/process_pending_docs_checkpoint.json" ]; then
            echo "=== Checkpoint Status ==="
            python3 -c "import json; data=json.load(open('/tmp/process_pending_docs_checkpoint.json')); print(f'Processed: {len(data[\"processed_doc_ids\"])} documents'); print(f'Updated: {data[\"updated_at\"]}')"
        else
            echo "No checkpoint file found"
        fi
        ;;

    clear-checkpoint)
        echo "=== Clearing checkpoint ==="
        python3 process_pending_docs.py --clear-checkpoint
        ;;

    logs)
        if [ -f "/tmp/process_pending_docs.log" ]; then
            echo "=== Recent Log Entries ==="
            tail -n 50 /tmp/process_pending_docs.log
        else
            echo "No log file found"
        fi
        ;;

    follow-logs)
        echo "=== Following logs (Ctrl+C to stop) ==="
        tail -f /tmp/process_pending_docs.log
        ;;

    cleanup-pdfs)
        echo "=== Cleaning up successfully extracted PDFs ==="
        echo "This will delete PDF files that have been successfully extracted"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cd downloads/files
            PGPASSWORD="$DB_PASS" psql \
                -h localhost \
                -U nabavki_user \
                -d nabavkidata \
                -t -c "SELECT file_name FROM documents WHERE extraction_status='success' AND file_path LIKE '%.pdf';" | \
                while read -r filename; do
                    filename=$(echo "$filename" | xargs)  # trim whitespace
                    if [ -f "$filename" ]; then
                        rm -f "$filename"
                        echo "Deleted: $filename"
                    fi
                done
            cd ../..
        fi
        ;;

    help|*)
        cat << EOF
Pending Documents Processing Script

Usage: $0 <command> [options]

Commands:
  test              Dry run with 10 documents (no actual processing)
  small             Process 50 documents (good for testing)
  batch [N]         Process N documents (default: 100)
  all               Process all pending documents in batches
  resume            Resume processing from checkpoint
  tender <id>       Process documents for specific tender
  with-embeddings   Process documents and generate embeddings

  stats             Show current database statistics
  pending           Count pending documents with URLs
  checkpoint        Show checkpoint status
  clear-checkpoint  Clear checkpoint and start fresh

  logs              Show recent log entries
  follow-logs       Follow logs in real-time
  cleanup-pdfs      Delete successfully extracted PDFs to save space

  help              Show this help message

Examples:
  $0 test                    # Dry run
  $0 small                   # Process 50 docs
  $0 batch 200               # Process 200 docs
  $0 all                     # Process all pending
  $0 tender 23178/2025       # Process specific tender
  $0 stats                   # Show database stats
  $0 follow-logs             # Watch processing in real-time

Files:
  Script:     $SCRIPT_DIR/process_pending_docs.py
  Log:        /tmp/process_pending_docs.log
  Checkpoint: /tmp/process_pending_docs_checkpoint.json
  Downloads:  $SCRIPT_DIR/downloads/files/

EOF
        ;;
esac
