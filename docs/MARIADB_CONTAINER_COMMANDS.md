# Команди за MariaDB Docker контейнер

## Проблем: `mysql` командата не е намерена

В MariaDB контейнерите, използвай `mariadb` вместо `mysql`.

## Решение 1: Използвай `mariadb` командата

```bash
# Влез в MariaDB контейнера с mariadb командата
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p

# След като влезеш, изпълни SQL командите:
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;
EXIT;
```

## Решение 2: Изпълни на един ред

```bash
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

## Решение 3: Влез в контейнера и използвай bash

```bash
# Влез в контейнера
docker exec -it ossoo808goc4cw4wos8sg0so bash

# В контейнера, провери какви команди има
which mariadb
which mysql

# Използвай наличната команда
mariadb -u root -p
# или
mysql -u root -p
```

## Решение 4: Използвай пълния път

Ако нито `mariadb` нито `mysql` работят, опитай с пълния път:

```bash
# Провери къде е MariaDB binary
docker exec -it ossoo808goc4cw4wos8sg0so which mariadb
docker exec -it ossoo808goc4cw4wos8sg0so which mysql

# Използвай пълния път (обикновено е в /usr/bin/)
docker exec -it ossoo808goc4cw4wos8sg0so /usr/bin/mariadb -u root -p
```

## Проверка след конфигуриране

```bash
# Провери дали потребителят е създаден
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p -e "SELECT user, host FROM mysql.user WHERE user='root';"

# Провери правата
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p -e "SHOW GRANTS FOR 'root'@'192.168.1.%';"
```

## Тествай connection от друг сървър

След като конфигурираш, тествай от dev сървъра или Coolify контейнера:

```bash
# От dev сървъра (192.168.1.51) или от друг контейнер
mysql -h 192.168.1.13 -P 3307 -u root -pL3mongate189 biblioman -e "SELECT COUNT(*) FROM book;"
```

Ако видиш броя на книгите, connection-ът работи!

