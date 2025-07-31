from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime

from src.db import database as db
from src.states.user_states import QOTD
from src.keyboards.inline import get_qotd_archive_kb

router = Router()

async def get_couple_id(user_id: int):
    partner = await db.get_partner(user_id)
    return min(user_id, partner['user_id']) if partner else None


@router.message(Command("addquestion"))
async def cmd_addquestion(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(QOTD.waiting_for_new_question)
    await message.answer("Введите текст нового вопроса, который вы хотите добавить в общую базу.")


@router.message(QOTD.waiting_for_new_question, F.text)
async def process_new_question(message: types.Message, state: FSMContext):
    success = await db.add_custom_question(message.text)
    if success:
        await message.answer("✅ Ваш вопрос успешно добавлен!")
    else:
        await message.answer("Такой вопрос уже существует в базе.")
    await state.clear()


@router.callback_query(F.data == "answer_qotd")
async def handle_answer_button(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    partner = await db.get_partner(user_id)
    couple_id = min(user_id, partner['user_id'])

    today_question_data = await db.get_today_question_for_couple(couple_id)
    if not today_question_data:
        await callback.answer("Не удалось найти вопрос на сегодня.", show_alert=True)
        return

    user1_answered = today_question_data['user1_id'] == user_id and today_question_data['answer_user1']
    user2_answered = today_question_data['user2_id'] == user_id and today_question_data['answer_user2']

    if user1_answered or user2_answered:
        await callback.answer("Вы уже ответили на сегодняшний вопрос.", show_alert=True)
        return

    await state.set_state(QOTD.waiting_for_answer)
    await callback.message.answer("Введите ваш ответ:")
    await callback.answer()


@router.message(QOTD.waiting_for_answer, F.text)
async def process_qotd_answer(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    partner = await db.get_partner(user_id)
    couple_id = min(user_id, partner['user_id'])

    success = await db.save_answer(couple_id, user_id, message.text)
    if success:
        await message.answer("Ваш ответ принят! Ответы будут показаны вечером.")
    else:
        await message.answer("Произошла ошибка при сохранении ответа.")
    await state.clear()


async def format_archive_page(archive_entry: dict, user_id: int):
    """Форматирует текст для одной страницы архива."""
    question_date = datetime.strptime(archive_entry['question_date'], "%Y-%m-%d").strftime("%d.%m.%Y")

    user1 = await db.get_user(archive_entry['user1_id'])
    user2 = await db.get_user(archive_entry['user2_id'])

    my_answer = "<i>(нет ответа)</i>"
    partner_answer = "<i>(нет ответа)</i>"

    if archive_entry['user1_id'] == user_id:
        my_answer = archive_entry['answer_user1'] or my_answer
        partner_answer = archive_entry['answer_user2'] or partner_answer
    else:
        my_answer = archive_entry['answer_user2'] or my_answer
        partner_answer = archive_entry['answer_user1'] or partner_answer

    text = (
        f"<b>Архив за {question_date}</b>\n\n"
        f"<i>Вопрос: {archive_entry['question_text']}</i>\n\n"
        f"<b>Ваш ответ:</b>\n{my_answer}\n\n"
        f"<b>Ответ партнера:</b>\n{partner_answer}"
    )
    return


@router.message(Command("answers"))
async def cmd_answers(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        return await message.answer("Эта команда доступна только для пар.")

    archive = await db.get_qotd_archive(couple_id)
    if not archive:
        return await message.answer("Архив ваших ответов пока пуст.\nЕсли хотите новый добавь вопрос /addquestion.")

    page_text = await format_archive_page(archive[0], message.from_user.id)
    await message.answer(
        page_text,
        reply_markup=get_qotd_archive_kb(0, len(archive))
    )


@router.callback_query(F.data.startswith("qotd_archive_"))
async def process_archive_page(callback: types.CallbackQuery):
    page_index = int(callback.data.split("_")[-1])

    couple_id = await get_couple_id(callback.from_user.id)
    archive = await db.get_qotd_archive(couple_id)

    if page_index >= len(archive) or page_index < 0:
        return await callback.answer("Ошибка навигации.", show_alert=True)

    page_text = await format_archive_page(archive[page_index], callback.from_user.id)

    await callback.message.edit_text(
        page_text,
        reply_markup=get_qotd_archive_kb(page_index, len(archive))
    )