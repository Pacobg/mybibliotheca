# Инсталиране на MariaDB Client

## За Debian/Ubuntu:

```bash
# Обнови package list
sudo apt-get update

# Инсталирай MariaDB client
sudo apt-get install mariadb-client

# Провери дали е инсталиран
mysql --version
```

## След инсталация:

### Вариант 1: Интерактивно влизане в MariaDB

```bash
# Влез в MariaDB
mysql -u root -p

# След като влезеш (ще видиш MariaDB prompt), изпълни:
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;
EXIT;
```

### Вариант 2: Един ред команда

```bash
mysql -u root -p -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

## Ако MariaDB сървърът е на друг порт:

```bash
# Ако MariaDB слуша на порт 3307 (не стандартния 3306)
mysql -u root -p -P 3307 -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

## Проверка след конфигуриране:

```bash
# Провери дали потребителят е създаден
mysql -u root -p -e "SELECT user, host FROM mysql.user WHERE user='root';"

# Провери правата
mysql -u root -p -e "SHOW GRANTS FOR 'root'@'192.168.1.%';"
```

