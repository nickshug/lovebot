import logging
from datetime import datetime, timedelta
import pytz
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from itertools import groupby

from src.db import database as db
from src.states.user_states import Calendar
from src.keyboards.inline import get_events_period_kb, get_skip_details_kb, get_date_selection_kb, get_delete_event_kb

router = Router()

WEEKDAYS_RU = {
    "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
    "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье"
}


@router.message(Command("addevent"))
async def cmd_addevent(message: types.Message, state: FSMContext):
    await state.clear()
    user_data = await db.get_user(message.from_user.id)
    if not user_data or not user_data['partner_id']:
        await message.answer("Эта команда доступна только для пар.")
        return

    await state.set_state(Calendar.waiting_for_event_date)
    await message.answer(
        "На какую дату планируем событие? Выберите или введите вручную (ДД.ММ.ГГГГ).",
        reply_markup=get_date_selection_kb()
    )


@router.callback_query(Calendar.waiting_for_event_date, F.data.startswith("date_"))
async def process_event_date_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    date_choice = callback.data.split("_")[1]
    send_date = None
    if date_choice == "today":
        send_date = datetime.now().date()
    elif date_choice == "tomorrow":
        send_date = (datetime.now() + timedelta(days=1)).date()

    await state.update_data(event_date=send_date)
    await callback.message.edit_text("Отлично! Теперь введите время в формате ЧЧ:ММ.")
    await state.set_state(Calendar.waiting_for_event_time)


