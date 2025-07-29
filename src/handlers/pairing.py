import logging
from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter

from src.db import database as db
from src.keyboards.inline import get_confirm_unlink_kb

router = Router()


@router.message(Command("code"))
async def cmd_code(message: types.Message):
    """
    Обработчик команды /code.
    Выдает пользователю его уникальный код для приглашения.
    """
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)

    if user_data and user_data['partner_id']:
        await message.answer("Вы уже в паре, эта команда вам не нужна. ❤️")
        return

    invite_code = user_id

    text = (
        "<b>Вот ваш код для приглашения.</b>\n\n"
        "Отправьте его вашей второй половинке. "
        "Партнер должен просто скопировать этот код и отправить его мне в чат."
    )

    await message.answer(text)
    await message.answer(f"<code>{invite_code}</code>")


@router.message(F.text.isdigit(), StateFilter(None))
async def handle_invite_code(message: types.Message):
    """
    Обрабатывает сообщение, если оно является кодом приглашения (просто число).
    """
    try:
        inviter_id = int(message.text)
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        # Режим отладки отключен
        if inviter_id == user_id:
            await message.answer("Нельзя создать пару с самим собой! 😉")
            return

        current_user_data = await db.get_user(user_id)
        if current_user_data and current_user_data['partner_id']:
            await message.answer(
                "Вы уже в паре. Чтобы создать новую, сначала разорвите текущую связь командой /unlink.")
            return

        inviter_data = await db.get_user(inviter_id)
        if not inviter_data:
            logging.info(f"Пользователь {user_id} ввел несуществующий код {inviter_id}")
            return
        if inviter_data['partner_id']:
            await message.answer("Этот пользователь уже состоит в паре.")
            return

        await db.link_partners(inviter_id, user_id)

        await message.answer(f"Поздравляем! Вы теперь в паре с пользователем {inviter_data['username']}! ❤️")
        try:
            await message.bot.send_message(
                chat_id=inviter_id,
                text=f"Отличные новости! Пользователь {username} принял ваше приглашение. Вы теперь в паре! ❤️"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить партнера {inviter_id}: {e}")

    except (ValueError, TypeError):
        pass


@router.message(Command("unlink"))
async def cmd_unlink(message: types.Message):
    """
    Шаг 1: Запрашивает подтверждение на разрыв связи.
    """
    user_data = await db.get_user(message.from_user.id)

    if not user_data or not user_data['partner_id']:
        await message.answer("Вы и так не в паре.")
        return

    await message.answer(
        "Вы уверены, что хотите разорвать связь в боте? Это действие нельзя будет отменить.",
        reply_markup=get_confirm_unlink_kb()
    )


@router.callback_query(F.data == "confirm_unlink")
async def process_confirm_unlink(callback: types.CallbackQuery):
    """
    Шаг 2 (Вариант А): Пользователь подтвердил разрыв.
    """
    user_id = callback.from_user.id
    user_data = await db.get_user(user_id)
    if not user_data or not user_data['partner_id']:
        await callback.message.edit_text("Вы уже не в паре.")
        return

    partner_id = user_data['partner_id']

    await db.unlink_partners(user_id)
    await callback.message.edit_text("Связь с партнером разорвана.")

    try:
        if partner_id != user_id:
            await callback.bot.send_message(
                chat_id=partner_id,
                text=f"Пользователь {callback.from_user.first_name} разорвал(а) с вами пару в боте."
            )
    except Exception as e:
        logging.error(f"Не удалось уведомить партнера {partner_id} о разрыве: {e}")


@router.callback_query(F.data == "cancel_unlink")
async def process_cancel_unlink(callback: types.CallbackQuery):
    """
    Шаг 2 (Вариант Б): Пользователь отменил действие.
    """
    await callback.message.edit_text("Действие отменено. Вы остались в паре. ❤️")
