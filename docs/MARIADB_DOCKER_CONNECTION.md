# Свързване към MariaDB в Docker контейнер

## Проблем: MariaDB не работи локално

Ако виждаш грешка `ERROR 2002 (HY000): Can't connect to local server through socket`, това означава че:
- MariaDB не е инсталиран локално на сървъра, ИЛИ
- MariaDB е в Docker контейнер

## Решение 1: Ако MariaDB е в Docker контейнер в Coolify

### Намери името на контейнера:

```bash
# Виж всички Docker контейнери
docker ps -a

# Търси контейнер с MariaDB или MySQL
docker ps | grep -i mariadb
docker ps | grep -i mysql
```

### Влез в контейнера и се свържи към MariaDB:

```bash
# Влез в MariaDB контейнера
docker exec -it <container_name> mysql -u root -p

# След като влезеш в MariaDB, изпълни:
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;
EXIT;
```

### Или изпълни командата директно:

```bash
docker exec -it <container_name> mysql -u root -p -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

## Решение 2: Ако MariaDB е на друг сървър (192.168.1.13)

### Свържи се към remote MariaDB:

```bash
# Свържи се към remote MariaDB сървър
mysql -h 192.168.1.13 -P 3307 -u root -p

# След като влезеш, изпълни:
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;
EXIT;
```

### Или на един ред:

```bash
mysql -h 192.168.1.13 -P 3307 -u root -p -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

## Решение 3: Провери дали MariaDB работи

### Провери дали има MariaDB процес:

```bash
# Провери дали MariaDB процес работи
ps aux | grep mysql
ps aux | grep mariadb

# Провери дали има Docker контейнер с MariaDB
docker ps | grep -i mariadb
docker ps | grep -i mysql
```

### Провери дали портът е отворен:

```bash
# Провери дали порт 3307 е отворен
netstat -tlnp | grep 3307
ss -tlnp | grep 3307

# Или провери от друг сървър
nc -zv 192.168.1.13 3307
```

## Най-вероятният сценарий:

Ако Biblioman MariaDB е в Coolify Docker контейнер:

1. **Намери контейнера:**
   ```bash
   docker ps | grep biblioman
   # или
   docker ps | grep mariadb
   ```

2. **Влез в контейнера:**
   ```bash
   docker exec -it <container_name> bash
   ```

3. **В контейнера, влез в MariaDB:**
   ```bash
   mysql -u root -p
   ```

4. **Изпълни SQL командите:**
   ```sql
   CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
   GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
   FLUSH PRIVILEGES;
   EXIT;
   ```

5. **Излез от контейнера:**
   ```bash
   exit
   ```

## Алтернатива: Използвай Docker exec директно

```bash
# Намери името на контейнера
CONTAINER_NAME=$(docker ps | grep -i mariadb | awk '{print $1}')

# Изпълни командата директно
docker exec -it $CONTAINER_NAME mysql -u root -p -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

