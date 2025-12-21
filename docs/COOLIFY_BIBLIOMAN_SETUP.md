# Biblioman Setup в Coolify

## 📋 Стъпки за конфигуриране на Biblioman в Coolify

### 1. Обнови Docker Compose файла в Coolify

В Coolify UI → Application → Docker Compose, обнови `docker-compose.yml` файла:

```yaml
services:
  mybibliotheca:
    image: 'pickles4evaaaa/mybibliotheca:beta-latest'
    container_name: mybibliotheca
    ports:
      - '5054:5054'
    volumes:
      - 'mybibliotheca_data:/app/data'
    environment:
      SECRET_KEY: '${SECRET_KEY}'
      SECURITY_PASSWORD_SALT: '${SECURITY_PASSWORD_SALT}'
      SITE_NAME: MyBibliotheca
      TIMEZONE: Europe/Sofia
      KUZU_DB_PATH: /app/data/kuzu
      GRAPH_DATABASE_ENABLED: 'true'
      WORKERS: '1'
      LOG_LEVEL: INFO
      ACCESS_LOGS: 'false'
      
      # Biblioman Integration (Bulgarian books metadata)
      BIBLIOMAN_ENABLED: '${BIBLIOMAN_ENABLED}'
      BIBLIOMAN_HOST: '${BIBLIOMAN_HOST}'
      BIBLIOMAN_PORT: '${BIBLIOMAN_PORT}'
      BIBLIOMAN_USER: '${BIBLIOMAN_USER}'
      BIBLIOMAN_PASSWORD: '${BIBLIOMAN_PASSWORD}'
      BIBLIOMAN_DATABASE: '${BIBLIOMAN_DATABASE}'
    restart: unless-stopped
    healthcheck:
      test: "timeout 10s bash -c ':> /dev/tcp/127.0.0.1/5054' || exit 1"
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 90s

volumes:
  mybibliotheca_data: null
```

### 2. Добави Environment Variables в Coolify UI

Отиди в **Coolify UI → Application → Environment Variables** и добави следните променливи:

| Variable | Value | Описание |
|----------|-------|----------|
| `BIBLIOMAN_ENABLED` | `true` | Активира Biblioman provider |
| `BIBLIOMAN_HOST` | `192.168.1.13` | IP адрес на Biblioman MariaDB сървъра |
| `BIBLIOMAN_PORT` | `3307` | Порт на MariaDB |
| `BIBLIOMAN_USER` | `root` | MariaDB потребител |
| `BIBLIOMAN_PASSWORD` | `L3mongate189` | MariaDB парола |
| `BIBLIOMAN_DATABASE` | `biblioman` | Име на базата данни |

### 3. Конфигурирай MariaDB за достъп от Coolify контейнера

Ако Biblioman MariaDB е на друг сървър (192.168.1.13), трябва да позволиш достъп от Coolify контейнера:

#### На MariaDB сървъра (192.168.1.13):

```sql
-- Влез в MariaDB
mysql -u root -p

-- Създай потребител за достъп от Coolify контейнера
-- Замени <COOLIFY_CONTAINER_IP> с IP адреса на Coolify контейнера
CREATE USER IF NOT EXISTS 'root'@'<COOLIFY_CONTAINER_IP>' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'<COOLIFY_CONTAINER_IP>';
FLUSH PRIVILEGES;

-- Или ако искаш да позволиш достъп от цялата локална мрежа:
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;
```

#### Провери MariaDB конфигурацията:

```bash
# На MariaDB сървъра, провери дали слуша на правилния интерфейс
sudo nano /etc/mysql/mariadb.conf.d/50-server.cnf

# Уверете се че има:
bind-address = 0.0.0.0  # или конкретния IP адрес

# Рестартирай MariaDB
sudo systemctl restart mariadb
```

### 4. Намери IP адреса на Coolify контейнера

За да знаеш от кой IP адрес да позволиш достъп в MariaDB:

```bash
# В Coolify контейнера на mybibliotheca
docker exec -it mybibliotheca hostname -I

# Или провери network:
docker network inspect <network_name> | grep -A 10 mybibliotheca
```

### 5. Тествай connection

След като конфигурираш всичко:

1. **Redeploy приложението в Coolify** (за да зареди новите environment variables)
2. **Провери логовете** за Biblioman connection:
   ```bash
   # В Coolify UI → Application → Logs
   # Търси за "Biblioman database connection established"
   ```
3. **Тествай search** с българска книга (например "Морето на спокойствието")

### 6. Troubleshooting

#### Ако виждаш грешка "Access denied":

1. Провери дали MariaDB потребителят е създаден правилно
2. Провери дали MariaDB слуша на правилния интерфейс (`bind-address`)
3. Провери firewall правилата между Coolify контейнера и MariaDB сървъра
4. Провери дали environment variables са правилно конфигурирани в Coolify

#### Ако виждаш грешка "Connection refused":

1. Провери дали MariaDB портът (3307) е отворен
2. Провери дали MariaDB сървърът е достъпен от Coolify контейнера:
   ```bash
   # От Coolify контейнера
   docker exec -it mybibliotheca nc -zv 192.168.1.13 3307
   ```

#### Ако Biblioman не се използва въпреки че е enabled:

1. Провери логовете за "Biblioman is not enabled" или "Biblioman connection failed"
2. Уверете се че `BIBLIOMAN_ENABLED=true` (не `'true'` или `True`)
3. Провери дали имаш правилни metadata settings в приложението (Settings → Server → Metadata)

---

## 📝 Забележки

- **Security**: В production, използвай отделен MariaDB потребител (не `root`) с ограничени права
- **Network**: Уверете се че Coolify контейнерът може да достигне до MariaDB сървъра (същата мрежа или правилни firewall правила)
- **Performance**: Biblioman търсенето се изпълнява паралелно с Google Books и OpenLibrary, така че не забавя основното търсене

