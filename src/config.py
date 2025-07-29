import os
from pathlib import Path
from dotenv import load_dotenv

# Определяем корневую директорию проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные из .env файла, который лежит в корне
load_dotenv(BASE_DIR / ".env")

# Читаем токены
BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if os.getenv('RENDER'):
    DB_PATH = Path("/data/lovebot.db")
else:
    DB_PATH = BASE_DIR / "lovebot.db"

# Проверки на наличие токенов
if not BOT_TOKEN:
    print("Ошибка: не найден BOT_TOKEN. Убедитесь, что он есть в .env или в переменных окружения хостинга.")
    exit()

if not TMDB_API_KEY:
    print("Ошибка: не найден TMDB_API_KEY. Убедитесь, что он есть в .env или в переменных окружения хостинга.")
    exit()
