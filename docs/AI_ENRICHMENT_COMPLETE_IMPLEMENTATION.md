# AI Enrichment Service - Пълна имплементация

## Общ преглед

Този документ описва пълната интеграция на AI обогатяване на метаданни за книги в MyBibliotheca системата. Системата поддържа три AI провайдъра: **Perplexity AI** (с web search), **OpenAI**, и **Ollama** (local LLM). Услугата автоматично търси информация в интернет за български и английски книги, намира корици, извлича описания, ISBN номера, издателства и друга метаинформация.

**Дата на имплементация:** 24 декември 2025

---

## Съдържание

1. [Основни компоненти](#основни-компоненти)
2. [AI провайдъри](#ai-провайдъри)
3. [Функционалности](#функционалности)
4. [UI интеграция](#ui-интеграция)
5. [Cover management](#cover-management)
6. [Езикова поддръжка](#езикова-поддръжка)
7. [Използване](#използване)
8. [Технически детайли](#технически-детайли)
9. [Решени проблеми](#решени-проблеми)

---

## Основни компоненти

### 1. PerplexityEnricher (`app/services/metadata_providers/perplexity.py`)

Основният клас за взаимодействие с Perplexity AI API за web search и metadata extraction.

**Основни методи:**
- `async def enrich_book()` - Извлича метаданни за книга
- `async def find_cover_image()` - Търси корица за книга
- `_build_metadata_query()` - Конструира заявка към AI според езика на заглавието
- `_parse_response()` - Парсва JSON отговор от AI
- `_extract_image_url()` - Извлича URL на корица от AI отговор

**Ключови характеристики:**
- Автоматично определяне на езика на книгата (български/английски) според заглавието
- Различни заявки за български и английски книги
- Нормализация на автори (един основен автор, предпочитане на кирилица за български книги)
- Валидация на качеството на метаданните
- Специфични заявки за български книжарници (ciela.com, helikon.bg, ozone.bg, hermesbooks.bg, и др.)

### 2. OpenAIEricher (`app/services/metadata_providers/openai_enricher.py`)

Алтернативен enricher за OpenAI/Ollama провайдъри.

**Особености:**
- Използва съществуващия `AIService` за API calls
- Ограничени възможности (няма web search)
- Не може да търси корици в интернет
- Полезен за text-based metadata extraction от съществуващи данни

### 3. EnrichmentService (`app/services/enrichment_service.py`)

Оркестратор за процеса на обогатяване.

**Основни методи:**
- `async def enrich_single_book()` - Обогатява една книга
- `async def enrich_batch()` - Обогатява множество книги
- `merge_metadata_into_book()` - Слива AI метаданни с съществуващи данни
- `_has_sufficient_data()` - Проверява дали книгата има достатъчно данни

**Ключови характеристики:**
- Динамична инициализация на AI провайдър (Perplexity/OpenAI/Ollama)
- Fallback логика: ако Perplexity fail-не, опитва OpenAI/Ollama
- Проверка на езика на описанието спрямо езика на заглавието
- Отхвърляне на описания, които не съответстват на езика на заглавието
- Поддръжка на `require_cover` флаг за търсене само на корици
- Валидация на local covers (проверка за съществуване и размер)

### 4. EnrichmentCommand (`scripts/enrich_books.py`)

Команден ред скрипт за batch обогатяване.

**Основни функции:**
- `_get_books_to_enrich()` - Намира книги за обогатяване
- `_save_enriched_books()` - Запазва обогатените книги в базата данни
- `_progress_callback()` - Callback за проследяване на прогрес
- `run()` - Главна функция за изпълнение

**Command-line аргументи:**
- `--limit N` - Ограничава броя книги за обогатяване
- `--no-cover-only` - Обогатява само книги без валидни корици
- `--force` - Принудително обогатяване (игнорира `_has_sufficient_data`)
- `--book-title "Title"` - Обогатява конкретна книга по заглавие
- `--book-id UUID` - Обогатява конкретна книга по ID
- `--quality-min 0.3` - Минимален quality score (0.0-1.0)
- `--dry-run` - Показва какво ще се обогати без да прави промени
- `-y` - Автоматично потвърждение (без интерактивни промптове)

**Ключови характеристики:**
- Валидация на cover URLs (http/https, image extensions, cache URL detection)
- Проверка за accessibility на cover URLs (HEAD request, content-type)
- Local cover caching (download и запазване в `/data/covers/`)
- Fallback механизъм за cover images (Perplexity → Google Books → OpenLibrary → Bulgarian bookstores)
- Image size validation (филтрира placeholder images < 1KB)
- Enrichment tracking (`last_enriched_at`, `enriched_by` в `custom_metadata`)
- Статистики и reporting (`enrichment_status.json`)

---

## AI провайдъри

### Perplexity AI (Препоръчан)

**Предимства:**
- ✅ Web search за намиране на актуална информация
- ✅ Търсене на корици в интернет
- ✅ Намиране на ISBN, издателства, описания
- ✅ Поддръжка на български и английски език
- ✅ Високо качество на метаданните

**Модели:**
- `sonar-pro` (Препоръчан) - Най-добро качество
- `sonar-deep-research` - За по-сложни заявки
- `llama-3.1-70b-instruct` - Алтернатива

**Конфигурация:**
```python
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_MODEL=sonar-pro
```

### OpenAI

**Ограничения:**
- ❌ Няма web search
- ❌ Не може да търси корици в интернет
- ✅ Добро за text-based extraction

**Конфигурация:**
```python
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

### Ollama (Local LLM)

**Ограничения:**
- ❌ Няма web search
- ❌ Не може да търси корици в интернет
- ✅ Работи локално (без API ключове)
- ✅ Безплатно

**Конфигурация:**
```python
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2-vision:11b
```

---

## Функционалности

### 1. Автоматично обогатяване на метаданни

Системата автоматично:
- Намира описания на книгите
- Търси корици от множество източници
- Извлича ISBN номера
- Намира издателства
- Определя година на публикуване
- Добавя жанрове

### 2. Cover Management

**Local Cover Caching:**
- Download-ва remote cover images
- Запазва ги локално в `/data/covers/`
- Генерира уникални имена (UUID)
- Обновява `cover_url` в базата данни с local path

**Fallback механизъм:**
1. Perplexity-provided URL
2. Google Books API
3. Open Library API
4. Bulgarian bookstores (за български книги):
   - ciela.com
   - ozone.bg
   - helikon.bg
   - hermesbooks.bg
   - book.store.bg
   - knigabg.com
   - booktrading.bg
   - chitanka.info

**Валидация:**
- Проверка за accessibility (HEAD request)
- Content-type validation (трябва да е image)
- Image size validation (филтрира < 1KB placeholder images)
- Cache URL detection (отхвърля счупени cache URLs)

### 3. Езикова поддръжка

**Автоматично определяне на езика:**
- Български книги: заглавия с кирилица → `language = 'bg'`
- Английски книги: заглавия с латиница → `language = 'en'`

**Езикова валидация:**
- Описания трябва да съответстват на езика на заглавието
- Автори трябва да съответстват на езика на заглавието
- Отхвърляне на некоректни езикови комбинации

**Нормализация на автори:**
- За български книги: предпочитане на кирилица
- За английски книги: предпочитане на латиница
- Един основен автор (отстраняване на множествени автори)

### 4. Quality Scoring

Системата оценява качеството на обогатените метаданни:
- `0.0` - Няма данни
- `0.3` - Минимални данни (по подразбиране)
- `0.7` - Добри данни
- `1.0` - Отлични данни (всички полета попълнени)

### 5. Enrichment Tracking

Системата проследява кои книги са обогатени:
- `last_enriched_at` - Timestamp на последното обогатяване
- `enriched_by` - Източник на обогатяване (perplexity/openai/ollama)
- Автоматично пропускане на книги обогатени в последните 24 часа

---

## UI интеграция

### AI Settings Page (`/auth/settings`)

**Нови функционалности:**
- Dropdown за избор на AI провайдър (OpenAI/Ollama/Perplexity)
- Perplexity конфигурация (API Key, Model)
- Обяснения за ограниченията на всеки провайдър
- Test connection бутон за всеки провайдър

**Файлове:**
- `app/templates/settings/partials/server_ai.html`
- `app/auth.py` (save_ai_settings)
- `app/admin.py` (load_ai_config)

### Metadata Management Page (`/metadata/`)

**Нова секция "Обогатяване с AI":**
- Показва дали Perplexity е активен
- Бутон за стартиране на обогатяване
- Опции за конфигурация:
  - Лимит книги (1-100)
  - Force опция (обогатява дори книги с covers)
- Real-time статус на обогатяването
- Детайли за обогатени и пропуснати книги

**Файлове:**
- `app/templates/metadata/index.html`
- `app/metadata_routes.py` (start_enrichment, get_enrichment_status)

**API endpoints:**
- `POST /metadata/enrichment/start` - Стартира обогатяване
- `GET /metadata/enrichment/status` - Връща статус на обогатяване

---

## Cover Management

### Local Cover Caching

**Защо?**
- Външните URL-и могат да станат недостъпни (404, 403)
- По-бързо зареждане (локални файлове)
- Надеждност (не зависи от външни услуги)

**Как работи:**
1. Системата намира cover URL от AI или fallback източници
2. Проверява accessibility (HEAD request)
3. Download-ва изображението
4. Запазва го в `/data/covers/{uuid}.{ext}`
5. Обновява `cover_url` в базата данни с `/covers/{filename}`

**Файлове:**
- `scripts/enrich_books.py` (_save_enriched_books)
- `app/utils/image_processing.py` (get_covers_dir)

### Cover URL Validation

**Валидни cover URLs:**
- `http://` или `https://` URLs с image extensions (.jpg, .png, .webp, .gif)
- Local paths `/covers/{filename}` (ако файлът съществува и не е празен)

**Невалидни cover URLs:**
- Cache URLs без image extension в края
- Cache URLs с ISBN в пътя (подозрителни)
- Недостъпни URLs (404, 403, non-image content-type)
- Празни local files

**Код:**
```python
# Проверка за валиден cover URL
def is_valid_cover_url(url: str) -> bool:
    if not url:
        return False
    
    # Local covers
    if url.startswith('/covers/'):
        return check_local_cover_exists(url)
    
    # HTTP/HTTPS URLs
    if url.startswith('http://') or url.startswith('https://'):
        # Проверка за image extension
        if not has_image_extension(url):
            return False
        
        # Проверка за cache URLs
        if '/cache/' in url:
            # Трябва да завършва с image extension
            if not url.split('?')[0].endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return False
        
        # Проверка за accessibility
        return check_url_accessible(url)
    
    return False
```

---

## Езикова поддръжка

### Автоматично определяне на езика

**Български книги:**
- Заглавие съдържа кирилица → `language = 'bg'`
- Автор трябва да е на български (кирилица)
- Описание трябва да е на български (кирилица)
- Cover търсене в български книжарници

**Английски книги:**
- Заглавие съдържа само латиница → `language = 'en'`
- Автор трябва да е на английски (латиница)
- Описание трябва да е на английски (латиница)

### Езикова валидация

**Описания:**
```python
def should_update_description(title: str, existing_desc: str, new_desc: str) -> bool:
    title_has_cyrillic = bool(re.search(r'[\u0400-\u04FF]', title))
    desc_has_cyrillic = bool(re.search(r'[\u0400-\u04FF]', new_desc))
    
    # Езикът на описанието трябва да съответства на езика на заглавието
    if title_has_cyrillic != desc_has_cyrillic:
        return False  # Отхвърляне
    
    # ... други проверки ...
    return True
```

**Автори:**
```python
def should_update_author(title: str, existing_author: str, new_author: str) -> bool:
    title_has_cyrillic = bool(re.search(r'[\u0400-\u04FF]', title))
    author_has_cyrillic = bool(re.search(r'[\u0400-\u04FF]', new_author))
    
    # Езикът на автора трябва да съответства на езика на заглавието
    if title_has_cyrillic != author_has_cyrillic:
        return False  # Отхвърляне
    
    return True
```

---

## Използване

### От UI

1. Отидете на `/metadata/`
2. В секцията "Обогатяване с AI":
   - Задайте лимит книги (1-100)
   - Изберете дали да обогатите само книги без covers или всички (force)
   - Натиснете "Стартирай обогатяване"
3. Следете статуса в real-time

### От командния ред

**Обогатяване на книги без covers:**
```bash
python scripts/enrich_books.py --no-cover-only --limit 10 -y
```

**Принудително обогатяване:**
```bash
python scripts/enrich_books.py --force --limit 5 -y
```

**Обогатяване на конкретна книга:**
```bash
python scripts/enrich_books.py --book-title "13 за късмет" --force -y
```

**Dry run (без промени):**
```bash
python scripts/enrich_books.py --no-cover-only --limit 10 --dry-run
```

### Конфигурация

**Environment variables (.env):**
```bash
# Perplexity AI
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_MODEL=sonar-pro

# OpenAI (опционално)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# Ollama (опционално)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2-vision:11b

# AI Provider (perplexity/openai/ollama)
AI_PROVIDER=perplexity
```

**Или от UI:**
- Отидете на `/auth/settings`
- Попълнете AI настройките
- Запазете

---

## Технически детайли

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    UI (metadata/index.html)                │
│  - Стартира обогатяване                                     │
│  - Показва статус                                           │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              metadata_routes.py (Flask routes)               │
│  - POST /metadata/enrichment/start                          │
│  - GET /metadata/enrichment/status                          │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            scripts/enrich_books.py (EnrichmentCommand)      │
│  - Query книги от KuzuDB                                     │
│  - Филтриране по критерии                                   │
│  - Batch processing                                          │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         enrichment_service.py (EnrichmentService)            │
│  - Оркестрация на процеса                                   │
│  - Merge на метаданни                                        │
│  - Quality scoring                                           │
└────────────────────┬───────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│ PerplexityEnricher│   │ OpenAIEricher     │
│ - Web search      │   │ - Text extraction │
│ - Cover finding   │   │ - No web search   │
└──────────────────┘   └──────────────────┘
```

### KuzuDB Integration

**Query за книги:**
```cypher
MATCH (b:Book)
WHERE b.title IS NOT NULL
RETURN b.id, b.title, b.author, b.cover_url, b.description, ...
LIMIT 100
```

**Update на книга:**
```python
await book_service.update_book(book_id, updates={
    'description': '...',
    'cover_url': '/covers/uuid.jpg',
    'language': 'bg',
    ...
})
```

**Enrichment tracking:**
```python
custom_metadata = {
    'last_enriched_at': datetime.now().isoformat(),
    'enriched_by': 'perplexity'
}
updates['custom_metadata'] = json.dumps(custom_metadata)
```

### Error Handling

**KuzuDB Lock Conflicts:**
- Retry логика с exponential backoff
- Използване на threading вместо subprocess за споделяне на connection

**Flask Application Context:**
- Helper функции за path resolution без app context
- `_get_covers_base_dir_no_app_context()` за scripts

**API Errors:**
- Graceful degradation (fallback на други провайдъри)
- Detailed logging за debugging
- Status tracking в JSON файл

---

## Решени проблеми

### 1. Perplexity API Errors

**Проблем:** `400 Bad Request` с различни model names

**Решение:**
- Обновени model names: `sonar-pro`, `sonar-deep-research`, `llama-3.1-70b-instruct`
- Премахнати неподдържани параметри

### 2. KuzuDB Lock Conflicts

**Проблем:** `RuntimeError: IO exception: Could not set lock on file`

**Решение:**
- Използване на threading вместо subprocess
- Споделяне на KuzuDB connection в същия процес
- Retry логика с exponential backoff

### 3. Cover URL Validation

**Проблем:** Счупени cache URLs се маркират като валидни

**Решение:**
- Проверка за image extensions
- Detection на ISBN в cache URL paths
- Accessibility проверка (HEAD request)
- Content-type validation

### 4. Local Cover Caching

**Проблем:** Външни cover URLs стават недостъпни

**Решение:**
- Download и local caching в `/data/covers/`
- Fallback механизъм (Perplexity → Google Books → OpenLibrary → Bulgarian bookstores)
- Image size validation (филтрира placeholder images)

### 5. Flask Application Context

**Проблем:** `RuntimeError: Working outside of application context`

**Решение:**
- Helper функции за path resolution без app context
- `_get_covers_base_dir_no_app_context()` за scripts
- Проверка за app context преди използване на `current_app`

### 6. Езикова валидация

**Проблем:** Български описания за английски книги и обратно

**Решение:**
- Автоматично определяне на езика според заглавието
- Езикова валидация на описания и автори
- Отхвърляне на некоректни езикови комбинации

### 7. Description Citations

**Проблем:** Описания съдържат citation markers `[3][5][7]`

**Решение:**
- Regex cleanup: `re.sub(r'\[\d+\]', '', description)`
- Премахване на citation markers преди запазване

### 8. Author Normalization

**Проблем:** Множествени автори или неправилни имена

**Решение:**
- Нормализация в `PerplexityEnricher._parse_response()`
- Предпочитане на един основен автор
- Езикова валидация (кирилица за български, латиница за английски)

### 9. Enrichment Tracking

**Проблем:** Същите книги се обогатяват многократно

**Решение:**
- `last_enriched_at` и `enriched_by` в `custom_metadata`
- Автоматично пропускане на книги обогатени в последните 24 часа
- Force опция за принудително обогатяване

### 10. Cover Display

**Проблем:** Covers не се визуализират в UI

**Решение:**
- Правилна директория за covers (`/data/covers/`)
- Local path resolution без app context
- Проверка за съществуване и размер на local files

---

## Статистики и Reporting

### Enrichment Status File

**Локация:** `data/enrichment_status.json`

**Структура:**
```json
{
  "running": false,
  "started_at": "2025-12-24T23:29:41",
  "completed_at": "2025-12-24T23:29:55",
  "limit": 10,
  "no_cover_only": true,
  "force": false,
  "processed": 10,
  "enriched": 1,
  "failed": 0,
  "enriched_books": [
    {
      "id": "uuid",
      "title": "Book Title",
      "updated_fields": ["description", "cover_url", "language"]
    }
  ],
  "skipped_books": [
    {
      "id": "uuid",
      "title": "Book Title",
      "reason": "Already has a valid cover"
    }
  ]
}
```

### Logging

**Логове включват:**
- Стартиране и завършване на обогатяване
- Прогрес по книги
- Успешни и неуспешни обогатявания
- Cover download процес
- Езикова валидация
- Статистики в края

**Пример:**
```
2025-12-24 23:29:52,614 [INFO] ✅ Enriched: Book Title (quality: 1.00)
2025-12-24 23:29:54,871 [INFO] ✅ Cover downloaded and cached locally: /covers/uuid.jpg
2025-12-24 23:29:55,562 [INFO] 📊 Statistics: Books enriched: 1, Success rate: 100.0%
```

---

## Бъдещи подобрения

### Възможни разширения:

1. **Batch processing оптимизация:**
   - Паралелно обогатяване на множество книги
   - Rate limiting по провайдър

2. **Допълнителни източници:**
   - Goodreads API
   - LibraryThing API
   - Други български книжарници

3. **Advanced cover detection:**
   - OCR за ISBN от cover images
   - Image similarity matching

4. **Quality improvements:**
   - Machine learning за quality scoring
   - User feedback за обогатени метаданни

5. **Performance:**
   - Caching на AI отговори
   - Background jobs с Celery/Redis

---

## Заключение

AI Enrichment Service предоставя мощен и гъвкав механизъм за автоматично обогатяване на метаданни за книги. Системата поддържа множество AI провайдъри, автоматично определяне на езика, intelligent cover management, и comprehensive error handling. Интеграцията с UI позволява лесно управление и monitoring на процеса на обогатяване.

**Ключови постижения:**
- ✅ Пълна интеграция на Perplexity AI с web search
- ✅ Поддръжка на OpenAI и Ollama като алтернативи
- ✅ Local cover caching за надеждност
- ✅ Intelligent fallback механизъм за covers
- ✅ Езикова валидация и автоматично определяне
- ✅ UI интеграция за лесно управление
- ✅ Comprehensive tracking и reporting

---

**Дата на последна актуализация:** 24 декември 2025

