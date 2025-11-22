#!/bin/bash
# Install scraper cron jobs
# Usage: ./install.sh

set -e  # Exit on error

echo "============================================"
echo "Nabavki Scraper - Cron Job Installation"
echo "============================================"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "Project directory: $PROJECT_DIR"
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set"
    read -p "Enter DATABASE_URL (postgresql://...): " DATABASE_URL
    export DATABASE_URL
fi

# Validate DATABASE_URL
if [[ ! "$DATABASE_URL" =~ ^postgresql:// ]]; then
    echo "❌ Invalid DATABASE_URL format"
    exit 1
fi

echo "✓ DATABASE_URL: $DATABASE_URL"

# Create logs directory
echo ""
echo "Creating logs directory..."
mkdir -p "$PROJECT_DIR/logs"
echo "✓ Logs directory created"

# Update scraper.cron with actual paths
echo ""
echo "Updating cron file paths..."
CRON_FILE="$SCRIPT_DIR/scraper.cron"
TEMP_CRON="/tmp/scraper_cron_temp"

# Replace placeholder paths
sed "s|SCRAPER_DIR=.*|SCRAPER_DIR=$PROJECT_DIR|g" "$CRON_FILE" > "$TEMP_CRON"
sed -i.bak "s|DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|g" "$TEMP_CRON"

echo "✓ Paths updated"

# Show cron jobs
echo ""
echo "============================================"
echo "Cron jobs to be installed:"
echo "============================================"
grep -v "^#" "$TEMP_CRON" | grep -v "^$" | grep -v "^SHELL" | grep -v "^PATH" | grep -v "^DATABASE_URL" | grep -v "^SCRAPER_DIR"
echo ""

# Confirm installation
read -p "Install these cron jobs? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ]; then
    echo "Installation cancelled"
    rm "$TEMP_CRON"
    exit 0
fi

# Backup existing crontab
echo ""
echo "Backing up existing crontab..."
crontab -l > "$PROJECT_DIR/logs/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null || true
echo "✓ Backup created"

# Install crontab
echo ""
echo "Installing cron jobs..."
crontab "$TEMP_CRON"
rm "$TEMP_CRON"
rm "${TEMP_CRON}.bak" 2>/dev/null || true

echo "✓ Cron jobs installed"

# Verify installation
echo ""
echo "============================================"
echo "Installed cron jobs:"
echo "============================================"
crontab -l | grep -v "^#" | grep -v "^$"

echo ""
echo "✓ Installation complete!"
echo ""
echo "Scraping schedule:"
echo "  - Hourly: Incremental scrape (every hour)"
echo "  - Daily: Full scrape (2 AM)"
echo "  - Weekly: Deep scrape (Sunday 3 AM)"
echo ""
echo "Logs location: $PROJECT_DIR/logs/"
echo ""
echo "To view logs:"
echo "  tail -f $PROJECT_DIR/logs/scraper_hourly.log"
echo ""
echo "To uninstall:"
echo "  crontab -r"
echo ""
