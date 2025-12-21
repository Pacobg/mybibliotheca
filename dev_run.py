"""
Development server entry point for KuzuDB compatibility.

This script runs Flask development server WITHOUT reloader to avoid
KuzuDB lock conflicts. The reloader creates two processes (parent + child)
which both try to access KuzuDB, causing "Could not set lock on file" errors.

Usage:
    python dev_run.py
"""

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import triggers preflight side-effect (safe no-op if nothing to change)
from app.startup import schema_preflight  # noqa: F401

from app import create_app

app = create_app()

if __name__ == '__main__':
    import os
    
    # Development mode: Use Flask dev server WITHOUT reloader
    # This prevents KuzuDB lock conflicts caused by Flask's reloader
    # creating multiple processes
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5054))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    print("🚀 Starting Flask development server (no reloader for KuzuDB compatibility)...")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Debug: {debug}")
    print("   ⚠️  Note: Auto-reload is disabled to prevent KuzuDB lock conflicts")
    print("   💡 Restart manually after code changes (Ctrl+C and run again)")
    
    # CRITICAL: use_reloader=False prevents multiple processes accessing KuzuDB
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,  # Disable reloader to prevent KuzuDB lock conflicts
        use_debugger=debug   # Keep debugger enabled for error inspection
    )

