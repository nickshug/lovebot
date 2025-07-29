from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime

from src.db import database as db
from src.states.user_states import Settings
from src.keyboards.inline import get_settings_kb

router = Router()


async def get_couple_id(user_id: int):
    """Вспомогательная функция для получения ID пары."""
    partner = await db.get_partner(user_id)
    if not partner:
        return None
    # ID пары - это меньший из ID партнеров, чтобы был уникальным и постоянным
    return min(user_id, partner['user_id'])


async def show_settings_menu(message: types.Message, couple_id: int):
    """Отображает или обновляет меню настроек."""
    settings = await db.get_couple_settings(couple_id)
    await message.answer(
        "<b>⚙️ Настройки вашей пары:</b>",
        reply_markup=get_settings_kb(settings)
    )


@router.message(Command("settings"))
async def cmd_settings(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        await message.answer("Эта команда доступна только для пар.")
        return
    await show_settings_menu(message, couple_id)


# --- Настройки напоминаний о событиях ---

@router.callback_query(F.data == "settings_enable")
async def process_reminders_enable(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Settings.waiting_for_reminder_time)
    await callback.message.edit_text(
        "Отлично! В какое время вам удобно получать напоминания о планах на день? (укажите в формате ЧЧ:ММ, например, 09:00)")


@router.callback_query(F.data == "settings_disable")
async def process_reminders_disable(callback: types.CallbackQuery):
    couple_id = await get_couple_id(callback.from_user.id)
    settings = await db.get_couple_settings(couple_id)
    await db.update_reminders_settings(couple_id, reminders_enabled=False)
    await callback.answer("Напоминания о событиях выключены 🔕")
    new_settings = await db.get_couple_settings(couple_id)
    await callback.message.edit_text("<b>⚙️ Настройки вашей пары:</b>", reply_markup=get_settings_kb(new_settings))


@router.callback_query(F.data == "settings_changetime")
async def process_reminders_change_time(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Settings.waiting_for_reminder_time)
    await callback.message.edit_text("Введите новое время для напоминаний о событиях (в формате ЧЧ:ММ).")


@router.message(Settings.waiting_for_reminder_time, F.text)
async def process_reminder_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите время в формате ЧЧ:ММ.")
        return

    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    await db.update_reminders_settings(couple_id, reminders_enabled=True, reminder_time=message.text)
    await message.answer(f"Отлично! Напоминания о событиях будут приходить ежедневно в {message.text}.")
    await show_settings_menu(message, couple_id)


# --- Настройки "Вопроса дня" ---

@router.callback_query(F.data == "settings_qotd_enable")
async def process_qotd_enable(callback: types.CallbackQuery, state: FSMContext):
    couple_id = await get_couple_id(callback.from_user.id)
    await db.update_reminders_settings(couple_id, qotd_enabled=True)
    await callback.answer("Вопрос дня включен 🔔")
    new_settings = await db.get_couple_settings(couple_id)
    await callback.message.edit_reply_markup(reply_markup=get_settings_kb(new_settings))


@router.callback_query(F.data == "settings_qotd_disable")
async def process_qotd_disable(callback: types.CallbackQuery):
    couple_id = await get_couple_id(callback.from_user.id)
    await db.update_reminders_settings(couple_id, qotd_enabled=False)
    await callback.answer("Вопрос дня выключен 🔕")
    new_settings = await db.get_couple_settings(couple_id)
    await callback.message.edit_reply_markup(reply_markup=get_settings_kb(new_settings))


@router.callback_query(F.data == "settings_qotd_changetime")
async def process_qotd_change_time(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Settings.waiting_for_qotd_send_time)
    await callback.message.edit_text("Введите время для отправки вопроса (например, 12:00).")


@router.message(Settings.waiting_for_qotd_send_time, F.text)
async def process_qotd_send_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите время в формате ЧЧ:ММ.")
        return
    await state.update_data(qotd_send_time=message.text)
    await state.set_state(Settings.waiting_for_qotd_summary_time)
    await message.answer("Отлично. Теперь введите время для получения итогов с ответами (например, 20:00).")


@router.message(Settings.waiting_for_qotd_summary_time, F.text)
async def process_qotd_summary_time(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите время в формате ЧЧ:ММ.")
        return

    data = await state.get_data()
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    await db.update_reminders_settings(
        couple_id,
        qotd_enabled=True,
        qotd_send_time=data['qotd_send_time'],
        qotd_summary_time=message.text
    )
    await message.answer("Время для 'Вопроса дня' успешно обновлено!")
    await show_settings_menu(message, couple_id)
