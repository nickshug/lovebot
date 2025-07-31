from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from src.db import database as db

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start.
    Регистрирует пользователя и показывает приветственное сообщение.
    """
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    await db.add_user(user_id, username)
    user_data = await db.get_user(user_id)

    if user_data and user_data['partner_id']:
        partner = await db.get_partner(user_id)
        await message.answer(
            f"Привет, {username}! ❤️\n"
            f"Вы в паре с {partner['username']}.\n\n"
            "Используйте /help, чтобы увидеть список доступных команд."
        )
    else:
        text = (
            f"Привет, {username}! ✨\n"
            "Это бот для вас и вашей второй половинки.\n\n"
            "<b>Как создать пару:</b>\n"
            "1. Один из вас должен получить код по команде /code.\n"
            "2. Второй партнер просто отправляет этот код мне в чат.\n\n"
            "Если у тебя уже есть код от партнера — смело отправляй его сюда!"
        )
        await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Обработчик команды /help.
    """
    text = (
        "<b>Основные команды:</b>\n"
        "/start - Перезапустить бота\n"
        "/code - Получить код для приглашения\n"
        "/unlink - Разорвать связь с партнером\n\n"
        "<b>Функции для пары:</b>\n"
        "/compliment - Отправить комплимент\n"
        "/addevent - Добавить событие в календарь\n"
        "/events - Посмотреть ваши события\n"
        "/delevent - Удалить событие из календаря\n"
        "/settings - Настройки напоминаний\n\n"
        "<b>Вишлист:</b>\n"
        "/addwish - Добавить желание в свой список\n"
        "/wishlist - Посмотреть вишлисты\n"
        "/delwish - Удалить желание из своего списка\n\n"
        "<b>Вопрос дня:</b>\n"
        "/addquestion - Добавить свой вопрос в базу\n"
        "/answers - Посмотреть архив ответов\n\n"
        "<b>Капсула Памяти:</b>\n"
        "/addmemory - Добавить воспоминание\n"
        "/memory - Посмотреть случайное воспоминание\n"
        "/allmemories - Посмотреть все воспоминания\n\n"
        "<b>Кино и сериалы:</b>\n"
        # "/movie - Кинорулетка для выбора фильма\n"
        "/addmovie - Добавить фильм в список вручную\n"
        "/watchlist - Посмотреть ваш список фильмов\n"
        "/delmovie - Удалить фильм из списка\n"
        "\n<b>Идеи для свиданий:</b>\n"
        "/add_date_idea - Добавить идею в список\n"
        "/date_ideas - Посмотреть и отметить идеи\n"
        "/del_date_idea - Удалить идею из списка"
    )
    await message.answer(text)
