# Импортиране на Biblioman база данни

## Стъпка 1: Копирай SQL файла в контейнера

```bash
# Копирай файла в контейнера
docker cp /root/biblioman.sql ossoo808goc4cw4wos8sg0so:/tmp/biblioman.sql
```

## Стъпка 2: Импортирай в MariaDB

### Вариант 1: Използвай базата данни в командата (Препоръчително)

```bash
# Импортирай директно в biblioman базата данни
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> biblioman < /root/biblioman.sql
```

Или ако използваш файла от контейнера:

```bash
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> biblioman < /tmp/biblioman.sql
```

### Вариант 2: Създай базата данни първо, след това импортирай

```bash
# Първо създай базата данни
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "CREATE DATABASE IF NOT EXISTS biblioman CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# След това импортирай
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> biblioman < /root/biblioman.sql
```

### Вариант 3: Ако SQL файлът е компресиран (.sql.gz)

```bash
# Копирай файла в контейнера
docker cp /root/biblioman.sql.gz ossoo808goc4cw4wos8sg0so:/tmp/biblioman.sql.gz

# Декомпресирай и импортирай
docker exec -i ossoo808goc4cw4wos8sg0so bash -c "gunzip < /tmp/biblioman.sql.gz | mariadb -u root -p<ROOT_PASSWORD> biblioman"
```

## Стъпка 3: Проверка след импорт

```bash
# Провери дали таблицата book съществува
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SHOW TABLES;"

# Провери броя на книгите
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SELECT COUNT(*) FROM book;"

# Провери структурата на таблицата book
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; DESCRIBE book;"
```

## Стъпка 4: Тествай с Python скрипта

```bash
cd ~/mybibliotheca
git pull origin main
source venv/bin/activate
python scripts/test_biblioman_connection.py
```

## Важни бележки:

1. **Заменяй `<ROOT_PASSWORD>`** с действителната root парола от Coolify
2. **Важно:** Добави `biblioman` след паролата в командата - това избира базата данни преди импорта
3. **Ако базата данни вече съществува**, може да трябва да я изтриеш първо:
   ```sql
   DROP DATABASE IF EXISTS biblioman;
   CREATE DATABASE biblioman CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
4. **Импортът може да отнеме време** за големи SQL файлове (211MB е доста голям файл)
