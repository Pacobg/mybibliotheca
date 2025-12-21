#!/bin/bash
# Script to resolve merge conflicts on dev server

set -e

echo "🔍 Checking git status..."
cd ~/mybibliotheca || { echo "❌ Directory not found"; exit 1; }

# Check if there are uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  Found uncommitted changes. Stashing them..."
    git stash save "Local changes before merge $(date +%Y-%m-%d_%H-%M-%S)"
fi

# Try to abort any ongoing merge
git merge --abort 2>/dev/null || echo "No merge in progress"

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
# Try pull with merge strategy
git pull origin main || {
    echo "⚠️  Merge conflict detected. Attempting to resolve..."
    
    # Check which files have conflicts
    CONFLICTED_FILES=$(git diff --name-only --diff-filter=U)
    
    if echo "$CONFLICTED_FILES" | grep -q "app/__init__.py"; then
        echo "🔧 Resolving conflict in app/__init__.py..."
        # Accept remote version (our fixes are in remote)
        git checkout --theirs app/__init__.py
        git add app/__init__.py
    fi
    
    # Complete the merge
    git commit -m "Merge origin/main - resolved conflicts" || {
        echo "❌ Failed to complete merge. Manual intervention needed."
        echo "Conflicted files:"
        git diff --name-only --diff-filter=U
        exit 1
    }
}

echo "✅ Successfully merged changes!"
echo "📋 Recent commits:"
git log --oneline -5

