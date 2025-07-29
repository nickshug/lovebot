import logging
from datetime import datetime, timedelta
import pytz
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.db import database as db
from src.states.user_states import Actions
from src.keyboards.inline import get_send_time_kb, get_skip_attachment_kb, get_date_selection_kb

router = Router()


@router.message(Command("compliment"))
async def cmd_compliment(message: types.Message, state: FSMContext):
    """
    Шаг 1: Начинает диалог и просит ввести текст.
    """
    user_data = await db.get_user(message.from_user.id)
    if not user_data or not user_data['partner_id']:
        await message.answer("Эта команда доступна только для пар.")
        return
    await state.set_state(Actions.waiting_for_compliment_text)
    await message.answer("Какой комплимент вы хотите отправить партнеру? Напишите текст.")


@router.message(Actions.waiting_for_compliment_text)
async def process_compliment_text(message: types.Message, state: FSMContext):
    """
    Шаг 2: Сохраняет текст и просит прикрепить вложение.
    """
    if not message.text:
        await message.answer("Пожалуйста, отправьте комплимент в виде текстового сообщения.")
        return
    await state.update_data(compliment_text=message.text)
    await message.answer(
        "Отлично! Теперь можете прикрепить фото, видео или аудио. Или нажмите кнопку, чтобы отправить без вложения.",
        reply_markup=get_skip_attachment_kb())
    await state.set_state(Actions.waiting_for_attachment)


@router.message(Actions.waiting_for_attachment, F.photo | F.video | F.voice | F.video_note)
async def process_attachment(message: types.Message, state: FSMContext):
    """
    Шаг 3 (Вариант А): Пользователь отправил вложение. Сохраняем его и спрашиваем время отправки.
    """
    attachment_info = {}
    if message.photo:
        attachment_info['type'] = 'photo'
        attachment_info['file_id'] = message.photo[-1].file_id
    elif message.video:
        attachment_info['type'] = 'video'
        attachment_info['file_id'] = message.video.file_id
    elif message.voice:
        attachment_info['type'] = 'voice'
        attachment_info['file_id'] = message.voice.file_id
    elif message.video_note:
        attachment_info['type'] = 'video_note'
        attachment_info['file_id'] = message.video_note.file_id

    attachment_info['caption'] = message.caption
    await state.update_data(attachment_info=attachment_info)

    await message.answer("Вложение принято! Когда отправить комплимент?", reply_markup=get_send_time_kb())
    await state.set_state(Actions.waiting_for_send_time_choice)


@router.callback_query(Actions.waiting_for_attachment, F.data == "skip_attachment")
async def process_skip_attachment(callback: types.CallbackQuery, state: FSMContext):
    """
    Шаг 3 (Вариант Б): Пользователь пропустил вложение. Спрашиваем время отправки.
    """
    await callback.message.edit_text("Хорошо. Когда отправить комплимент?", reply_markup=get_send_time_kb())
    await state.set_state(Actions.waiting_for_send_time_choice)


@router.callback_query(Actions.waiting_for_send_time_choice, F.data == "send_now")
async def process_send_now(callback: types.CallbackQuery, state: FSMContext):
    """
    Шаг 4 (Вариант А): Пользователь выбрал "Отправить сейчас". Завершаем диалог.
    """
    await callback.message.delete()
    await finalize_compliment(callback.from_user.id, callback.bot, state)


@router.callback_query(Actions.waiting_for_send_time_choice, F.data == "send_later")
async def process_send_later(callback: types.CallbackQuery, state: FSMContext):
    """
    Шаг 4 (Вариант Б): Пользователь выбрал "Отправить позже". Просим выбрать/ввести дату.
    """
    await callback.message.edit_text(
        "Хорошо. Выберите дату для отправки или введите ее вручную.\n\n"
        "Формат для ручного ввода: <b>ДД.ММ.ГГГГ</b> (например, 31.12.2024).",
        reply_markup=get_date_selection_kb()
    )
    await state.set_state(Actions.waiting_for_send_date)


@router.callback_query(Actions.waiting_for_send_date, F.data.startswith("date_"))
async def process_date_button(callback: types.CallbackQuery, state: FSMContext):
    """
    Шаг 5 (Вариант А): Обрабатывает нажатие кнопок "Сегодня" / "Завтра".
    """
    await callback.answer()
    date_choice = callback.data.split("_")[1]
    send_date = None
    if date_choice == "today":
        send_date = datetime.now().date()
    elif date_choice == "tomorrow":
        send_date = (datetime.now() + timedelta(days=1)).date()
    await state.update_data(send_date=send_date)
    await callback.message.edit_text(
        "Отлично! Теперь введите время в формате <b>ЧЧ:ММ</b> (например, 09:30 или 18:00).")
    await state.set_state(Actions.waiting_for_send_time)


