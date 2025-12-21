# Quick Fix Commands for Dev Server

## Стъпка по стъпка команди (без коментари)

### 1. Спри текущия процес

```bash
ps aux | grep python | grep -E "run.py|dev_run.py"
```

Виж PID-а и спри процеса:
```bash
kill <PID>
```

Ако не спира:
```bash
kill -9 <PID>
```

### 2. Pull последните промени

```bash
cd ~/mybibliotheca
git pull origin main
```

### 3. Премахни lock файловете

```bash
rm -f data/kuzu/.lock
rm -f data/kuzu/*.lock
```

### 4. Стартирай с dev_run.py

```bash
source venv/bin/activate
python dev_run.py
```

## Един ред (ако няма процес който работи)

```bash
cd ~/mybibliotheca && git pull origin main && rm -f data/kuzu/.lock data/kuzu/*.lock && source venv/bin/activate && python dev_run.py
```

