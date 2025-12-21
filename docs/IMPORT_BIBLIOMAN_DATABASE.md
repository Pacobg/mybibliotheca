# Импортиране на Biblioman база данни

## Проблем: Базата данни съществува, но няма таблици

Ако базата данни `biblioman` съществува, но няма таблици, това означава че импортът не е работил правилно.

## Решение: Провери SQL файла и импортирай правилно

### Стъпка 1: Провери какво има в SQL файла

```bash
# Провери първите редове на SQL файла
head -n 50 /root/biblioman.sql

# Търси за CREATE DATABASE или USE команди
grep -i "CREATE DATABASE\|USE " /root/biblioman.sql | head -5
```

### Стъпка 2: Импортирай правилно

#### Вариант A: Ако SQL файлът създава базата данни

```bash
# Импортирай без да указваш базата данни (SQL файлът ще я създаде)
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> < /root/biblioman.sql
```

#### Вариант B: Ако SQL файлът НЕ създава базата данни

```bash
# Първо изтрий старата база данни (ако има проблеми)
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "DROP DATABASE IF EXISTS biblioman; CREATE DATABASE biblioman CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# След това импортирай
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> biblioman < /root/biblioman.sql
```

#### Вариант C: Използвай файла от контейнера

```bash
# Копирай файла в контейнера (ако още не е копиран)
docker cp /root/biblioman.sql ossoo808goc4cw4wos8sg0so:/tmp/biblioman.sql

# Импортирай от контейнера
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> < /tmp/biblioman.sql
```

### Стъпка 3: Проверка след импорт

```bash
# Провери дали таблицата book съществува
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SHOW TABLES;"

# Провери броя на книгите
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SELECT COUNT(*) FROM book;"

# Провери структурата на таблицата book
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; DESCRIBE book;"
```

### Стъпка 4: Тествай с Python скрипта

```bash
cd ~/mybibliotheca
source venv/bin/activate
python scripts/test_biblioman_connection.py
```

## Troubleshooting

### Ако все още няма таблици след импорт:

1. **Провери дали SQL файлът е валиден:**
   ```bash
   # Провери синтаксиса
   head -n 100 /root/biblioman.sql
   ```

2. **Провери дали има грешки при импорт:**
   ```bash
   # Импортирай и виж грешките
   docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> < /root/biblioman.sql 2>&1 | grep -i error
   ```

3. **Опитай да импортираш на части:**
   ```bash
   # Първо създай базата данни
   docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "CREATE DATABASE IF NOT EXISTS biblioman CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
   
   # След това импортирай
   docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> biblioman < /root/biblioman.sql
   ```

## Важни бележки:

1. **Заменяй `<ROOT_PASSWORD>`** с действителната root парола от Coolify
2. **Импортът може да отнеме време** за големи SQL файлове (211MB е доста голям файл)
3. **Провери логовете** за грешки по време на импорта
4. **Ако SQL файлът създава базата данни**, не указвай базата данни в командата
5. **Ако SQL файлът НЕ създава базата данни**, създай я първо и след това импортирай
