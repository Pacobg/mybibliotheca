# Resolving Merge Conflicts on Dev Server

## Quick Fix

Ако имаш merge конфликт при `git pull`, използвай една от следните опции:

### Option 1: Приеми remote версията (препоръчително)

```bash
cd ~/mybibliotheca

# Stash локалните промени (ако има такива)
git stash

# Fetch последните промени
git fetch origin main

# Приеми remote версията на конфликтния файл
git checkout --theirs app/__init__.py

# Добави файла
git add app/__init__.py

# Завърши merge-а
git commit -m "Merge origin/main - accept remote changes"

# Pull отново
git pull origin main
```

### Option 2: Използвай автоматичния скрипт

```bash
cd ~/mybibliotheca
chmod +x scripts/resolve_merge_conflict.sh
./scripts/resolve_merge_conflict.sh
```

### Option 3: Reset и pull отново (ако няма важни локални промени)

```bash
cd ~/mybibliotheca

# Запази локалните промени
git stash

# Reset към remote версията
git reset --hard origin/main

# Pull отново
git pull origin main

# Върни локалните промени (ако са нужни)
git stash pop
```

## След успешен merge

```bash
# Стартирай приложението
source venv/bin/activate
python dev_run.py
```

## Проверка

След merge, провери че всичко е наред:

```bash
git status
git log --oneline -5
```

Трябва да видиш commit "fix: Properly encode Cyrillic characters in URL query parameters for redirects"

