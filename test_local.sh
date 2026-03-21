#!/usr/bin/env bash
# Local test script — simulates what the GitHub Actions start/stop do.
# Usage: bash test_local.sh
set -euo pipefail

DIR=$(mktemp -d)
echo "=== Using temp dir: $DIR ==="

# -- start phase --
echo "Starting tracker..."
python3 start/tracker.py --dir "$DIR" &
sleep 2

# -- simulate CI work --
echo "Simulating CI work (10s)..."
sleep 10

# -- stop phase --
echo "Generating report..."
export PR_NUMBER="test-local"
export BRANCH_NAME="local"
python3 stop/report.py --dir "$DIR" --markdown "$DIR/carbon-report.md" --history carbon-history.csv

echo ""
echo "=== Markdown report ==="
cat "$DIR/carbon-report.md"

echo "=== CSV history ==="
cat carbon-history.csv

rm -rf "$DIR"
echo "Done."
