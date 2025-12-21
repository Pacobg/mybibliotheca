# MariaDB Setup за Biblioman достъп

## Стъпки за конфигуриране на MariaDB достъп

### 1. Инсталирай MariaDB client (ако нямаш)

```bash
# На Debian/Ubuntu
sudo apt-get update
sudo apt-get install mariadb-client

# Провери дали е инсталиран
mysql --version
```

### 2. Влез в MariaDB

```bash
# Влез в MariaDB като root потребител
mysql -u root -p

# Ще те попита за парола - въведи MariaDB root паролата
```

### 3. Изпълни SQL командите

След като влезеш в MariaDB (ще видиш `MariaDB [(none)]>` prompt), изпълни следните команди:

```sql
-- Позволи достъп от цялата локална мрежа (192.168.1.x)
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;

-- Провери дали потребителят е създаден
SELECT user, host FROM mysql.user WHERE user='root';

-- Излез от MariaDB
EXIT;
```

### Алтернатива: Изпълни командите на един ред

Ако предпочиташ да изпълниш командите директно от bash без да влизаш интерактивно:

```bash
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

### 4. Провери MariaDB конфигурацията

```bash
# Провери дали MariaDB слуша на правилния интерфейс
sudo nano /etc/mysql/mariadb.conf.d/50-server.cnf

# Уверете се че има:
bind-address = 0.0.0.0  # или конкретния IP адрес

# Рестартирай MariaDB
sudo systemctl restart mariadb
```

### 5. Тествай connection

От друг сървър в мрежата (например от Coolify контейнера или dev сървъра):

```bash
# Тествай connection
mysql -h 192.168.1.13 -P 3307 -u root -pL3mongate189 biblioman -e "SELECT COUNT(*) FROM book;"
```

Ако видиш броя на книгите, connection-ът работи правилно!

### Troubleshooting

#### Ако `mysql` командата не е намерена:

```bash
# Инсталирай MariaDB client
sudo apt-get update
sudo apt-get install mariadb-client
```

#### Ако не можеш да влезеш в MariaDB:

```bash
# Провери дали MariaDB сървърът работи
sudo systemctl status mariadb

# Ако не работи, стартирай го
sudo systemctl start mariadb
```

#### Ако виждаш "Access denied" след конфигуриране:

1. Провери дали потребителят е създаден:
   ```sql
   SELECT user, host FROM mysql.user WHERE user='root';
   ```

2. Провери дали правата са дадени:
   ```sql
   SHOW GRANTS FOR 'root'@'192.168.1.%';
   ```

3. Ако нещо не е наред, изтрий и създай отново:
   ```sql
   DROP USER IF EXISTS 'root'@'192.168.1.%';
   CREATE USER 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
   GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
   FLUSH PRIVILEGES;
   ```

