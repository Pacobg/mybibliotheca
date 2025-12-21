#!/bin/bash
# Fix KuzuDB lock file issues on dev server
# Usage: ./scripts/fix_kuzu_locks.sh

set -e

KUZU_DB_PATH="${KUZU_DB_PATH:-./data/kuzu}"

echo "🔍 Checking for KuzuDB lock files..."

# Check if KuzuDB directory exists
if [ ! -d "$KUZU_DB_PATH" ]; then
    echo "❌ KuzuDB directory not found: $KUZU_DB_PATH"
    exit 1
fi

# Find and remove lock files
LOCK_FILES=$(find "$KUZU_DB_PATH" -name ".lock" -o -name "*.lock" 2>/dev/null || true)

if [ -z "$LOCK_FILES" ]; then
    echo "✅ No lock files found"
else
    echo "🧹 Found lock files:"
    echo "$LOCK_FILES"
    echo ""
    echo "Removing lock files..."
    find "$KUZU_DB_PATH" -name ".lock" -delete 2>/dev/null || true
    find "$KUZU_DB_PATH" -name "*.lock" -delete 2>/dev/null || true
    echo "✅ Lock files removed"
fi

# Check for running processes that might be holding locks
echo ""
echo "🔍 Checking for processes using KuzuDB..."
PYTHON_PROCS=$(ps aux | grep -E "python.*run.py|gunicorn.*run:app" | grep -v grep || true)

if [ -z "$PYTHON_PROCS" ]; then
    echo "✅ No Python processes found holding locks"
else
    echo "⚠️  Found Python processes:"
    echo "$PYTHON_PROCS"
    echo ""
    echo "💡 Tip: Stop the application before removing locks to prevent data corruption"
fi

echo ""
echo "✅ KuzuDB lock cleanup completed!"
echo "💡 You can now restart the application"

