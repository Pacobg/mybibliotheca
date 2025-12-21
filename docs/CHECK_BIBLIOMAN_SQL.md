# Проверка на Biblioman SQL файл

## Стъпка 1: Провери структурата на SQL файла

```bash
# Провери първите 100 реда за CREATE TABLE statements
head -n 100 /root/biblioman.sql | grep -i "CREATE TABLE"

# Провери дали има CREATE DATABASE statement
head -n 50 /root/biblioman.sql | grep -i "CREATE DATABASE\|USE "

# Провери дали има DROP TABLE statements
head -n 100 /root/biblioman.sql | grep -i "DROP TABLE"
```

## Стъпка 2: Импортирай според структурата

### Ако SQL файлът съдържа CREATE TABLE statements:

```bash
# Импортирай директно (SQL файлът ще създаде таблиците)
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> biblioman < /root/biblioman.sql
```

### Ако SQL файлът съдържа само INSERT statements:

Трябва първо да създадеш таблиците. Провери дали има schema файл или създай таблиците ръчно.

### Ако SQL файлът създава базата данни:

```bash
# Импортирай БЕЗ да указваш базата данни
docker exec -i ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> < /root/biblioman.sql
```

## Стъпка 3: Проверка

```bash
# Провери таблиците
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SHOW TABLES;"

# Провери броя на записите
docker exec -it ossoo808goc4cw4wos8sg0so mariadb -u root -p<ROOT_PASSWORD> -e "USE biblioman; SELECT COUNT(*) FROM book;"
```

