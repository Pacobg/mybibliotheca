# Тестване на Biblioman Connection

## Вариант 1: Инсталирай MariaDB Client

```bash
# На dev сървъра
sudo apt-get update
sudo apt-get install mariadb-client

# След това тествай
mysql -h 192.168.1.13 -P 3307 -u root -pL3mongate189 biblioman -e "SELECT COUNT(*) FROM book;"
```

## Вариант 2: Тествай с Python (без инсталация на mysql client)

Създай временен Python скрипт за тестване:

```bash
cd ~/mybibliotheca
cat > test_biblioman.py << 'EOF'
import mysql.connector

try:
    conn = mysql.connector.connect(
        host='192.168.1.13',
        port=3307,
        user='root',
        password='L3mongate189',
        database='biblioman',
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM book")
    count = cursor.fetchone()[0]
    print(f"✅ Connection successful! Found {count} books in biblioman database.")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
EOF

# Активирай virtual environment и тествай
source venv/bin/activate
python test_biblioman.py
```

## Вариант 3: Тествай директно от MyBibliotheca приложението

След като конфигурираш `.env` файла и рестартираш приложението, провери логовете:

```bash
# Стартирай приложението
cd ~/mybibliotheca
source venv/bin/activate
python dev_run.py

# В друг терминал, провери логовете за Biblioman connection
tail -f ~/mybibliotheca/logs/*.log | grep -i biblioman
```

Търси за:
- `Biblioman database connection established` - успешно свързване
- `Biblioman connection failed` - проблем със свързването

## Вариант 4: Тествай чрез MyBibliotheca API

След като приложението работи, тествай search с българска книга:

1. Отвори браузър: `http://192.168.1.51:5054/books/add`
2. Търси: "Морето на спокойствието"
3. Провери дали виждаш резултати от Biblioman

## Проверка на .env файла

Уверете се че `.env` файлът съществува и има правилните стойности:

```bash
cd ~/mybibliotheca
cat .env | grep BIBLIOMAN
```

Трябва да видиш:
```
BIBLIOMAN_ENABLED=true
BIBLIOMAN_HOST=192.168.1.13
BIBLIOMAN_PORT=3307
BIBLIOMAN_USER=root
BIBLIOMAN_PASSWORD=L3mongate189
BIBLIOMAN_DATABASE=biblioman
```

Ако няма `.env` файл, създай го:

```bash
cd ~/mybibliotheca
nano .env
```

И добави горните редове.