@router.message(Calendar.waiting_for_event_date, F.text)
async def process_event_date_text(message: types.Message, state: FSMContext):
    try:
        send_date = datetime.strptime(message.text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ.")
        return
    if send_date < datetime.now().date():
        await message.answer("Эта дата уже в прошлом!")
        return
    await state.update_data(event_date=send_date)
    await message.answer("Отлично! Теперь введите время в формате ЧЧ:ММ.")
    await state.set_state(Calendar.waiting_for_event_time)


@router.message(Calendar.waiting_for_event_time, F.text)
async def process_event_time(message: types.Message, state: FSMContext):
    try:
        user_time = datetime.strptime(message.text, "%H:%M").time()
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите время в формате ЧЧ:ММ.")
        return

    data = await state.get_data()
    event_date = data.get('event_date')

    naive_event_datetime = datetime.combine(event_date, user_time)

    moscow_tz = pytz.timezone("Europe/Moscow")
    aware_event_datetime = moscow_tz.localize(naive_event_datetime)
    now_aware = datetime.now(moscow_tz)

    if aware_event_datetime < now_aware:
        await message.answer("Это время уже прошло! Пожалуйста, выберите будущее время.")
        return

    await state.update_data(event_time=user_time)
    await message.answer("Принято! Теперь введите короткое название события (например, 'Ужин в ресторане').")
    await state.set_state(Calendar.waiting_for_event_title)


@router.message(Calendar.waiting_for_event_title, F.text)
async def process_event_title(message: types.Message, state: FSMContext):
    await state.update_data(event_title=message.text)
    await message.answer(
        "Хотите добавить детали? (например, 'Забронирован столик у окна'). Нажмите 'Пропустить', если не нужно.",
        reply_markup=get_skip_details_kb())
    await state.set_state(Calendar.waiting_for_event_details)


async def finalize_event_creation(user_id: int, bot: Bot, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    user = await db.get_user(user_id)
    partner = await db.get_partner(user_id)

    event_date = data['event_date']
    event_time = data['event_time']
    event_title = data['event_title']
    event_details = data.get('event_details')

    full_event_date = datetime.combine(event_date, event_time)

    couple_id = min(user_id, partner['user_id'])

    await db.add_event(couple_id, full_event_date, event_title, event_details)

    event_date_str = full_event_date.strftime('%d.%m.%Y в %H:%M')
    await bot.send_message(user_id, f"✅ Событие добавлено: {event_date_str} - {event_title}")

    try:
        await bot.send_message(
            partner['user_id'],
            f"🔔 {user['username']} добавил(а) новое событие: {event_date_str} - {event_title}"
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить партнера {partner['user_id']} о новом событии: {e}")


@router.message(Calendar.waiting_for_event_details, F.text)
async def process_event_details(message: types.Message, state: FSMContext):
    await state.update_data(event_details=message.text)
    await finalize_event_creation(message.from_user.id, message.bot, state)


@router.callback_query(Calendar.waiting_for_event_details, F.data == "skip_details")
async def process_skip_details(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await finalize_event_creation(callback.from_user.id, callback.bot, state)


@router.message(Command("events"))
async def cmd_events(message: types.Message, state: FSMContext):
    await state.clear()
    user_data = await db.get_user(message.from_user.id)
    if not user_data or not user_data['partner_id']:
        await message.answer("Эта команда доступна только для пар.")
        return
    await message.answer("За какой период показать события?", reply_markup=get_events_period_kb())


@router.callback_query(F.data.startswith("events_"))
async def process_events_period(callback: types.CallbackQuery):
    period = callback.data.split("_")[1]
    user_id = callback.from_user.id
    partner = await db.get_partner(user_id)
    couple_id = min(user_id, partner['user_id'])

    now = datetime.now()
    start_date = now
    end_date = None
    title = ""

    if period == "today":
        end_date = start_date.replace(hour=23, minute=59, second=59)
        title = "Планы на сегодня:"
    elif period == "week":
        end_date = start_date + timedelta(days=7)
        title = "Планы на неделю:"
    elif period == "month":
        end_date = start_date + timedelta(days=30)
        title = "Планы на месяц:"
    elif period == "all":
        end_date = start_date + timedelta(days=365 * 5)
        title = "Все предстоящие планы:"

    events = await db.get_events_for_period(couple_id, start_date, end_date)

    if not events:
        await callback.answer()
        await callback.message.edit_text(
            "На этот период планов нет. 😕\n\n"
            "Попробуйте выбрать другой период или добавьте новое событие командой /addevent.",
            reply_markup=get_events_period_kb()
        )
        return

    response_text = f"<b>{title}</b>\n\n"

    key_func = lambda e: datetime.fromisoformat(e['event_date']).date()

    for event_date, daily_events in groupby(events, key=key_func):
        day_of_week_en = event_date.strftime("%A")
        day_of_week_ru = WEEKDAYS_RU.get(day_of_week_en, day_of_week_en)
        day_str = event_date.strftime(f"{day_of_week_ru}, %d.%m")
        response_text += f"————— <b>{day_str}</b> —————\n"

        for event in daily_events:
            event_datetime = datetime.fromisoformat(event['event_date'])
            time_str = event_datetime.strftime("%H:%M")
            response_text += f"    {time_str} - {event['title']}\n"
            if event['details']:
                response_text += f"         <i>└ {event['details']}</i>\n"
        response_text += "\n"

    response_text += "\nЧтобы удалить событие, используйте команду /delevent."
    await callback.message.edit_text(response_text)


@router.message(Command("delevent"))
async def cmd_delevent(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    partner = await db.get_partner(user_id)
    if not partner:
        await message.answer("Эта команда доступна только для пар.")
        return

    couple_id = min(user_id, partner['user_id'])
    now = datetime.now()
    events = await db.get_events_for_period(couple_id, now, now + timedelta(days=365 * 5))

    if not events:
        await message.answer("У вас нет предстоящих событий для удаления.")
        return

    await message.answer(
        "Какое событие вы хотите удалить?",
        reply_markup=get_delete_event_kb(events)
    )


@router.callback_query(F.data.startswith("del_event_"))
async def process_del_event(callback: types.CallbackQuery):
    event_id = int(callback.data.split("_")[-1])

    user_id = callback.from_user.id
    partner = await db.get_partner(user_id)
    couple_id = min(user_id, partner['user_id'])
    event = await db.get_event_by_id(event_id, couple_id)

    if not event:
        await callback.answer("Событие не найдено или уже удалено.", show_alert=True)
        await callback.message.delete()
        return

    await db.delete_event_by_id(event_id)
    await callback.message.edit_text(f"✅ Событие '{event['title']}' удалено.")

    try:
        await callback.bot.send_message(
            partner['user_id'],
            f"🔔 {callback.from_user.username} удалил(а) событие: '{event['title']}'"
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить партнера об удалении события: {e}")


@router.callback_query(F.data.startswith("event_page_"))
async def process_event_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    partner = await db.get_partner(user_id)
    couple_id = min(user_id, partner['user_id'])
    now = datetime.now()
    events = await db.get_events_for_period(couple_id, now, now + timedelta(days=365 * 5))

    await callback.message.edit_reply_markup(reply_markup=get_delete_event_kb(events, page))
