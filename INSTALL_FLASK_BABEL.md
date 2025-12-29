# Инсталиране на Flask-Babel на сървъра

## Проблем

Грешката показва:
```
ModuleNotFoundError: No module named 'flask_babel'
```

Това означава че Flask-Babel не е инсталиран на сървъра.

## Решение

### Стъпка 1: Активиране на виртуалната среда

```bash
cd ~/mybibliotheca
source venv/bin/activate
```

### Стъпка 2: Инсталиране на Flask-Babel

```bash
pip install Flask-Babel Babel
```

**Очакван изход:**
```
Collecting Flask-Babel
  Downloading flask_babel-4.0.0-py3-none-any.whl
Collecting Babel>=2.12
  Downloading babel-2.17.0-py3-none-any.whl
...
Successfully installed Babel-2.17.0 Flask-Babel-4.0.0 pytz-2025.2
```

### Стъпка 3: Проверка на инсталацията

```bash
python -c "from flask_babel import Babel; print('✅ Flask-Babel OK')"
```

Трябва да видите: `✅ Flask-Babel OK`

### Стъпка 4: Компилиране на преводите

```bash
# Ако pybabel работи:
pybabel compile -d translations

# ИЛИ ако pybabel не работи:
python -m babel.messages.frontend compile -d translations
```

**Очакван изход:**
```
compiling catalog translations/bg/LC_MESSAGES/messages.po to translations/bg/LC_MESSAGES/messages.mo
compiling catalog translations/en/LC_MESSAGES/messages.po to translations/en/LC_MESSAGES/messages.mo
```

### Стъпка 5: Рестартиране на приложението

```bash
# Спрете текущия процес (Ctrl+C)
python dev_run.py
```

### Стъпка 6: Тест

1. Отворете приложението в браузър
2. Кликнете на language switcher-а (икона за превод)
3. Изберете "Български"
4. Проверете конзолата на сървъра - трябва да видите:
   ```
   🌐 [LANGUAGE] Language set to: bg
   🌐 [LANGUAGE] Session language value: bg
   🌐 [LANGUAGE] Forced Babel locale to: bg
   ```
5. Страницата трябва да се презареди и интерфейсът да е на български

## Ако има проблеми

### Проблем: pip не работи

```bash
# Използвайте python -m pip
python -m pip install Flask-Babel Babel
```

### Проблем: pybabel не работи

```bash
# Използвайте python -m babel
python -m babel.messages.frontend compile -d translations
```

### Проблем: Permission denied

```bash
# Ако имате проблеми с права, използвайте --user
pip install --user Flask-Babel Babel
```

## Проверка след инсталация

```bash
# Проверете дали е инсталиран
pip list | grep -i babel

# Трябва да видите:
# Babel         2.17.0
# Flask-Babel   4.0.0
```

## Важно!

След инсталация на Flask-Babel, **задължително рестартирайте приложението**, иначе промените няма да влязат в сила!
