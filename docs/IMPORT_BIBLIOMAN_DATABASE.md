# Импортиране на Biblioman база данни

## Стъпка 1: Копирай SQL файла в контейнера

### Вариант 1: Ако файлът е на host сървъра

```bash
# Копирай файла в контейнера
docker cp /root/biblioman.sql ossoo808goc4cw4wos8sg0so:/tmp/biblioman.sql

# Импортирай в MariaDB
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> < /tmp/biblioman.sql
```

### Вариант 2: Ако файлът е компресиран (.sql.gz)

```bash
# Копирай файла в контейнера
docker cp /root/biblioman.sql.gz ossoo808goc4cw4wos8sg0so:/tmp/biblioman.sql.gz

# Декомпресирай и импортирай
docker exec -i ossoo808goc4cw4wos8sg0so bash -c "gunzip < /tmp/biblioman.sql.gz | mariadb -u root -p<ROOT_PASSWORD>"
```

### Вариант 3: Импортирай директно от host файла

```bash
# Ако файлът е на host сървъра, импортирай директно
cat /root/biblioman.sql | docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD>
```

## Стъпка 2: Проверка след импорт

```bash
# Провери дали таблицата book съществува
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SHOW TABLES;"

# Провери броя на книгите
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SELECT COUNT(*) FROM book;"
```

## Стъпка 3: Тествай с Python скрипта

```bash
cd ~/mybibliotheca
source venv/bin/activate
python scripts/test_biblioman_connection.py
```

## Важни бележки:

1. **Заменяй `<ROOT_PASSWORD>`** с действителната root парола от Coolify
2. **Ако базата данни вече съществува**, може да трябва да я изтриеш първо:
   ```sql
   DROP DATABASE IF EXISTS biblioman;
   CREATE DATABASE biblioman CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. **Ако SQL файлът не създава базата данни**, създай я първо:
   ```sql
   CREATE DATABASE IF NOT EXISTS biblioman CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

