#!/usr/bin/env python3
"""
MyBibliotheca Dev Script: Clear All Books
==========================================

⚠️  WARNING: This script will DELETE ALL BOOKS from the database!
This should ONLY be used in development/testing environments.

This script:
- Deletes all Book nodes and their relationships
- Preserves Users, Locations, Categories, Series, and other metadata
- Requires explicit confirmation
- Only works in development mode (FLASK_ENV=development or DEBUG=True)
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_dev_mode(force=False):
    """Check if we're in development mode"""
    if force:
        return True
    
    flask_env = os.getenv('FLASK_ENV', '').lower()
    flask_debug = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'on', 'yes')
    mybibliotheca_debug = os.getenv('MYBIBLIOTHECA_DEBUG', '').lower() in ('1', 'true', 'on', 'yes')
    
    # Check config if available
    try:
        from config import Config
        is_dev = (
            flask_env == 'development' or 
            flask_debug or 
            mybibliotheca_debug or
            (hasattr(Config, 'DEBUG') and Config.DEBUG) or
            (hasattr(Config, 'DEBUG_MODE') and Config.DEBUG_MODE) or
            (hasattr(Config, 'FLASK_ENV') and Config.FLASK_ENV == 'development')
        )
    except:
        is_dev = flask_env == 'development' or flask_debug or mybibliotheca_debug
    
    return is_dev

def get_book_count():
    """Get total number of books in the database"""
    try:
        from app.infrastructure.kuzu_graph import safe_execute_kuzu_query
        from app.utils.kuzu_async_helper import run_async
        
        query = "MATCH (b:Book) RETURN COUNT(b) as count"
        result = safe_execute_kuzu_query(query, {})
        
        # Convert result to list
        if hasattr(result, 'has_next') and result.has_next():
            row = result.get_next()
            if isinstance(row, (list, tuple)) and row:
                return int(row[0])
            elif isinstance(row, dict):
                return int(row.get('count') or row.get('col_0') or 0)
        elif isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict):
                return int(first.get('count') or first.get('col_0') or 0)
            elif isinstance(first, (list, tuple)) and first:
                return int(first[0])
        
        return 0
    except Exception as e:
        print(f"❌ Error getting book count: {e}")
        return None

def delete_all_books():
    """Delete all books from the database"""
    try:
        from app.infrastructure.kuzu_graph import safe_execute_kuzu_query
        
        print("🗑️  Deleting all books...")
        
        # Delete all books and their relationships using DETACH DELETE
        # This will automatically remove all relationships (AUTHORED, CATEGORIZED_AS, etc.)
        query = """
        MATCH (b:Book)
        DETACH DELETE b
        """
        
        result = safe_execute_kuzu_query(query, {})
        
        print("✅ All books have been deleted successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting books: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clear all books from the database (dev only)')
    parser.add_argument('--force', action='store_true', 
                       help='Force execution even if not in development mode (USE WITH CAUTION!)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("MyBibliotheca - Clear All Books (Dev Script)")
    print("=" * 60)
    print()
    
    # Check if we're in development mode
    if not check_dev_mode(force=args.force):
        print("❌ ERROR: This script can only be run in development mode!")
        print()
        print("To enable development mode, set one of:")
        print("  - FLASK_ENV=development")
        print("  - FLASK_DEBUG=1")
        print("  - MYBIBLIOTHECA_DEBUG=1")
        print()
        print("Or use --force flag (USE WITH CAUTION!):")
        print("  python scripts/clear_all_books.py --force")
        print()
        sys.exit(1)
    
    if args.force:
        print("⚠️  WARNING: Running with --force flag!")
        print("   This bypasses development mode check.")
        print()
    
    print("✅ Development mode detected")
    print()
    
    # Get book count
    print("📊 Checking database...")
    book_count = get_book_count()
    
    if book_count is None:
        print("❌ Failed to connect to database")
        sys.exit(1)
    
    if book_count == 0:
        print("ℹ️  No books found in the database. Nothing to delete.")
        sys.exit(0)
    
    print(f"📚 Found {book_count} book(s) in the database")
    print()
    
    # Warning
    print("⚠️  WARNING: This will DELETE ALL BOOKS from the database!")
    print("   This action cannot be undone!")
    print()
    print("The following will be deleted:")
    print("  - All Book nodes")
    print("  - All book relationships (AUTHORED, CATEGORIZED_AS, etc.)")
    print("  - All personal metadata (HAS_PERSONAL_METADATA)")
    print("  - All reading logs associated with books")
    print()
    print("The following will be PRESERVED:")
    print("  - Users")
    print("  - Locations")
    print("  - Categories (but book associations will be removed)")
    print("  - Series (but book associations will be removed)")
    print("  - People/Authors (but book associations will be removed)")
    print("  - Publishers")
    print()
    
    # Confirmation
    confirmation = input("Type 'DELETE ALL BOOKS' to confirm: ")
    
    if confirmation != 'DELETE ALL BOOKS':
        print("❌ Confirmation failed. Aborting.")
        sys.exit(0)
    
    print()
    print("🗑️  Proceeding with deletion...")
    print()
    
    # Delete all books
    success = delete_all_books()
    
    if success:
        # Verify deletion
        remaining = get_book_count()
        if remaining == 0:
            print()
            print("✅ Success! All books have been deleted.")
            print(f"   Remaining books: {remaining}")
        else:
            print()
            print(f"⚠️  Warning: {remaining} book(s) still remain in the database.")
            print("   The deletion may not have completed successfully.")
    else:
        print()
        print("❌ Failed to delete all books. Check the error messages above.")
        sys.exit(1)

if __name__ == '__main__':
    main()

