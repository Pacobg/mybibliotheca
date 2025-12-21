# Deployment Steps - Biblioman Integration

## ✅ Git Setup Completed

Git repository е инициализиран и commit е направен успешно!

**Commit Hash:** `1d8abc1`
**Commit Message:** "feat: Add Biblioman integration for Bulgarian books"

## 📤 Следващи стъпки: Push към GitHub

### Стъпка 1: Push към вашия fork

```bash
# Push към GitHub (първи път)
git push -u origin main

# Следващи пъти просто:
git push origin main
```

**Важно:** Ако GitHub fork-ът ти все още няма съдържание, може да се наложи да направиш force push:
```bash
git push -u origin main --force
```

## 🖥️ Deploy на Dev Server (192.168.1.52)

### Вариант A: Ако вече имаш клониран repository

```bash
# SSH към dev сървъра
ssh pacovw@192.168.1.52

# Отиди в project директорията
cd ~/mybibliotheca

# Pull последните промени
git pull origin main

# Инсталирай новите зависимости
source venv/bin/activate
pip install -r requirements.txt

# Рестартирай приложението
# (Ctrl+C ако работи, после стартирай отново)
python run.py
```

### Вариант B: Ако нямаш клониран repository

```bash
# SSH към dev сървъра
ssh pacovw@192.168.1.52

# Клонирай repository
git clone https://github.com/Pacobg/mybibliotheca.git
cd mybibliotheca

# Създай virtual environment
python3 -m venv venv
source venv/bin/activate

# Инсталирай зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Конфигурирай .env файл
cp .env.example .env
nano .env  # Добави Biblioman настройките

# Стартирай приложението
python run.py
```

## 🐳 Deploy с Docker (Алтернатива)

Ако предпочиташ Docker на dev сървъра:

```bash
# SSH към dev сървъра
ssh pacovw@192.168.1.52

cd ~/mybibliotheca

# Pull последните промени
git pull origin main

# Build и стартирай с Docker
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml up -d --build

# Виж логовете
docker-compose -f docker-compose.dev.yml logs -f
```

## 🚀 Deploy на Production (Coolify)

### Автоматичен Deploy

Coolify автоматично pull-ва от Git при push към main branch. Просто:

1. Push промените към GitHub (виж по-горе)
2. В Coolify UI: Отиди на приложението → "Redeploy" или "Pull & Deploy"

### Manual Deploy (ако имаш директен достъп)

```bash
# На production сървъра
cd /path/to/mybibliotheca
git pull origin main
# Coolify ще засече промените и ще рестартира автоматично
```

## ⚙️ Environment Configuration

### На Dev Server (192.168.1.52)

Създай или редактирай `.env` файл:

```bash
nano ~/mybibliotheca/.env
```

Добави:

```bash
# Biblioman Integration
BIBLIOMAN_ENABLED=true
BIBLIOMAN_HOST=192.168.1.13
BIBLIOMAN_PORT=3307
BIBLIOMAN_USER=root
BIBLIOMAN_PASSWORD=L3mongate189
BIBLIOMAN_DATABASE=biblioman
```

### На Production (Coolify)

Добави тези environment variables в Coolify UI:
- Settings → Environment Variables → Add New

## ✅ Deployment Checklist

- [x] Git repository инициализиран
- [x] Remotes добавени (origin + upstream)
- [x] Промените са committed
- [ ] Промените са pushed към GitHub
- [ ] `.env` файлът е конфигуриран на dev сървъра
- [ ] Зависимостите са инсталирани (`pip install -r requirements.txt`)
- [ ] Приложението стартира без грешки
- [ ] Biblioman connection работи (провери логовете)
- [ ] Тествано с реални данни (търсене на българска книга)

## 🔍 Testing

След deployment, тествай:

1. **Търсене на българска книга:**
   - Отвори MyBibliotheca
   - Търси книга с кирилица (напр. "Измамници")
   - Провери дали се появяват резултати от Biblioman

2. **Проверка на логовете:**
   ```bash
   # Ако използваш Docker
   docker-compose logs bibliotheca | grep -i biblioman
   
   # Ако използваш Native
   tail -f app.log | grep -i biblioman
   ```

3. **Проверка на connection:**
   ```bash
   # Тест MySQL connection
   mysql -h 192.168.1.13 -P 3307 -u root -p biblioman
   ```

## 🐛 Troubleshooting

### Ако Git push не работи:

```bash
# Провери дали имаш правилни credentials
git config --global user.name "Pacobg"
git config --global user.email "pacovw@gmail.com"

# Ако имаш проблеми с authentication, използвай Personal Access Token
# GitHub → Settings → Developer settings → Personal access tokens
```

### Ако има проблеми с dependencies:

```bash
# Преинсталирай всички зависимости
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### Ако Biblioman не се свързва:

1. Провери дали Biblioman database е достъпен:
   ```bash
   mysql -h 192.168.1.13 -P 3307 -u root -p biblioman
   ```

2. Провери firewall правилата на сървъра

3. Провери логовете за грешки:
   ```bash
   grep -i biblioman app.log
   ```

## 📚 Допълнителна информация

- [Biblioman Integration Guide](docs/BIBLIOMAN_INTEGRATION.md)
- [Git Setup Guide](GIT_SETUP.md)
- [Docker Guide](DOCKER.md)

