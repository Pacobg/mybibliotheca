# KuzuDB Lock File Fix Guide

## Проблем

KuzuDB lock грешки се появяват когато:
- Приложението е рестартирано без правилно затваряне на connections
- Има zombie процеси които държат lock файлове
- Lock файлове остават след crash или force kill

## Бързо Решение

### На Dev Server (192.168.1.52)

```bash
# 1. Спри приложението (ако работи)
# Намери процеса
ps aux | grep python | grep run.py

# Спри процеса
kill <PID>
# или ако не спира
kill -9 <PID>

# 2. Премахни lock файловете
cd ~/mybibliotheca
rm -f data/kuzu/.lock
rm -f data/kuzu/*.lock

# 3. Провери за други процеси
ps aux | grep python | grep -v grep

# 4. Рестартирай приложението
source venv/bin/activate
python run.py
```

### Използвай скрипта

```bash
cd ~/mybibliotheca
chmod +x scripts/fix_kuzu_locks.sh
./scripts/fix_kuzu_locks.sh
```

## Подробно Решение

### Стъпка 1: Спри всички процеси

```bash
# Намери всички Python процеси свързани с MyBibliotheca
ps aux | grep -E "python.*run.py|gunicorn.*run:app" | grep -v grep

# Спри ги един по един
kill <PID>

# Ако не спират, force kill
kill -9 <PID>
```

### Стъпка 2: Премахни Lock Файлове

```bash
cd ~/mybibliotheca

# Премахни основните lock файлове
rm -f data/kuzu/.lock
rm -f data/kuzu/bibliotheca.db.lock

# Премахни всички lock файлове
find data/kuzu -name "*.lock" -delete
find data/kuzu -name ".lock" -delete

# Провери дали са премахнати
ls -la data/kuzu/ | grep lock
```

### Стъпка 3: Провери Permissions

```bash
# Провери permissions на директорията
ls -ld data/kuzu/

# Ако има проблеми, поправи
chmod 755 data/kuzu/
chown -R $USER:$USER data/kuzu/
```

### Стъпка 4: Рестартирай Приложението

```bash
source venv/bin/activate
python run.py
```

## Предотвратяване на Проблеми

### 1. Винаги спирай приложението правилно

```bash
# Използвай Ctrl+C вместо kill -9
# Или ако работи като service:
sudo systemctl stop mybibliotheca
```

### 2. Използвай Docker (по-добро за development)

Docker автоматично премахва stale lock files при стартиране:

```bash
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml up -d
```

### 3. Добави cleanup в startup скрипт

Създай `start.sh`:

```bash
#!/bin/bash
# Cleanup KuzuDB locks before starting
rm -f data/kuzu/.lock
rm -f data/kuzu/*.lock

# Start application
source venv/bin/activate
python run.py
```

## Troubleshooting

### Ако проблемът продължава:

1. **Провери за multiple instances:**
   ```bash
   ps aux | grep python | grep run.py
   ```

2. **Провери за file locks:**
   ```bash
   lsof data/kuzu/bibliotheca.db 2>/dev/null || echo "No processes holding file"
   ```

3. **Провери disk space:**
   ```bash
   df -h data/kuzu/
   ```

4. **Провери permissions:**
   ```bash
   ls -la data/kuzu/
   ```

### Ако нищо не помага:

```bash
# Backup данните
cp -r data/kuzu data/kuzu.backup

# Премахни всички lock файлове и temp файлове
rm -f data/kuzu/.lock
rm -f data/kuzu/*.lock
rm -f data/kuzu/*.tmp

# Рестартирай
python run.py
```

## За Production (Coolify)

Coolify автоматично управлява процесите, но ако има проблеми:

1. В Coolify UI: Restart контейнера
2. Или ако имаш директен достъп:
   ```bash
   docker-compose restart
   ```

## Допълнителна Информация

- [KuzuDB Concurrency Docs](https://docs.kuzudb.com/concurrency)
- [Docker Guide](DOCKER.md)
- [Debugging Guide](docs/DEBUGGING.md)

