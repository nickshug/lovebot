import logging
from datetime import datetime
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto, InputMediaVideo

from src.db import database as db
from src.states.user_states import Memory
from src.keyboards.inline import get_memory_view_kb, get_today_date_kb

router = Router()


async def get_couple_id(user_id: int):
    partner = await db.get_partner(user_id)
    return min(user_id, partner['user_id']) if partner else None


@router.message(Command("addmemory"))
async def cmd_addmemory(message: types.Message, state: FSMContext):
    await state.clear()
    if not await get_couple_id(message.from_user.id):
        return await message.answer("Эта команда доступна только для пар.")

    await state.set_state(Memory.waiting_for_media)
    await message.answer("Отправьте фото или видео, которое хотите сохранить в вашей 'Капсуле Памяти'.")


@router.message(Memory.waiting_for_media, F.photo | F.video)
async def process_memory_media(message: types.Message, state: FSMContext):
    media_type = 'photo' if message.photo else 'video'
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id

    await state.update_data(media_type=media_type, media_file_id=file_id)
    await state.set_state(Memory.waiting_for_description)
    await message.answer("Отлично! Теперь добавьте описание к этому моменту.")


@router.message(Memory.waiting_for_description, F.text)
async def process_memory_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(Memory.waiting_for_date)
    await message.answer(
        "На какую дату записать это воспоминание? (ДД.ММ.ГГГГ)\n\n"
        "Нажмите кнопку или введите дату вручную. Если ничего не отправлять, будет использована текущая дата.",
        reply_markup=get_today_date_kb()
    )


async def finalize_memory_creation(user_id: int, bot: Bot, state: FSMContext, memory_date: datetime.date):
    """Общая функция для завершения создания воспоминания."""
    data = await state.get_data()
    await state.clear()

    couple_id = await get_couple_id(user_id)
    await db.add_memory(
        couple_id=couple_id,
        media_type=data['media_type'],
        media_file_id=data['media_file_id'],
        description=data['description'],
        added_at=memory_date
    )
    await bot.send_message(user_id, "✅ Воспоминание добавлено в вашу капсулу!")


@router.message(Memory.waiting_for_date, F.text)
async def process_memory_date_text(message: types.Message, state: FSMContext):
    try:
        memory_date = datetime.strptime(message.text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "Неверный формат. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ или нажмите кнопку 'Сегодня'.")
        return
    await finalize_memory_creation(message.from_user.id, message.bot, state, memory_date)


@router.callback_query(Memory.waiting_for_date, F.data == "date_today")
async def process_memory_date_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()  # Удаляем сообщение с кнопкой
    await finalize_memory_creation(callback.from_user.id, callback.bot, state, datetime.now().date())


@router.message(Command("memory"))
async def cmd_memory(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        return await message.answer("Эта команда доступна только для пар.")

    memory = await db.get_random_memory(couple_id)
    if not memory:
        return await message.answer("Ваша 'Капсула Памяти' пока пуста. Добавьте что-нибудь командой /addmemory.")

    date_str = datetime.strptime(memory['added_at'], "%Y-%m-%d").strftime("%d.%m.%Y")
    caption = f"<b>Воспоминание от {date_str}:</b>\n\n{memory['description']}"

    if memory['media_type'] == 'photo':
        await message.answer_photo(photo=memory['media_file_id'], caption=caption)
    elif memory['media_type'] == 'video':
        await message.answer_video(video=memory['media_file_id'], caption=caption)


@router.message(Command("allmemories"))
async def cmd_allmemories(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        return await message.answer("Эта команда доступна только для пар.")

    memories = await db.get_all_memories(couple_id)
    if not memories:
        return await message.answer("Ваша 'Капсула Памяти' пока пуста.")

    await state.update_data(memories_archive=memories)

    # Показываем первое воспоминание
    memory = memories[0]
    date_str = datetime.strptime(memory['added_at'], "%Y-%m-%d").strftime("%d.%m.%Y")
    caption = f"<b>Воспоминание от {date_str}:</b>\n\n{memory['description']}"

    if memory['media_type'] == 'photo':
        await message.answer_photo(
            photo=memory['media_file_id'],
            caption=caption,
            reply_markup=get_memory_view_kb(0, len(memories))
        )
    elif memory['media_type'] == 'video':
        await message.answer_video(
            video=memory['media_file_id'],
            caption=caption,
            reply_markup=get_memory_view_kb(0, len(memories))
        )


@router.callback_query(F.data.startswith("memory_view_"))
async def process_memory_page(callback: types.CallbackQuery, state: FSMContext):
    page_index = int(callback.data.split("_")[-1])

    data = await state.get_data()
    memories = data.get('memories_archive')

    # Если FSM сбросился, получаем данные заново
    if not memories:
        couple_id = await get_couple_id(callback.from_user.id)
        memories = await db.get_all_memories(couple_id)
        await state.update_data(memories_archive=memories)

    if page_index >= len(memories) or page_index < 0:
        return await callback.answer("Ошибка навигации.")

    memory = memories[page_index]
    date_str = datetime.strptime(memory['added_at'], "%Y-%m-%d").strftime("%d.%m.%Y")
    caption = f"<b>Воспоминание от {date_str}:</b>\n\n{memory['description']}"

    # Создаем объект InputMedia для редактирования
    if memory['media_type'] == 'photo':
        media = InputMediaPhoto(media=memory['media_file_id'], caption=caption)
    else:  # video
        media = InputMediaVideo(media=memory['media_file_id'], caption=caption)

    await callback.message.edit_media(
        media=media,
        reply_markup=get_memory_view_kb(page_index, len(memories))
    )
