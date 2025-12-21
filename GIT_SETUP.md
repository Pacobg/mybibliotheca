# Git Setup Guide за Biblioman Integration

## Стъпка 1: Инициализиране на Git Repository

Ако това е нов проект или не е свързано с Git:

```bash
# Инициализирай Git repository
git init

# Добави всички файлове
git add .

# Първи commit
git commit -m "Initial commit: Biblioman integration"
```

## Стъпка 2: Свързване с GitHub Fork

Според документацията ви, вашият fork е:
- **GitHub Fork:** https://github.com/Pacobg/mybibliotheca
- **Upstream:** https://github.com/pickles4evaaaa/mybibliotheca

```bash
# Добави origin (вашият fork)
git remote add origin https://github.com/Pacobg/mybibliotheca.git

# Добави upstream (оригиналният репозиторий)
git remote add upstream https://github.com/pickles4evaaaa/mybibliotheca.git

# Провери remotes
git remote -v
```

## Стъпка 3: Commit на Biblioman промените

```bash
# Провери статуса
git status

# Добави новите файлове
git add app/services/metadata_providers/
git add app/utils/text_utils.py
git add app/routes/book_routes.py
git add app/utils/unified_metadata.py
git add app/utils/metadata_settings.py
git add requirements.txt
git add docker-compose.dev.yml
git add docs/BIBLIOMAN_INTEGRATION.md

# Commit
git commit -m "feat: Add Biblioman integration for Bulgarian books

- Add Biblioman metadata provider (app/services/metadata_providers/biblioman.py)
- Add Cyrillic text utilities (app/utils/text_utils.py)
- Integrate Biblioman in search endpoint (app/routes/book_routes.py)
- Add Biblioman to unified metadata lookup (app/utils/unified_metadata.py)
- Update BOOK_FIELD_PROVIDERS to include Biblioman
- Add mysql-connector-python dependency
- Add Biblioman environment variables to docker-compose.dev.yml
- Add comprehensive integration documentation"
```

## Стъпка 4: Push към GitHub

```bash
# Push към вашия fork
git push -u origin main

# Ако main branch не съществува още, създай го
git branch -M main
git push -u origin main
```

## Стъпка 5: Sync с Upstream (опционално)

Ако искаш да синхронизираш с последните промени от upstream:

```bash
# Fetch последните промени от upstream
git fetch upstream

# Merge в текущия branch
git merge upstream/main

# Resolve conflicts ако има такива
# После push отново
git push origin main
```

## Стъпка 6: Deploy на Dev Server (192.168.1.52)

```bash
# SSH към dev сървъра
ssh pacovw@192.168.1.52

# Отиди в project директорията
cd ~/mybibliotheca

# Ако няма Git repository там:
git clone https://github.com/Pacobg/mybibliotheca.git
cd mybibliotheca

# Или ако вече има:
git pull origin main

# Инсталирай новите зависимости
source venv/bin/activate
pip install -r requirements.txt

# Рестартирай приложението
python run.py
```

## Стъпка 7: Deploy на Production (Coolify)

Coolify автоматично pull-ва от Git, но можеш да направиш manual deploy:

1. В Coolify UI: Отиди на приложението → "Redeploy"
2. Или ако имаш директен достъп:
   ```bash
   cd /path/to/mybibliotheca
   git pull origin main
   ```

## Troubleshooting

### Ако имаш конфликти при pull:

```bash
git stash
git pull origin main
git stash pop
# Resolve conflicts manually
git add .
git commit -m "fix: Resolve merge conflicts"
```

### Ако забравиш да добавиш файл:

```bash
git add <файл>
git commit --amend --no-edit
git push --force-with-lease origin main
```

### Ако искаш да видиш какво е променено:

```bash
git status
git diff
git log --oneline
```

