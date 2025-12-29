# Бързо решение за проблемите на сървъра

## Проблем 1: numpy не се компилира

Това НЕ е критично за i18n функционалността! Можете да продължите без да компилирате numpy.

**Решение:**
```bash
# Инсталирайте само Flask-Babel (без да компилирате numpy)
pip install Flask-Babel Babel pytz

# Проверете дали работи
python -c "from flask_babel import Babel; print('Flask-Babel OK')"
```

## Проблем 2: pybabel командата не е налична

**Решение:**
```bash
# Инсталирайте Babel (който включва CLI инструментите)
pip install Babel

# Проверете
pybabel --version

# Ако все още не работи, използвайте python -m babel вместо pybabel:
python -m babel.messages.frontend compile -d translations
```

## Компилиране на преводите (алтернативен метод)

Ако `pybabel` не работи, използвайте Python модула директно:

```bash
python -m babel.messages.frontend compile -d translations
```

Или в Python код:

```python
from babel.messages.frontend import compile_catalog
compile_catalog('translations', 'bg')
compile_catalog('translations', 'en')
```

## Минимална инсталация за i18n

Ако имате проблеми с всички зависимости, инсталирайте само необходимото:

```bash
pip install Flask-Babel Babel pytz
```

Това е достатъчно за i18n функционалността да работи!

## Проверка след инсталация

```bash
# Проверете Flask-Babel
python -c "from flask_babel import Babel; print('✅ Flask-Babel OK')"

# Проверете Babel CLI
python -m babel.messages.frontend --version

# Компилирайте преводите
python -m babel.messages.frontend compile -d translations
```

## Рестартиране на приложението

След като инсталирате зависимостите:

```bash
# Спрете текущия процес (Ctrl+C ако е в терминал)
# или
pkill -f "python.*dev_run"

# Стартирайте отново
python dev_run.py
```

## Важно!

- **numpy проблемът НЕ пречи на i18n** - numpy се използва за OCR функционалност, не за преводи
- **Flask-Babel е достатъчен** - не се нуждаете от компилиране на numpy за да работи i18n
- **Преводите могат да се компилират с `python -m babel`** ако `pybabel` не е наличен
