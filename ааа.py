import os
import logging

# --- Настройка логирования для вывода информации о создании ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- Определение структуры проекта ---
PROJECT_STRUCTURE = [
    "lovebot/",
    "lovebot/.env",
    "lovebot/requirements.txt",
    "lovebot/src/",
    "lovebot/src/__init__.py",
    "lovebot/src/main.py",
    "lovebot/src/config.py",
    "lovebot/src/handlers/",
    "lovebot/src/handlers/__init__.py",
    "lovebot/src/handlers/common.py",
    "lovebot/src/handlers/pairing.py",
    "lovebot/src/handlers/actions.py",
    "lovebot/src/keyboards/",
    "lovebot/src/keyboards/__init__.py",
    "lovebot/src/keyboards/inline.py",
    "lovebot/src/db/",
    "lovebot/src/db/__init__.py",
    "lovebot/src/db/database.py",
    "lovebot/src/states/",
    "lovebot/src/states/__init__.py",
    "lovebot/src/states/user_states.py",
    "lovebot/src/utils/",
    "lovebot/src/utils/__init__.py",
    "lovebot/src/utils/scheduler.py",
]

# --- Содержимое для файлов по умолчанию ---
FILE_CONTENTS = {
    "lovebot/.env": "BOT_TOKEN=ВАШ_ТЕЛЕГРАМ_ТОКЕН_СЮДА",
    "lovebot/requirements.txt": (
        "aiogram>=3.2.0\n"
        "python-dotenv>=1.0.0\n"
        "apscheduler>=3.10.0\n"
        "aiosqlite>=0.19.0\n"
    ),
    # Добавим "заглушки" в некоторые файлы, чтобы они не были совсем пустыми
    "lovebot/src/main.py": (
        "import asyncio\nimport logging\n\n\n"
        "async def main():\n"
        '    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")\n'
        '    logging.info("Starting bot...")\n\n\n'
        "if __name__ == '__main__':\n"
        "    try:\n"
        "        asyncio.run(main())\n"
        "    except (KeyboardInterrupt, SystemExit):\n"
        '        logging.info("Bot stopped.")\n'
    ),
    "lovebot/src/handlers/common.py": (
        "from aiogram import Router\n"
        "from aiogram.filters import CommandStart\n"
        "from aiogram.types import Message\n\n"
        "router = Router()\n\n\n"
        "@router.message(CommandStart())\n"
        "async def cmd_start(message: Message):\n"
        '    await message.answer("Привет! ❤️")\n'
    )
}


def create_project_structure():
    """
    Создает папки и файлы согласно определенной структуре.
    """
    logging.info("Начинаю создание структуры проекта 'lovebot'...")

    for path in PROJECT_STRUCTURE:
        # Проверяем, папка это или файл
        if path.endswith('/'):
            # Создаем директорию, exist_ok=True предотвращает ошибку, если папка уже есть
            os.makedirs(path, exist_ok=True)
            logging.info(f"Создана директория: {path}")
        else:
            # Создаем файл
            try:
                # Открываем файл в режиме записи, это создаст его, если он не существует
                with open(path, 'w', encoding='utf-8') as f:
                    # Если для файла есть содержимое по умолчанию, записываем его
                    if path in FILE_CONTENTS:
                        f.write(FILE_CONTENTS[path])
                logging.info(f"Создан файл: {path}")
            except IOError as e:
                logging.error(f"Не удалось создать файл {path}: {e}")

    logging.info("Структура проекта 'lovebot' успешно создана! ✅")


if __name__ == "__main__":
    create_project_structure()
