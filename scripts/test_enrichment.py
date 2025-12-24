#!/usr/bin/env python3
"""
Quick Test Script for Perplexity Enrichment
Tests basic functionality with sample books

Usage:
    python scripts/test_enrichment.py

Requirements:
    - PERPLEXITY_API_KEY in environment or .env file
    - httpx installed: pip install httpx
"""

import os
import sys
import asyncio
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to load from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed, using environment variables only")

# Check for API key
API_KEY = os.getenv('PERPLEXITY_API_KEY')
if not API_KEY:
    print("❌ Error: PERPLEXITY_API_KEY not found!")
    print("\n📝 Please set your API key:")
    print("   1. Get key from: https://www.perplexity.ai/settings/api")
    print("   2. Add to .env file: PERPLEXITY_API_KEY=pplx-xxxxx")
    print("   3. Or export: export PERPLEXITY_API_KEY=pplx-xxxxx")
    sys.exit(1)

# Import enricher
try:
    from app.services.metadata_providers.perplexity import PerplexityEnricher
except ImportError as e:
    print(f"❌ Error: Cannot import PerplexityEnricher: {e}")
    print("   Make sure you're running from the project root")
    sys.exit(1)


# Test books (mix of known and obscure)
TEST_BOOKS = [
    {
        "title": "Измамници",
        "author": "Катрин Каултър",
        "expected_publisher": "Бард",
        "difficulty": "easy"
    },
    {
        "title": "Адвокатът с линкълна",
        "author": "Майкъл Конъли",
        "expected_publisher": None,
        "difficulty": "medium"
    },
    {
        "title": "Кули от камък и кост",
        "author": "Емил Минчев",
        "expected_publisher": None,
        "difficulty": "medium"
    }
]


async def test_basic_enrichment():
    """Test basic enrichment functionality"""
    
    print("="*70)
    print("PERPLEXITY ENRICHMENT - QUICK TEST")
    print("="*70)
    print(f"API Key: {API_KEY[:10]}...")
    print(f"Test books: {len(TEST_BOOKS)}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Initialize enricher
    enricher = PerplexityEnricher(api_key=API_KEY)
    print("✅ Enricher initialized")
    
    results = {
        'total': len(TEST_BOOKS),
        'success': 0,
        'failed': 0,
        'quality_scores': [],
        'covers_found': 0,
        'descriptions_found': 0
    }
    
    # Test each book
    for i, book in enumerate(TEST_BOOKS, 1):
        print(f"\n{'-'*70}")
        print(f"Test {i}/{len(TEST_BOOKS)}: {book['title']}")
        print(f"Author: {book['author']}")
        print(f"Difficulty: {book['difficulty']}")
        print(f"{'-'*70}")
        
        try:
            # Enrich book
            metadata = await enricher.enrich_book(
                title=book['title'],
                author=book['author']
            )
            
            if metadata:
                results['success'] += 1
                
                # Extract info
                quality = metadata.get('quality_score', 0)
                results['quality_scores'].append(quality)
                
                print(f"\n✅ SUCCESS!")
                print(f"   Quality Score: {quality:.2f}")
                
                # Check fields
                if metadata.get('title'):
                    print(f"   📖 Title: {metadata['title']}")
                
                if metadata.get('author'):
                    print(f"   ✍️  Author: {metadata['author']}")
                
                if metadata.get('publisher'):
                    print(f"   🏢 Publisher: {metadata['publisher']}")
                    if book['expected_publisher']:
                        match = book['expected_publisher'].lower() in metadata['publisher'].lower()
                        print(f"      Expected match: {'✅' if match else '❌'}")
                
                if metadata.get('year'):
                    print(f"   📅 Year: {metadata['year']}")
                
                if metadata.get('isbn'):
                    print(f"   🔢 ISBN: {metadata['isbn']}")
                
                if metadata.get('pages'):
                    print(f"   📄 Pages: {metadata['pages']}")
                
                if metadata.get('description'):
                    results['descriptions_found'] += 1
                    desc = metadata['description'][:100]
                    print(f"   📝 Description: {desc}...")
                
                if metadata.get('cover_url'):
                    results['covers_found'] += 1
                    cover = metadata['cover_url']
                    print(f"   🖼️  Cover: {cover[:60]}...")
                
                if metadata.get('genres'):
                    genres = ', '.join(metadata['genres'][:3])
                    print(f"   🏷️  Genres: {genres}")
                
                if metadata.get('sources'):
                    print(f"   🔗 Sources: {len(metadata['sources'])} cited")
                    for source in metadata['sources'][:2]:
                        print(f"      - {source[:60]}...")
                
                # Save detailed results
                filename = f"test_result_{i}_{book['title'].replace(' ', '_')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                print(f"\n   💾 Full results saved to: {filename}")
                
            else:
                results['failed'] += 1
                print(f"\n❌ FAILED - No metadata found")
            
            # Rate limiting
            if i < len(TEST_BOOKS):
                print(f"\n⏳ Waiting 2 seconds...")
                await asyncio.sleep(2)
            
        except Exception as e:
            results['failed'] += 1
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Close enricher
    await enricher.close()
    
    # Show summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    
    print(f"\n📊 Results:")
    print(f"   Total tests: {results['total']}")
    print(f"   Successful: {results['success']}")
    print(f"   Failed: {results['failed']}")
    print(f"   Success rate: {results['success']/results['total']*100:.1f}%")
    
    if results['quality_scores']:
        avg_quality = sum(results['quality_scores']) / len(results['quality_scores'])
        print(f"\n⭐ Quality:")
        print(f"   Average: {avg_quality:.2f}")
        print(f"   Min: {min(results['quality_scores']):.2f}")
        print(f"   Max: {max(results['quality_scores']):.2f}")
    
    print(f"\n📝 Content:")
    print(f"   Covers found: {results['covers_found']}/{results['success']}")
    print(f"   Descriptions: {results['descriptions_found']}/{results['success']}")
    
    # Cost estimate
    cost = results['total'] * 0.0008
    print(f"\n💰 Estimated cost: ${cost:.4f}")
    
    # Verdict
    print(f"\n{'='*70}")
    if results['success'] == results['total']:
        print("✅ ALL TESTS PASSED!")
        print("\nYou're ready to enrich your books!")
        print("Run: python scripts/enrich_books.py --limit 50")
    elif results['success'] > 0:
        print("⚠️  PARTIAL SUCCESS")
        print(f"\n{results['success']}/{results['total']} tests passed")
        print("Review failed tests and try again")
    else:
        print("❌ ALL TESTS FAILED")
        print("\nCheck:")
        print("  1. API key is correct")
        print("  2. Internet connection working")
        print("  3. Perplexity API is accessible")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Check dependencies
    try:
        import httpx
    except ImportError:
        print("❌ Error: httpx not installed")
        print("   Install: pip install httpx")
        sys.exit(1)
    
    # Run tests
    try:
        asyncio.run(test_basic_enrichment())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

