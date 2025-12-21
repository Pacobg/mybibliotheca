#!/usr/bin/env python3
"""
Test script for Biblioman database connection.
Usage: python scripts/test_biblioman_connection.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import mysql.connector
except ImportError:
    print("❌ mysql-connector-python is not installed.")
    print("Install it with: pip install mysql-connector-python")
    sys.exit(1)

def test_connection():
    """Test connection to Biblioman database."""
    # Get connection details from environment variables or use defaults
    config = {
        'host': os.getenv('BIBLIOMAN_HOST', '192.168.1.13'),
        'port': int(os.getenv('BIBLIOMAN_PORT', '3307')),
        'user': os.getenv('BIBLIOMAN_USER', 'root'),
        'password': os.getenv('BIBLIOMAN_PASSWORD', 'L3mongate189'),
        'database': os.getenv('BIBLIOMAN_DATABASE', 'biblioman'),
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci',
    }
    
    print("🔍 Testing Biblioman database connection...")
    print(f"   Host: {config['host']}:{config['port']}")
    print(f"   User: {config['user']}")
    print(f"   Database: {config['database']}")
    print()
    
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        # First, check what databases exist
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]
        print(f"📂 Available databases: {', '.join(databases)}")
        
        # Check if biblioman database exists
        if config['database'] not in databases:
            print(f"\n⚠️  Database '{config['database']}' not found!")
            print(f"   Available databases: {', '.join(databases)}")
            cursor.close()
            conn.close()
            return False
        
        # Check what tables exist in biblioman database
        cursor.execute(f"USE {config['database']}")
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        print(f"\n📋 Tables in '{config['database']}' database: {', '.join(tables)}")
        
        # Check if 'book' table exists
        if 'book' not in tables:
            print(f"\n⚠️  Table 'book' not found in '{config['database']}' database!")
            print(f"   Available tables: {', '.join(tables)}")
            cursor.close()
            conn.close()
            return False
        
        # Test 1: Count books
        cursor.execute("SELECT COUNT(*) FROM book")
        count = cursor.fetchone()[0]
        print(f"\n✅ Connection successful!")
        print(f"   Found {count:,} books in biblioman database.")
        
        # Test 2: Get a sample book with Cyrillic title
        cursor.execute("SELECT title, author, isbn FROM book WHERE title LIKE '%море%' LIMIT 3")
        books = cursor.fetchall()
        
        if books:
            print(f"\n📚 Sample books with 'море' in title:")
            for i, (title, author, isbn) in enumerate(books, 1):
                print(f"   {i}. {title} - {author} (ISBN: {isbn})")
        else:
            print("\n⚠️  No books found with 'море' in title")
        
        # Test 3: Check if chitanka_id exists (if column exists)
        try:
            cursor.execute("SELECT COUNT(*) FROM book WHERE chitanka_id IS NOT NULL")
            chitanka_count = cursor.fetchone()[0]
            print(f"\n📖 Books with Chitanka ID: {chitanka_count:,}")
        except mysql.connector.Error:
            print("\n⚠️  Column 'chitanka_id' not found in 'book' table")
        
        cursor.close()
        conn.close()
        
        print("\n✅ All tests passed! Biblioman connection is working correctly.")
        return True
        
    except mysql.connector.Error as e:
        print(f"❌ MariaDB connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_connection()
    sys.exit(0 if success else 1)

