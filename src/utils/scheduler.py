import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, time, timedelta
import pytz

from src.db import database as db
from src.keyboards.inline import get_answer_qotd_kb


# --- Основные задачи планировщика ---

async def check_and_send_compliments(bot: Bot):
    """Проверяет и отправляет запланированные комплименты."""
    compliments = await db.get_due_compliments()
    if not compliments: return

    logging.info(f"Scheduler: Найдено {len(compliments)} комплиментов для отправки.")
    for compliment in compliments:
        try:
            from_user = await db.get_user(compliment['sender_id'])
            from_user_name = from_user['username'] if from_user else "Ваш партнер"

            full_message = f"💌 Вам пришел отложенный комплимент от {from_user_name}:\n\n✨ «{compliment['text']}» ✨"

            if compliment['attachment_file_id']:
                attachment_type = compliment['attachment_type']
                file_id = compliment['attachment_file_id']
                caption = compliment['caption']

                await bot.send_message(chat_id=compliment['receiver_id'], text=full_message)

                if attachment_type == 'photo':
                    await bot.send_photo(chat_id=compliment['receiver_id'], photo=file_id, caption=caption)
                elif attachment_type == 'video':
                    await bot.send_video(chat_id=compliment['receiver_id'], video=file_id, caption=caption)
                elif attachment_type == 'voice':
                    await bot.send_voice(chat_id=compliment['receiver_id'], voice=file_id, caption=caption)
                elif attachment_type == 'video_note':
                    await bot.send_video_note(chat_id=compliment['receiver_id'], video_note=file_id)
            else:
                await bot.send_message(chat_id=compliment['receiver_id'], text=full_message)

            await db.delete_compliment(compliment['id'])
            logging.info(f"Scheduler: Комплимент {compliment['id']} успешно отправлен.")
        except Exception as e:
            logging.error(f"Scheduler: Не удалось отправить комплимент {compliment['id']}: {e}")


async def master_scheduler_task(bot: Bot):
    """Главная задача, которая запускается каждую минуту и управляет всеми событиями."""
    moscow_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)
    current_time_str = now.strftime("%H:%M")

    all_couples = await db.get_all_couples_with_settings()

    for couple in all_couples:
        # --- 1. Напоминания о событиях ---
        if couple['reminders_enabled'] and couple['reminder_time'] == current_time_str:
            await send_event_reminders_for_couple(bot, couple, now)

        # --- 2. Вопрос дня ---
        if couple['qotd_enabled']:
            # 2a. Отправка вопроса
            if couple['qotd_send_time'] == current_time_str:
                await send_qotd_to_couple(bot, couple)

            # 2b. Напоминание и итоги
            summary_time = datetime.strptime(couple['qotd_summary_time'], "%H:%M").time()
            reminder_time = (datetime.combine(now.date(), summary_time) - timedelta(hours=1)).time()

            if reminder_time.strftime("%H:%M") == current_time_str:
                await send_qotd_reminder_to_couple(bot, couple)

            if couple['qotd_summary_time'] == current_time_str:
                await send_qotd_summary_to_couple(bot, couple)


# --- Вспомогательные функции для master_scheduler_task ---

async def send_event_reminders_for_couple(bot: Bot, couple: dict, now: datetime):
    """Отправляет напоминание о событиях на сегодня для одной пары."""
    couple_id = couple['couple_id']
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    events = await db.get_events_for_period(couple_id, today_start, today_end)
    if not events: return

    response_text = "<b>Доброе утро! Напоминаю о ваших планах на сегодня:</b>\n\n"
    for event in events:
        event_datetime = datetime.fromisoformat(event['event_date'])
        time_str = event_datetime.strftime("%H:%M")
        response_text += f"• <b>{time_str}</b> - {event['title']} 🗓️\n"
    response_text += "\nХорошего дня! ❤️"

    try:
        await bot.send_message(couple['user1_id'], response_text)
        await bot.send_message(couple['user2_id'], response_text)
        logging.info(f"Scheduler: Напоминание о событиях отправлено паре {couple_id}")
    except Exception as e:
        logging.error(f"Scheduler: Не удалось отправить напоминание паре {couple_id}: {e}")


async def send_qotd_to_couple(bot: Bot, couple: dict):
    """Отправляет вопрос дня одной паре."""
    question = await db.get_random_question()
    if not question: return

    await db.create_daily_question_entry(couple['couple_id'], question['question_id'], couple['user1_id'],
                                         couple['user2_id'])

    text = f"<b>❓ Вопрос дня для вас двоих:</b>\n\n{question['text']}"
    try:
        await bot.send_message(couple['user1_id'], text, reply_markup=get_answer_qotd_kb())
        await bot.send_message(couple['user2_id'], text, reply_markup=get_answer_qotd_kb())
        logging.info(f"Scheduler: Вопрос дня отправлен паре {couple['couple_id']}")
    except Exception as e:
        logging.error(f"Scheduler: Не удалось отправить вопрос дня паре {couple['couple_id']}: {e}")


async def send_qotd_reminder_to_couple(bot: Bot, couple: dict):
    """Отправляет напоминание об ответе на вопрос дня."""
    answers = await db.get_today_question_for_couple(couple['couple_id'])
    if not answers or (answers['answer_user1'] and answers['answer_user2']): return

    reminder_text = "Напоминаю, что ваш партнер уже ответил на вопрос дня. Мы ждем только вас! 😉"
    try:
        if not answers['answer_user1']:
            await bot.send_message(answers['user1_id'], reminder_text)
        if not answers['answer_user2']:
            await bot.send_message(answers['user2_id'], reminder_text)
        logging.info(f"Scheduler: Напоминание о вопросе дня отправлено паре {couple['couple_id']}")
    except Exception as e:
        logging.error(f"Scheduler: Не удалось отправить напоминание о вопросе дня паре {couple['couple_id']}: {e}")


async def send_qotd_summary_to_couple(bot: Bot, couple: dict):
    """Отправляет итоги с ответами."""
    answers = await db.get_today_question_for_couple(couple['couple_id'])
    if not answers: return

    user1_answer = answers['answer_user1'] or "<i>(нет ответа)</i>"
    user2_answer = answers['answer_user2'] or "<i>(нет ответа)</i>"

    # Получаем имена пользователей
    user1 = await db.get_user(answers['user1_id'])
    user2 = await db.get_user(answers['user2_id'])
    user1_name = user1['username'] if user1 else "Партнер 1"
    user2_name = user2['username'] if user2 else "Партнер 2"

    summary_text = (
        f"<b>Ответы на вопрос дня:</b>\n"
        f"<i>{answers['question_text']}</i>\n\n"
        f"<b>Ответ {user1_name}:</b>\n{user1_answer}\n\n"
        f"<b>Ответ {user2_name}:</b>\n{user2_answer}"
    )

    try:
        await bot.send_message(answers['user1_id'], summary_text)
        await bot.send_message(answers['user2_id'], summary_text)
        logging.info(f"Scheduler: Итоги по вопросу дня отправлены паре {couple['couple_id']}")
    except Exception as e:
        logging.error(f"Scheduler: Не удалось отправить итоги по вопросу дня паре {couple['couple_id']}: {e}")


def setup_scheduler(bot: Bot):
    """Настраивает и запускает планировщик задач."""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(check_and_send_compliments, 'interval', minutes=1, args=(bot,))
    scheduler.add_job(master_scheduler_task, 'interval', minutes=1, args=(bot,))
    return scheduler
