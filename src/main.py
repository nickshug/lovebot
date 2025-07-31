import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from src.config import BOT_TOKEN
from src.db import database as db
from src.handlers import common, pairing, actions, calendar, settings, wishlist, qotd, memories, movies, dates
from src.utils.scheduler import setup_scheduler

async def set_main_menu(bot: Bot):
    """
    Создает и устанавливает основное меню команд для бота.
    """
    main_menu_commands = [
        BotCommand(command="/start", description="Перезапустить бота"),
        BotCommand(command="/help", description="Помощь и список команд"),
        BotCommand(command="/settings", description="⚙️ Настройки пары"),

        BotCommand(command="/compliment", description="💌 Отправить комплимент"),

        BotCommand(command="/addevent", description="🗓️ Добавить событие в календарь"),
        BotCommand(command="/events", description="🗓️ Посмотреть события"),
        BotCommand(command="/delevent", description="🗓️ Удалить событие"),

        BotCommand(command="/addwish", description="🎁 Добавить желание в вишлист"),
        BotCommand(command="/wishlist", description="🎁 Посмотреть вишлисты"),
        BotCommand(command="/delwish", description="🎁 Удалить желание"),

        BotCommand(command="/addquestion", description="❓ Добавить свой Вопрос дня"),
        BotCommand(command="/answers", description="❓ Архив ответов"),

        BotCommand(command="/addmemory", description="📸 Добавить воспоминание"),
        BotCommand(command="/memory", description="📸 Случайное воспоминание"),
        BotCommand(command="/allmemories", description="📸 Все воспоминания"),

        # BotCommand(command="/movie", description="🎬 Кинорулетка"),
        BotCommand(command="/addmovie", description="🎬 Добавить фильм в список"),
        BotCommand(command="/watchlist", description="🎬 Список фильмов к просмотру"),
        BotCommand(command="/delmovie", description="🎬 Удалить фильм из списка"),

        BotCommand(command="/add_date_idea", description="💖 Добавить идею для свидания"),
        BotCommand(command="/date_ideas", description="💖 Посмотреть идеи для свиданий"),
        BotCommand(command="/del_date_idea", description="💖 Удалить идею")
    ]
    await bot.set_my_commands(main_menu_commands)


async def main():
    """
    Основная функция, которая запускает бота.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logging.info("Запускаю бота...")

    await db.db_start()
    await db.add_questions_to_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logging.info("Планировщик запущен.")

    # Регистрация роутеров
    dp.include_router(common.router)
    dp.include_router(pairing.router)
    dp.include_router(actions.router)
    dp.include_router(calendar.router)
    dp.include_router(settings.router)
    dp.include_router(wishlist.router)
    dp.include_router(qotd.router)
    dp.include_router(memories.router)
    dp.include_router(movies.router)
    dp.include_router(dates.router)

    # --- УСТАНАВЛИВАЕМ МЕНЮ КОМАНД ---
    await set_main_menu(bot)

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен пользователем.")
