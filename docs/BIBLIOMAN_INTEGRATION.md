# Biblioman Integration - Development & Deployment Guide

## 📋 Съдържание

1. [Git Workflow](#git-workflow)
2. [Docker vs Native Development](#docker-vs-native-development)
3. [Deployment Strategy](#deployment-strategy)
4. [Environment Configuration](#environment-configuration)

---

## 🔄 Git Workflow

### Препоръчителен Workflow

**ДА, промените трябва да отидат първо в Git, после на сървъра!**

Това осигурява:
- ✅ Версионен контрол на промените
- ✅ Възможност за rollback при проблеми
- ✅ Документиране на промените
- ✅ Лесно споделяне между сървъри
- ✅ Backup на кода

### Стъпки за Git Workflow

#### 1. Проверка на текущото състояние

```bash
# Провери статуса
git status

# Виж какви промени има
git diff

# Виж какви файлове са променени
git status --short
```

#### 2. Добавяне на промените

```bash
# Добави всички нови/променени файлове
git add .

# Или добави конкретни файлове
git add app/services/metadata_providers/biblioman.py
git add app/utils/text_utils.py
git add app/routes/book_routes.py
git add requirements.txt
```

#### 3. Commit на промените

```bash
# Commit с описателно съобщение
git commit -m "feat: Add Biblioman integration for Bulgarian books

- Add Biblioman metadata provider (app/services/metadata_providers/biblioman.py)
- Add Cyrillic text utilities (app/utils/text_utils.py)
- Integrate Biblioman in search endpoint (app/routes/book_routes.py)
- Add Biblioman to unified metadata lookup (app/utils/unified_metadata.py)
- Update BOOK_FIELD_PROVIDERS to include Biblioman
- Add mysql-connector-python dependency"
```

#### 4. Push към GitHub fork

```bash
# Провери remote репозиториите
git remote -v

# Push към вашия fork
git push origin main

# Или ако работите на branch
git push origin feature/biblioman-integration
```

#### 5. Pull на сървъра

```bash
# На сървъра (192.168.1.52 или production)
cd ~/mybibliotheca

# Fetch последните промени
git fetch origin

# Pull промените
git pull origin main

# Или ако работите на branch
git checkout main
git pull origin main
```

---

## 🐳 Docker vs Native Development

### Сравнение

| Аспект | Docker | Native (Python venv) |
|--------|--------|---------------------|
| **Изолация** | ✅ Пълна изолация | ⚠️ Зависи от системата |
| **Консистентност** | ✅ Еднакво на всички машини | ⚠️ Може да варира |
| **Setup време** | ⚠️ По-бавно (build image) | ✅ По-бързо |
| **Debugging** | ⚠️ По-сложно (логове, attach) | ✅ По-лесно (директно) |
| **Production similarity** | ✅ Идентично | ⚠️ Може да се различава |
| **Dependencies** | ✅ Автоматично | ⚠️ Ръчно управление |
| **KuzuDB locks** | ✅ По-добре изолирани | ⚠️ Проблеми в dev |

### Препоръка

**За development на 192.168.1.52:**
- ✅ **Използвайте Docker** ако искате production-like среда
- ✅ **Използвайте Native** ако искате по-бърз debugging и iteration

**За production (Coolify):**
- ✅ **Винаги Docker** - Coolify изисква Docker

### Docker Development Setup

```bash
# На dev машината (192.168.1.52)
cd ~/mybibliotheca

# Копирай .env файл
cp .env.example .env

# Редактирай .env с Biblioman настройки
nano .env

# Стартирай с Docker Compose (development mode)
docker-compose -f docker-compose.dev.yml up -d

# Виж логовете
docker-compose -f docker-compose.dev.yml logs -f

# Спри контейнера
docker-compose -f docker-compose.dev.yml down
```

### Native Development Setup

```bash
# На dev машината (192.168.1.52)
cd ~/mybibliotheca

# Активирай virtual environment
source venv/bin/activate

# Инсталирай новите зависимости
pip install -r requirements.txt

# Стартирай Flask dev server
python run.py
```

---

## 🚀 Deployment Strategy

### Оптимален Deployment Workflow

```
Local Dev → Git Commit → Push to GitHub → Pull on Server → Deploy
```

### Стъпка по стъпка

#### Фаза 1: Local Development (192.168.1.52)

```bash
# 1. Направи промените в кода
# 2. Тествай локално
python run.py
# или
docker-compose -f docker-compose.dev.yml up

# 3. Commit промените
git add .
git commit -m "feat: Biblioman integration"

# 4. Push към GitHub
git push origin main
```

#### Фаза 2: Deploy на Dev Server (192.168.1.52)

```bash
# SSH към dev сървъра
ssh pacovw@192.168.1.52

# Отиди в project директорията
cd ~/mybibliotheca

# Pull последните промени от GitHub
git pull origin main

# Ако използваш Docker:
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml up -d --build

# Ако използваш Native:
source venv/bin/activate
pip install -r requirements.txt
# Рестартирай приложението (ако работи като service)
sudo systemctl restart mybibliotheca
# или просто рестартирай Flask dev server
```

#### Фаза 3: Deploy на Production (Coolify)

Coolify автоматично pull-ва от Git при push към main branch, но можеш да направиш manual deploy:

```bash
# В Coolify UI:
# 1. Отиди на приложението
# 2. Кликни "Redeploy" или "Pull & Deploy"
# 3. Coolify ще pull-не последните промени и ще rebuild контейнера
```

Или чрез Git hook на сървъра:

```bash
# На production сървъра (ако има директен достъп)
cd /path/to/mybibliotheca
git pull origin main
# Coolify ще засече промените и ще рестартира
```

---

## ⚙️ Environment Configuration

### Biblioman Environment Variables

Добави следните променливи в `.env` файла:

```bash
# Biblioman Integration
BIBLIOMAN_ENABLED=true
BIBLIOMAN_HOST=192.168.1.13
BIBLIOMAN_PORT=3307
BIBLIOMAN_USER=root
BIBLIOMAN_PASSWORD=L3mongate189
BIBLIOMAN_DATABASE=biblioman
```

### За Docker

Добави в `docker-compose.dev.yml` или `docker-compose.yml`:

```yaml
environment:
  - BIBLIOMAN_ENABLED=true
  - BIBLIOMAN_HOST=192.168.1.13
  - BIBLIOMAN_PORT=3307
  - BIBLIOMAN_USER=root
  - BIBLIOMAN_PASSWORD=L3mongate189
  - BIBLIOMAN_DATABASE=biblioman
```

### За Native Development

Добави в `.env` файла в project root:

```bash
BIBLIOMAN_ENABLED=true
BIBLIOMAN_HOST=192.168.1.13
BIBLIOMAN_PORT=3307
BIBLIOMAN_USER=root
BIBLIOMAN_PASSWORD=L3mongate189
BIBLIOMAN_DATABASE=biblioman
```

---

## 📝 Best Practices

### Git Commits

1. **Използвай описателни commit messages:**
   ```bash
   git commit -m "feat: Add Biblioman integration"
   git commit -m "fix: Handle Cyrillic text encoding"
   git commit -m "docs: Update Biblioman integration guide"
   ```

2. **Групирай свързани промени:**
   - Не комитвай всичко наведнъж
   - Групирай логически свързани промени

3. **Тествай преди commit:**
   ```bash
   # Провери за синтактични грешки
   python -m py_compile app/services/metadata_providers/biblioman.py
   
   # Ако имаш тестове
   pytest tests/
   ```

### Deployment Checklist

- [ ] Промените са committed в Git
- [ ] Промените са pushed към GitHub
- [ ] `.env` файлът е конфигуриран правилно
- [ ] Зависимостите са инсталирани (`pip install -r requirements.txt`)
- [ ] Приложението стартира без грешки
- [ ] Biblioman connection работи (провери логовете)
- [ ] Тествано с реални данни (търсене на българска книга)

---

## 🔍 Troubleshooting

### Git Issues

```bash
# Ако имаш конфликти при pull
git stash
git pull origin main
git stash pop

# Ако забравиш да commit-неш промени
git status
git add .
git commit -m "fix: Add missing changes"
```

### Docker Issues

```bash
# Ако има проблеми с build
docker-compose -f docker-compose.dev.yml build --no-cache

# Ако има проблеми с permissions
sudo chown -R $USER:$USER ./data
```

### Biblioman Connection Issues

```bash
# Провери дали можеш да се свържеш към Biblioman
mysql -h 192.168.1.13 -P 3307 -u root -p biblioman

# Провери логовете на приложението
docker-compose logs bibliotheca | grep -i biblioman
# или
tail -f app.log | grep -i biblioman
```

---

## 📚 Допълнителни Ресурси

- [Git Workflow Guide](https://www.atlassian.com/git/tutorials/comparing-workflows)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [MyBibliotheca Docker Guide](DOCKER.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