@router.message(Actions.waiting_for_send_date, F.text)
async def process_date_text_input(message: types.Message, state: FSMContext):
    """
    Шаг 5 (Вариант Б): Обрабатывает дату, введенную вручную.
    """
    try:
        send_date = datetime.strptime(message.text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ или выберите на кнопках.")
        return
    if send_date < datetime.now().date():
        await message.answer("Эта дата уже в прошлом! Пожалуйста, выберите сегодняшнюю или будущую дату.")
        return
    await state.update_data(send_date=send_date)
    await message.answer("Отлично! Теперь введите время в формате <b>ЧЧ:ММ</b> (например, 09:30 или 18:00).")
    await state.set_state(Actions.waiting_for_send_time)


@router.message(Actions.waiting_for_send_time, F.text)
async def process_send_time(message: types.Message, state: FSMContext):
    """
    Шаг 6: Обрабатывает время, сохраняет его и завершает диалог.
    """
    try:
        user_time = datetime.strptime(message.text, "%H:%M").time()
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введите время в формате ЧЧ:ММ.")
        return
    user_data = await state.get_data()
    naive_send_datetime = datetime.combine(user_data['send_date'], user_time)
    moscow_tz = pytz.timezone("Europe/Moscow")
    aware_send_datetime = moscow_tz.localize(naive_send_datetime)
    if aware_send_datetime < datetime.now(moscow_tz):
        await message.answer("Это время уже прошло! Пожалуйста, выберите будущее время.")
        return
    await state.update_data(send_datetime=aware_send_datetime)
    await finalize_compliment(message.from_user.id, message.bot, state)


async def finalize_compliment(user_id: int, bot: Bot, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    sender = await db.get_user(user_id)
    partner = await db.get_partner(user_id)
    if not partner or not sender:
        logging.error(f"Не удалось найти пару для user_id: {user_id} при финализации комплимента.")
        try:
            await bot.send_message(user_id,
                                   "Произошла ошибка, не удалось найти вашего партнера. Попробуйте, пожалуйста, снова.")
        except Exception as e:
            logging.error(f"Не удалось даже отправить сообщение об ошибке пользователю {user_id}: {e}")
        return

    text = data.get('compliment_text')
    from_user_name = sender['username'] or 'Ваш партнер'
    full_message = f"💌 Вам пришел комплимент от {from_user_name}:\n\n✨ «{text}» ✨"

    attachment_info = data.get('attachment_info')
    caption = attachment_info.get('caption') if attachment_info else None
    file_id = attachment_info.get('file_id') if attachment_info else None
    attachment_type = attachment_info.get('type') if attachment_info else None

    if 'send_datetime' not in data:
        try:
            await bot.send_message(chat_id=partner['user_id'], text=full_message)
            if file_id:
                if attachment_type == 'photo':
                    await bot.send_photo(chat_id=partner['user_id'], photo=file_id, caption=caption)
                elif attachment_type == 'video':
                    await bot.send_video(chat_id=partner['user_id'], video=file_id, caption=caption)
                elif attachment_type == 'voice':
                    await bot.send_voice(chat_id=partner['user_id'], voice=file_id, caption=caption)
                elif attachment_type == 'video_note':
                    await bot.send_video_note(chat_id=partner['user_id'], video_note=file_id)
            await bot.send_message(user_id, "Ваш комплимент отправлен! 💖")
        except Exception as e:
            logging.error(f"Ошибка при отправке комплимента: {e}")
            await bot.send_message(user_id, "Не удалось отправить комплимент.")
    else:
        send_datetime = data['send_datetime']
        send_time_str = send_datetime.strftime('%d.%m.%Y в %H:%M')
        send_at_iso = send_datetime.isoformat()
        await db.add_scheduled_compliment(
            sender_id=user_id,
            receiver_id=partner['user_id'],
            text=text,
            caption=caption,
            attachment_type=attachment_type,
            attachment_file_id=file_id,
            send_at=send_at_iso
        )
        await bot.send_message(user_id, f"Отлично! Ваш комплимент будет отправлен {send_time_str}. 💌")
