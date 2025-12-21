#!/bin/bash
# Script to resolve merge conflicts on dev server - Fixed version

set -e

echo "🔍 Checking git status..."
cd ~/mybibliotheca || { echo "❌ Directory not found"; exit 1; }

# Abort any ongoing merge first
if [ -f .git/MERGE_HEAD ]; then
    echo "🛑 Aborting current merge..."
    git merge --abort 2>/dev/null || true
fi

# Stash any non-conflict changes (but not merge conflicts)
echo "💾 Stashing non-conflict changes..."
git stash push -m "Local changes before merge $(date +%Y-%m-%d_%H-%M-%S)" 2>/dev/null || echo "No changes to stash"

# Fetch latest changes
echo "📥 Fetching latest changes..."
git fetch origin main

# Check current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "📍 Current branch: $CURRENT_BRANCH"

# Check if we're behind remote
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "✅ Already up to date with origin/main"
    exit 0
fi

echo "🔄 Pulling changes..."
# Reset to remote version to avoid conflicts (we want remote version)
echo "⚠️  Resetting to remote version (accepting all remote changes)..."
git reset --hard origin/main

echo "✅ Successfully updated to latest version!"
echo "📋 Recent commits:"
git log --oneline -5

echo ""
echo "💡 If you had local changes, you can recover them with: git stash list"

