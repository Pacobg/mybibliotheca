# Свързване към Remote MariaDB сървър

## Проблем: MariaDB се опитва да се свърже локално

Ако виждаш грешка `ERROR 2002 (HY000): Can't connect to local server through socket`, това означава че `mysql` клиентът се опитва да се свърже локално, а не към remote сървъра.

## Решение: Използвай `-h` за remote host

### За свързване към MariaDB на 192.168.1.13:

```bash
# Свържи се към remote MariaDB сървър
mysql -h 192.168.1.13 -P 3307 -u root -p
```

### След като влезеш в MariaDB, изпълни командите:

```sql
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;
EXIT;
```

### Или на един ред:

```bash
mysql -h 192.168.1.13 -P 3307 -u root -p -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

## Важни параметри:

- `-h 192.168.1.13` - IP адрес на MariaDB сървъра
- `-P 3307` - Порт (ако не е стандартния 3306)
- `-u root` - Потребител
- `-p` - Ще те попита за парола интерактивно
- `-e "SQL команда"` - Изпълни SQL команда и излез

## Проверка дали MariaDB сървърът работи:

```bash
# Провери дали портът е отворен
nc -zv 192.168.1.13 3307

# Или с telnet
telnet 192.168.1.13 3307
```

## Ако все още има проблеми:

### 1. Провери дали MariaDB слуша на правилния интерфейс:

На MariaDB сървъра (192.168.1.13):
```bash
sudo nano /etc/mysql/mariadb.conf.d/50-server.cnf
```

Уверете се че има:
```
bind-address = 0.0.0.0
```

Рестартирай:
```bash
sudo systemctl restart mariadb
```

### 2. Провери firewall правилата:

```bash
# На MariaDB сървъра, провери firewall
sudo ufw status
sudo iptables -L -n | grep 3307
```

### 3. Тествай connection:

```bash
# От друг сървър, тествай connection
mysql -h 192.168.1.13 -P 3307 -u root -pL3mongate189 biblioman -e "SELECT COUNT(*) FROM book;"
```

Ако видиш броя на книгите, connection-ът работи!

