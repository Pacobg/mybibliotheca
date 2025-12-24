# Perplexity AI Enrichment - Setup Guide

## 🎯 Overview

Този модул използва Perplexity AI за автоматично обогатяване на метаданни за български книги чрез търсене в интернет.

**Features:**
- ✅ AI-powered web search за български книги
- ✅ Автоматично намиране на корици
- ✅ Извличане на описания, ISBN, издателства
- ✅ Source citations (verifiable sources)
- ✅ Batch processing с progress tracking
- ✅ Quality scoring на резултатите
- ✅ Cost-effective (~$0.0008 per book)

---

## 📋 Prerequisites

### 1. Perplexity API Key

**Get API Key:**
1. Visit: https://www.perplexity.ai/settings/api
2. Create account (free to start)
3. Generate API key
4. Copy key (starts with `pplx-`)

**Pricing:**
- Model: `llama-3.1-sonar-large-128k-online`
- Cost: $1 per 1M tokens
- Average: ~$0.0008 per book
- 373 books: ~$0.30 total

### 2. Install Dependencies

```bash
pip install httpx
```

The `httpx` package has been added to `requirements.txt`.

---

## 🚀 Setup

### Step 1: Add API Key to .env

```bash
# Edit .env file
nano .env

# Add these lines:
# Perplexity AI Configuration
PERPLEXITY_API_KEY=pplx-your-api-key-here

# Enrichment Settings (optional)
AI_ENRICHMENT_ENABLED=true
AI_ENRICHMENT_MIN_QUALITY=0.7
AI_ENRICHMENT_RATE_LIMIT=1.0
AI_COVER_DOWNLOAD=true
```

### Step 2: Test the Integration

```bash
# Test with sample books
python scripts/test_enrichment.py
```

**Expected output:**
```
========================================
Testing: Измамници - Катрин Каултър
========================================

✅ SUCCESS!
Quality Score: 0.88

Metadata:
{
  "title": "Измамници",
  "author": "Катрин Каултър",
  "publisher": "Бард",
  "year": "2002",
  "isbn": "954-585-341-7",
  ...
}
```

---

## 📖 Usage

### Option 1: Command Line (Recommended for Batch)

```bash
# Enrich all books missing metadata
python scripts/enrich_books.py

# Enrich first 50 books
python scripts/enrich_books.py --limit 50

# Force re-enrichment of all books
python scripts/enrich_books.py --force

# Dry run (see what would be done)
python scripts/enrich_books.py --dry-run --limit 10

# With custom quality threshold
python scripts/enrich_books.py --quality-min 0.8

# Skip confirmation
python scripts/enrich_books.py --limit 100 -y
```

### Option 2: Python API

```python
from app.services.enrichment_service import EnrichmentService
import asyncio

async def enrich_books():
    # Initialize service
    service = EnrichmentService()
    
    # Get books from database
    books = [
        {
            "id": "book-id-123",
            "title": "Измамници",
            "author": "Катрин Каултър",
            "description": None,
            "cover_url": None
        }
    ]
    
    # Enrich batch
    stats = await service.enrich_batch(books)
    
    print(f"Enriched: {stats['enriched']}/{stats['total']}")
    print(f"Covers found: {stats['covers_found']}")
    
    # Cleanup
    await service.close()

# Run
asyncio.run(enrich_books())
```

---

## 📊 Expected Results

### For Your Books Without Metadata:

**Enrichment Coverage:**
```
Starting: 373 books (36% of total)

Expected Results:
├── Enriched: ~300-340 books (80-90%)
├── Covers found: ~240-280 covers (65-75%)
├── Descriptions: ~270-310 descriptions (72-83%)
├── ISBN added: ~230-270 ISBNs (62-72%)
└── Failed: ~30-70 books (8-19%)
```

**Processing Time:**
```
Rate: ~30-40 books/hour (with 1s rate limit)
Total: ~9-12 hours for all 373 books

Or run in batches:
- Batch 1: 100 books (~2.5 hours)
- Batch 2: 100 books (~2.5 hours)
- Batch 3: 100 books (~2.5 hours)
- Batch 4: 73 books (~2 hours)
```

