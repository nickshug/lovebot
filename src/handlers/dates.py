from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.db import database as db
from src.states.user_states import DateIdea
from src.keyboards.inline import get_date_ideas_kb, get_delete_date_idea_kb

router = Router()


async def get_couple_id(user_id: int):
    partner = await db.get_partner(user_id)
    return min(user_id, partner['user_id']) if partner else None


# --- Добавление идеи ---
@router.message(Command("add_date_idea"))
async def cmd_add_date_idea(message: types.Message, state: FSMContext):
    await state.clear()
    if not await get_couple_id(message.from_user.id):
        return await message.answer("Эта команда доступна только для пар.")

    await state.set_state(DateIdea.waiting_for_idea_text)
    await message.answer("Какую идею для свидания вы хотите добавить в ваш общий список?")


@router.message(DateIdea.waiting_for_idea_text, F.text)
async def process_new_date_idea(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    success = await db.add_date_idea(couple_id, message.text)

    if success:
        await message.answer(f"✅ Идея '{message.text}' добавлена в ваш список!")
    else:
        await message.answer("Такая идея уже есть в вашем списке.")


# --- Просмотр и управление ---
@router.message(Command("date_ideas"))
async def cmd_date_ideas(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        return await message.answer("Эта команда доступна только для пар.")

    ideas = await db.get_date_ideas(couple_id)
    if not ideas:
        return await message.answer(
            "Ваш список идей для свиданий пока пуст. Добавьте что-нибудь командой /add_date_idea.")

    await message.answer(
        "<b>💖 Ваш список идей для свиданий:</b>\n\nНажимайте на идеи, чтобы отметить их как выполненные.",
        reply_markup=get_date_ideas_kb(ideas)
    )


@router.callback_query(F.data.startswith("toggle_idea_"))
async def process_toggle_idea(callback: types.CallbackQuery):
    idea_id = int(callback.data.split("_")[-1])
    couple_id = await get_couple_id(callback.from_user.id)

    await db.toggle_date_idea_status(idea_id, couple_id)
    await callback.answer("Статус изменен!")

    # Обновляем клавиатуру
    ideas = await db.get_date_ideas(couple_id)
    await callback.message.edit_reply_markup(reply_markup=get_date_ideas_kb(ideas))


# --- Удаление идеи ---
@router.message(Command("del_date_idea"))
async def cmd_del_date_idea(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        return await message.answer("Эта команда доступна только для пар.")

    ideas = await db.get_date_ideas(couple_id)
    if not ideas:
        return await message.answer("Ваш список идей пуст. Нечего удалять.")

    await message.answer(
        "Какую идею вы хотите удалить из списка?",
        reply_markup=get_delete_date_idea_kb(ideas)
    )


@router.callback_query(F.data.startswith("del_idea_"))
async def process_del_idea(callback: types.CallbackQuery):
    idea_id = int(callback.data.split("_")[-1])
    couple_id = await get_couple_id(callback.from_user.id)

    await db.delete_date_idea(idea_id, couple_id)
    await callback.answer("Идея удалена.", show_alert=True)

    ideas = await db.get_date_ideas(couple_id)
    if not ideas:
        await callback.message.edit_text("Ваш список идей теперь пуст.")
    else:
        await callback.message.edit_text(
            "Какую идею вы хотите удалить из списка?",
            reply_markup=get_delete_date_idea_kb(ideas)
        )


@router.callback_query(F.data.startswith("idea_page_"))
async def process_idea_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    couple_id = await get_couple_id(callback.from_user.id)
    ideas = await db.get_date_ideas(couple_id)
    await callback.message.edit_reply_markup(reply_markup=get_delete_date_idea_kb(ideas, page))
