# Резюме на промените - Интернационализация и UI подобрения

## Общ преглед

Този документ описва подробно всички промени, направени за внедряване на интернационализация (i18n) и подобрения на потребителския интерфейс в MyBibliotheca приложението.

---

## 📋 Съдържание

1. [Интернационализация (i18n)](#интернационализация-i18n)
2. [Промени в навигацията](#промени-в-навигацията)
3. [Промени в layout и стилове](#промени-в-layout-и-стилове)
4. [Конфигурация на езици](#конфигурация-на-езици)
5. [Технически детайли](#технически-детайли)
6. [Инструкции за deployment](#инструкции-за-deployment)

---

## 🌐 Интернационализация (i18n)

### 1. Инсталация и конфигурация

#### Добавени зависимости
- **Flask-Babel>=4.0.0** в `requirements.txt`
- **Babel** (CLI инструмент за компилиране на преводи)

#### Конфигурация на Flask-Babel

**Файл: `app/__init__.py`**

```python
# Конфигурация на Babel
app.config['BABEL_TRANSLATION_DIRECTORIES'] = '../translations'
app.config['BABEL_DEFAULT_LOCALE'] = 'bg'  # Български по подразбиране
app.config['BABEL_DEFAULT_TIMEZONE'] = 'UTC'

# Функция за определяне на езика
def get_locale():
    # 1. Проверка за избран език в session
    if 'language' in session and session['language']:
        return session['language']
    
    # 2. Проверка на Accept-Language header от браузъра
    browser_lang = request.accept_languages.best_match(['bg', 'en']) or 'bg'
    return browser_lang

babel = Babel(app, locale_selector=get_locale)
```

#### Контекст процесор за templates

**Файл: `app/__init__.py`**

```python
@app.context_processor
def inject_gettext():
    """Прави функцията _() достъпна във всички templates."""
    if Babel is not None:
        from flask_babel import gettext
        return dict(_=gettext)
    else:
        def noop_gettext(text):
            return text
        return dict(_=noop_gettext)
```

### 2. Структура на преводите

#### Създадени директории
```
translations/
├── bg/
│   └── LC_MESSAGES/
│       ├── messages.po  (изходен файл с преводи)
│       └── messages.mo  (компилиран файл)
└── en/
    └── LC_MESSAGES/
        ├── messages.po
        └── messages.mo
```

#### Конфигурационен файл за Babel

**Файл: `babel.cfg`**

```ini
[python: **.py]
[jinja2: **/templates/**.html]
encoding = utf-8
```

### 3. Language Routes

**Файл: `app/routes/language_routes.py`**

Създаден нов blueprint за управление на езиците:

```python
@language_bp.route('/set_language/<language>')
def set_language(language):
    """Задава предпочитания език на потребителя."""
    supported_languages = ['en', 'bg']
    
    if language not in supported_languages:
        language = 'bg'  # Default to Bulgarian
    
    # Запазване в session
    session['language'] = language
    session.permanent = True
    session.modified = True
    
    # Редирект обратно с запазване на query параметри
    return redirect(...)
```

### 4. Български преводи

**Файл: `translations/bg/LC_MESSAGES/messages.po`**

Добавени над 100+ превода, включително:

- **Навигация**: Библиотека, Хора, Категории, Статистика, Дневник за четене
- **Действия**: Добави, Редактирай, Изтрий, Запази, Отказ
- **Форми**: Заглавие, Автор, Описание, ISBN, Издател
- **Статуси**: Прочетена, Четене, Искам да прочета, Не довършена
- **Съобщения**: Успешно, Грешка, Внимание, Информация
- **И много други...**

---

## 🎨 Промени в навигацията

### 1. User Dropdown Menu

**Файл: `app/templates/base.html`**

**Преди:**
```html
<span class="navbar-text">Добре дошли, pacovw</span>
<a href="...">Администрация</a>
<a href="...">Изход</a>
```

**След:**
```html
<li class="nav-item dropdown">
  <a class="nav-link nav-pill nav-ghost dropdown-toggle" 
     href="#" id="userDropdown" data-bs-toggle="dropdown">
    Добре дошли, <strong>pacovw</strong>
  </a>
  <ul class="dropdown-menu dropdown-menu-end">
    {% if current_user.is_admin %}
      <li><a class="dropdown-item" href="...">
        <i class="bi bi-shield-check"></i> Администрация
      </a></li>
      <li><hr class="dropdown-divider"></li>
    {% endif %}
    <li><a class="dropdown-item" href="...">
      <i class="bi bi-person-gear"></i> Потребител
    </a></li>
    <li><a class="dropdown-item" href="...">
      <i class="bi bi-box-arrow-right"></i> Изход
    </a></li>
  </ul>
</li>
```

**Предимства:**
- По-компактен layout
- По-добра организация на опциите
- Добавени икони за по-добра визуализация

### 2. Language Switcher

**Файл: `app/templates/base.html`**

**Преди:**
```html
<a href="...">
  <i class="bi bi-translate"></i>
  {% if session.get('language') == 'bg' %}
    Български
  {% else %}
    English
  {% endif %}
</a>
```

**След:**
```html
<li class="nav-item dropdown">
  <a class="nav-link nav-pill nav-ghost dropdown-toggle" 
     href="#" id="languageDropdown" data-bs-toggle="dropdown">
    {% if session.get('language') == 'bg' %}
      <span>🇧🇬</span>
    {% else %}
      <span>🇬🇧</span>
    {% endif %}
  </a>
  <ul class="dropdown-menu dropdown-menu-end">
    <li><a class="dropdown-item" href="...">
      <span>🇬🇧</span> English
    </a></li>
    <li><a class="dropdown-item" href="...">
      <span>🇧🇬</span> Български
    </a></li>
  </ul>
</li>
```

**Предимства:**
- По-компактен (само флаг в бутона)
- Визуално ясно показване на текущия език
- Dropdown менюто все още показва името на езика

### 3. Преместване на Locations

**Файл: `app/templates/base.html`**

**Преди:** Locations беше в dropdown менюто "Още"

**След:** Locations е отделен линк в основната навигация, след "Дневник за четене"

```html
<a class="nav-link nav-pill" href="{{ url_for('locations.manage_locations') }}">
  <i class="bi bi-geo-alt"></i> {{ _('Locations') }}
</a>
```

**Предимства:**
- По-лесен достъп до Locations
- По-добра видимост на важната функционалност

### 4. Центриране на Brand

**Файл: `app/templates/base.html`**

**Преди:**
```html
<a class="navbar-brand" href="...">{{ site_name }}</a>
```

**След:**
```html
<div class="container-fluid position-relative">
  <a class="navbar-brand position-absolute start-50 translate-middle-x" 
     href="..." 
     style="font-size: 1.5rem; font-weight: 600; z-index: 10;">
    {{ site_name }}
  </a>
  ...
</div>
```

**Промени:**
- **По-голям шрифт**: `font-size: 1.5rem` (вместо стандартния)
- **Центриран**: използва `position-absolute` с `start-50 translate-middle-x`
- **По-видим**: `font-weight: 600`
- **Z-index**: зададен за да е над другите елементи

---

## ⚙️ Конфигурация на езици

### 1. Език по подразбиране

**Файл: `app/__init__.py`**

```python
# Променено от 'en' на 'bg'
app.config['BABEL_DEFAULT_LOCALE'] = 'bg'

# Променен fallback от 'en' на 'bg'
browser_lang = request.accept_languages.best_match(['bg', 'en']) or 'bg'
```

**Файл: `app/templates/base.html`**

```html
<!-- Променено от 'en' на 'bg' -->
<html lang="{{ session.get('language', 'bg') }}" data-theme="{{ current_theme }}">
```

### 2. Поддържани езици

```python
supported_languages = ['en', 'bg']
```

### 3. Приоритет на езиците

1. **Избран език в session** (най-висок приоритет)
2. **Accept-Language header от браузъра**
3. **Български по подразбиране** (fallback)

---

## 🔧 Технически детайли

### 1. ETag Caching с Language Support

**Файл: `app/routes/book_routes.py`**

```python
# Включване на езика в ETag за да се избегне кеширане при смяна на език
current_language = session.get('language', 'bg')
_html_etag = f"W/\"libhtml:{...}:lang:{current_language}:v{_version}\""

# Добавяне на Vary header
resp.headers['Vary'] = 'Accept-Language, Cookie'
```

**Защо е важно:**
- Предотвратява показването на кеширана версия при смяна на език
- Информира браузъра, че съдържанието варира според езика

### 2. Session Management

**Файл: `app/routes/language_routes.py`**

```python
session['language'] = language
session.permanent = True  # Прави session-а персистентен
session.modified = True   # Явно маркиране като модифициран
```

**Защо е важно:**
- `session.modified = True` гарантира, че промените се запазват
- `session.permanent = True` прави session-а по-дълготраен

### 3. Redirect Logic

**Файл: `app/routes/language_routes.py`**

```python
# Редирект директно към book.library (избягва двойни редиректи)
target_url = url_for('book.library')

# Запазване на query параметри
if request.args:
    query_params = {k: v for k, v in request.args.items()}
    target_url = f"{target_url}?{urlencode(query_params, doseq=True)}"

return redirect(target_url)
```

**Защо е важно:**
- Избягва двойни редиректи (main.library → book.library)
- Запазва query параметри (page, rows, cols, filters, etc.)

### 4. Template Context

**Файл: `app/template_context.py`**

```python
# Функциите за терминология (Genre/Category) вече използват gettext
from flask_babel import gettext as _

def _get_genre_term():
    return _('Genre') if terminology_preference == 'genre' else _('Category')

def _get_genre_term_plural():
    return _('Genres') if terminology_preference == 'genre' else _('Categories')
```

---

## 📦 Файлове, които са променени

### Python файлове
- `app/__init__.py` - Конфигурация на Babel и context processor
- `app/routes/language_routes.py` - НОВ файл за language switching
- `app/routes/book_routes.py` - ETag с language support
- `app/template_context.py` - Преводи за терминология

### Template файлове
- `app/templates/base.html` - Навигация, language switcher, user dropdown
- `app/templates/library_enhanced.html` - Преводи за библиотечната страница
- `app/templates/genres/index.html` - Преводи за категории
- `app/templates/view_book_enhanced.html` - Преводи за детайли на книга

### Конфигурационни файлове
- `babel.cfg` - НОВ файл за конфигурация на Babel
- `requirements.txt` - Добавен Flask-Babel>=4.0.0

### Translation файлове
- `translations/bg/LC_MESSAGES/messages.po` - Български преводи
- `translations/en/LC_MESSAGES/messages.po` - Английски преводи
- `translations/*/LC_MESSAGES/messages.mo` - Компилирани преводи (генерирани)

---

## 🚀 Инструкции за deployment

### 1. Локална разработка

```bash
# Инсталация на зависимости
pip install -r requirements.txt

# Извличане на преводите (ако има промени в кода)
pybabel extract -F babel.cfg -k _l -o messages.pot .
pybabel update -i messages.pot -d translations -l bg
pybabel update -i messages.pot -d translations -l en

# Компилиране на преводите
pybabel compile -d translations

# Стартиране на приложението
python dev_run.py
```

### 2. Production Server

```bash
# 1. Пулване на промените
cd ~/mybibliotheca
git pull origin main

# 2. Активиране на virtual environment
source venv/bin/activate  # или: . venv/bin/activate

# 3. Инсталация на нови зависимости
pip install Flask-Babel>=4.0.0
pip install Babel  # За pybabel CLI инструмента

# 4. Компилиране на преводите
pybabel compile -d translations
# или ако pybabel не е наличен:
python -m babel.messages.frontend compile -d translations

# 5. Проверка на компилираните файлове
ls -lh translations/bg/LC_MESSAGES/messages.mo
ls -lh translations/en/LC_MESSAGES/messages.mo
# Трябва да са > 0 bytes

# 6. Рестартиране на приложението
# Спрете текущия процес (Ctrl+C) и стартирайте отново:
python dev_run.py
```

### 3. Troubleshooting

#### Проблем: `pybabel: command not found`
```bash
# Решение: Инсталирайте Babel пакета
pip install Babel

# Алтернатива: Използвайте Python модула
python -m babel.messages.frontend compile -d translations
```

#### Проблем: Преводите не се показват
```bash
# Проверете дали .mo файловете са компилирани
ls -lh translations/bg/LC_MESSAGES/messages.mo

# Ако не съществуват или са 0 bytes:
pybabel compile -d translations

# Проверете логовете за грешки
tail -f logs/app.log | grep -i language
```

#### Проблем: Езикът не се запазва след рестарт
```bash
# Проверете session конфигурацията в app/__init__.py
# Уверете се че session.permanent = True е зададено
```

---

## ✅ Проверка на функционалността

### 1. Тест на language switching

1. Отворете приложението
2. Кликнете на language switcher (флаг)
3. Изберете различен език
4. Проверете че:
   - URL-ът се редиректва правилно
   - Текстовете се променят на избрания език
   - Езикът се запазва след рестарт на страницата

### 2. Тест на user dropdown

1. Влезте в системата
2. Кликнете на "Добре дошли, [username]"
3. Проверете че dropdown менюто се отваря с:
   - Администрация (ако сте admin)
   - Потребител
   - Изход

### 3. Тест на brand центриране

1. Отворете приложението на различни размери на екрана
2. Проверете че "Моята библиотека" е центрирана
3. Проверете че шрифтът е по-голям от другите елементи

### 4. Тест на Locations линк

1. Влезте в системата
2. Проверете че "Местоположение" е видим в основната навигация
3. Проверете че линкът работи правилно

---

## 📊 Статистика на промените

- **Нови файлове**: 3
  - `app/routes/language_routes.py`
  - `babel.cfg`
  - `translations/bg/LC_MESSAGES/messages.po`

- **Променени файлове**: 8+
  - `app/__init__.py`
  - `app/routes/book_routes.py`
  - `app/template_context.py`
  - `app/templates/base.html`
  - `app/templates/library_enhanced.html`
  - `app/templates/genres/index.html`
  - `app/templates/view_book_enhanced.html`
  - `requirements.txt`

- **Преводи**: 100+ думи/фрази на български

- **Поддържани езици**: 2 (Български, Английски)

---

## 🎯 Ключови подобрения

1. ✅ **Интернационализация**: Пълна поддръжка на български и английски език
2. ✅ **По-добър UX**: Компактен и организиран navigation bar
3. ✅ **По-лесен достъп**: Locations е в основната навигация
4. ✅ **Визуална яснота**: Центриран brand с по-голям шрифт
5. ✅ **Език по подразбиране**: Български за нови потребители
6. ✅ **Session management**: Правилно запазване на избрания език
7. ✅ **Caching**: Правилна обработка на кеширане при смяна на език

---

## 📝 Бележки

- Всички промени са обратно съвместими
- Старият код продължава да работи без преводи (fallback към оригиналния текст)
- Преводите могат да се разширяват лесно чрез `messages.po` файловете
- Добавянето на нови езици изисква само създаване на нова директория в `translations/`

---

## 🔗 Полезни команди

```bash
# Извличане на нови strings за превод
pybabel extract -F babel.cfg -k _l -o messages.pot .

# Обновяване на съществуващи .po файлове
pybabel update -i messages.pot -d translations -l bg
pybabel update -i messages.pot -d translations -l en

# Компилиране на преводите
pybabel compile -d translations

# Проверка на статистиката на преводите
pybabel compile -d translations --statistics
```

---

**Дата на създаване**: 2025-12-29  
**Последна актуализация**: 2025-12-29  
**Версия**: 1.0
