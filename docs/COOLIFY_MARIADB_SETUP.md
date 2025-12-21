# Конфигуриране на MariaDB в Coolify за Biblioman достъп

## Парола от Coolify

Root паролата на MariaDB може да се намери в:
**Coolify UI → Biblioman DB → Configuration → General → Root Password**

## Стъпка 1: Влез в MariaDB контейнера

```bash
# Използвай mariadb командата (не mysql)
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p
```

Когато те попита за парола, въведи root паролата от Coolify.

## Стъпка 2: След като влезеш в MariaDB, изпълни:

```sql
CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189';
GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%';
FLUSH PRIVILEGES;
EXIT;
```

## Алтернатива: Изпълни на един ред с паролата

```bash
# Замени <ROOT_PASSWORD> с паролата от Coolify
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

**Важно:** Не оставяй интервал между `-p` и паролата!

## Пример с конкретна парола:

Ако паролата е `FbDMvhdb6NPEXBrgU5pWLj3dOu9GknuW`:

```bash
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -pFbDMvhdb6NPEXBrgU5pWLj3dOu9GknuW -e "CREATE USER IF NOT EXISTS 'root'@'192.168.1.%' IDENTIFIED BY 'L3mongate189'; GRANT ALL PRIVILEGES ON biblioman.* TO 'root'@'192.168.1.%'; FLUSH PRIVILEGES;"
```

## Проверка след конфигуриране:

```bash
# Провери дали потребителят е създаден
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "SELECT user, host FROM mysql.user WHERE user='root';"

# Провери правата
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "SHOW GRANTS FOR 'root'@'192.168.1.%';"
```

## Тествай connection от MyBibliotheca:

След като конфигурираш, тествай от dev сървъра или от MyBibliotheca контейнера:

```bash
# От dev сървъра (192.168.1.51)
mysql -h 192.168.1.13 -P 3307 -u root -pL3mongate189 biblioman -e "SELECT COUNT(*) FROM book;"

# Или от MyBibliotheca контейнера в Coolify
docker exec -it mybibliotheca-yowcwsssscgkww8ckck400kw mysql -h 192.168.1.13 -P 3307 -u root -pL3mongate189 biblioman -e "SELECT COUNT(*) FROM book;"
```

Ако видиш броя на книгите, connection-ът работи!

## Важни бележки:

1. **Паролата от Coolify** е за root потребителя в MariaDB контейнера
2. **Новата парола `L3mongate189`** е за достъп от мрежата (192.168.1.x)
3. След конфигуриране, MyBibliotheca ще използва `L3mongate189` за достъп от мрежата
4. Root паролата в Coolify остава същата - не я променяй