**Cost:**
```
Per book: ~$0.0008
Total: 373 × $0.0008 = ~$0.30

Very affordable! 💰
```

---

## 🔧 Configuration Options

### Environment Variables

```bash
# Required
PERPLEXITY_API_KEY=pplx-xxxxx        # Your API key

# Optional (with defaults)
AI_ENRICHMENT_MIN_QUALITY=0.7        # Minimum quality score (0.0-1.0)
AI_ENRICHMENT_RATE_LIMIT=1.0         # Seconds between requests
AI_COVER_DOWNLOAD=true               # Download covers (true/false)
```

### Quality Thresholds

**Quality Score Components:**
- Title: 0.20
- Author: 0.20
- Description (50+ chars): 0.20
- Publisher: 0.10
- ISBN: 0.10
- Cover URL: 0.10
- Year: 0.03
- Pages: 0.03
- Genres: 0.04

**Recommended Thresholds:**
- `0.7` - Balanced (default) ⭐
- `0.6` - More lenient (more results, lower quality)
- `0.8` - Strict (fewer results, higher quality)

---

## 🐛 Troubleshooting

### Issue 1: API Key Error

**Error:**
```
❌ PERPLEXITY_API_KEY not set!
```

**Solution:**
```bash
# Check if key is in .env
grep PERPLEXITY_API_KEY .env

# Add if missing
echo "PERPLEXITY_API_KEY=pplx-your-key" >> .env

# Restart server
python dev_run.py
```

### Issue 2: No Results Found

**Error:**
```
⚠️  Could not parse metadata for: Book Title
```

**Possible causes:**
1. Book is very obscure (not in web sources)
2. Title/author spelling is incorrect
3. Book is foreign original (not Bulgarian edition)

**Solutions:**
- Try with ISBN if available
- Check title/author spelling
- Lower quality threshold: `--quality-min 0.6`

### Issue 3: Rate Limiting

**Error:**
```
HTTP 429: Too Many Requests
```

**Solution:**
```bash
# Increase rate limit delay
# In .env:
AI_ENRICHMENT_RATE_LIMIT=2.0  # 2 seconds between requests
```

---

## 📈 Performance Optimization

### Faster Processing

```python
# Reduce rate limit (risky)
AI_ENRICHMENT_RATE_LIMIT=0.5

# Use smaller model (faster, cheaper, slightly lower quality)
enricher = PerplexityEnricher(
    api_key=key,
    model=PerplexityEnricher.MODEL_SMALL
)
```

### Batch Processing

```bash
# Process in smaller batches
python scripts/enrich_books.py --limit 100

# Run multiple batches
for i in {1..4}; do
    python scripts/enrich_books.py --limit 100 -y
    sleep 60  # 1 minute break between batches
done
```

---

## 🎓 Best Practices

### 1. Start Small

```bash
# Test with 10 books first
python scripts/enrich_books.py --limit 10 -y

# Check results
# If good, scale up to 50
python scripts/enrich_books.py --limit 50 -y

# Then full run
python scripts/enrich_books.py -y
```

### 2. Monitor Quality

After enrichment, check the quality scores in the logs. Books with quality < 0.7 are rejected by default.

### 3. Verify Sources

The enrichment service includes source citations for each enriched book. Check these to verify accuracy.

---

## 📞 Support

**Issues:**
- Check logs: `enrichment.log`
- Enable debug logging: `logging.DEBUG`
- Test with single book first

**Questions:**
- Review code comments
- Check API docs: https://docs.perplexity.ai
- Test in dry-run mode

---

## 🎉 Success Criteria

Your enrichment is successful if:

- ✅ 80%+ enrichment rate
- ✅ Quality scores > 0.7
- ✅ Cover URLs accessible
- ✅ Descriptions in Bulgarian
- ✅ Sources cited (verifiable)
- ✅ Cost under $0.50

**Expected final state:**
```
Total books: 1035
Fully enriched: 1000+ (97%+)
Missing data: < 35 books (3%)
```

---

**Ready to start enriching! 🚀📚**

