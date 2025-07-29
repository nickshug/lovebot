import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.db import database as db
from src.states.user_states import Wishlist
from src.keyboards.inline import get_wishlist_choice_kb, get_skip_photo_kb, get_skip_link_kb

router = Router()
WISHES_PER_PAGE = 5


# --- Добавление желания ---

@router.message(Command("addwish"))
async def cmd_addwish(message: types.Message, state: FSMContext):
    await state.clear()
    user_data = await db.get_user(message.from_user.id)
    if not user_data or not user_data['partner_id']:
        await message.answer("Эта команда доступна только для пар.")
        return

    await state.set_state(Wishlist.waiting_for_title)
    await message.answer("Что вы хотите добавить в свой вишлист? (например, 'Билет на концерт')")


@router.message(Wishlist.waiting_for_title, F.text)
async def process_wish_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(Wishlist.waiting_for_link)
    await message.answer("Хотите добавить ссылку на товар? Отправьте ее или нажмите 'Пропустить'.",
                         reply_markup=get_skip_link_kb())


@router.message(Wishlist.waiting_for_link, F.text)
async def process_wish_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text)
    await state.set_state(Wishlist.waiting_for_photo)
    await message.answer("Хотите добавить фото? Отправьте его сейчас или нажмите 'Пропустить'.",
                         reply_markup=get_skip_photo_kb())


@router.callback_query(Wishlist.waiting_for_link, F.data == "skip_link")
async def process_skip_link(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Wishlist.waiting_for_photo)
    await callback.message.edit_text("Хотите добавить фото? Отправьте его сейчас или нажмите 'Пропустить'.",
                                     reply_markup=get_skip_photo_kb())


async def finalize_wish_creation(user_id: int, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    await db.add_wish(
        user_id=user_id,
        title=data['title'],
        link=data.get('link'),
        photo_file_id=data.get('photo_file_id')
    )


@router.message(Wishlist.waiting_for_photo, F.photo)
async def process_wish_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await finalize_wish_creation(message.from_user.id, state)
    await message.answer("✅ Желание с фото добавлено в ваш вишлист!")


@router.callback_query(Wishlist.waiting_for_photo, F.data == "skip_photo")
async def process_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await finalize_wish_creation(callback.from_user.id, state)
    await callback.message.edit_text("✅ Желание добавлено в ваш вишлист!")


# --- Просмотр вишлистов ---

@router.message(Command("wishlist"))
async def cmd_wishlist(message: types.Message, state: FSMContext):
    await state.clear()
    user_data = await db.get_user(message.from_user.id)
    if not user_data or not user_data['partner_id']:
        await message.answer("Эта команда доступна только для пар.")
        return
    await message.answer("Чей вишлист вы хотите посмотреть?", reply_markup=get_wishlist_choice_kb())


async def format_wishlist_text_and_kb(wishes: list, owner_name: str, is_partner: bool, viewer_id: int):
    if not wishes:
        return f"Вишлист пользователя {owner_name} пока пуст.", None

    text = f"<b>Вишлист {owner_name}:</b>\n\n"
    builder = InlineKeyboardBuilder()

    for i, wish in enumerate(wishes, 1):
        text += f"<b>{i}. {wish['title']}</b>\n"
        if wish['link']:
            text += f"   <a href='{wish['link']}'>🔗 Ссылка на товар</a>\n"
        if wish['photo_file_id']:
            text += f"   <i>(Прикреплено фото)</i>\n"

        if is_partner:
            if not wish['booked_by_id']:
                builder.row(InlineKeyboardButton(text=f"🤫 Забронировать '{wish['title'][:20]}'",
                                                 callback_data=f"book_wish_{wish['wish_id']}"))
            elif wish['booked_by_id'] == viewer_id:
                builder.row(InlineKeyboardButton(text=f"🎁 Уже в планах! (снять бронь)",
                                                 callback_data=f"unbook_wish_{wish['wish_id']}"))
            else:
                builder.row(InlineKeyboardButton(text=f" кем-то забронировано ", callback_data="noop"))
        text += "\n"

    return text, builder.as_markup() if is_partner else None


async def show_partner_wishlist(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    partner = await db.get_partner(user_id)
    wishes = await db.get_wishes(partner['user_id'])
    text, keyboard = await format_wishlist_text_and_kb(wishes, partner['username'], is_partner=True, viewer_id=user_id)
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("wishlist_"))
async def process_wishlist_choice(callback: types.CallbackQuery):
    choice = callback.data.split("_")[1]
    user_id = callback.from_user.id

    if choice == "my":
        wishes = await db.get_wishes(user_id)
        text, _ = await format_wishlist_text_and_kb(wishes, "вас", is_partner=False, viewer_id=user_id)
        await callback.message.edit_text(text, disable_web_page_preview=True)

    elif choice == "partner":
        await show_partner_wishlist(callback)


@router.callback_query(F.data.startswith("book_wish_"))
async def process_book_wish(callback: types.CallbackQuery):
    wish_id = int(callback.data.split("_")[-1])
    await db.book_wish(wish_id, callback.from_user.id)
    await callback.answer("Вы тайно забронировали это желание! 🤫")
    await show_partner_wishlist(callback)


@router.callback_query(F.data.startswith("unbook_wish_"))
async def process_unbook_wish(callback: types.CallbackQuery):
    wish_id = int(callback.data.split("_")[-1])
    await db.unbook_wish(wish_id)
    await callback.answer("Бронь снята.")
    await show_partner_wishlist(callback)


# --- Удаление желания ---

def get_delete_wish_kb(wishes: list, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * WISHES_PER_PAGE
    end = start + WISHES_PER_PAGE

    for wish in wishes[start:end]:
        builder.row(InlineKeyboardButton(text=f"❌ {wish['title'][:30]}", callback_data=f"del_wish_{wish['wish_id']}"))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"wish_page_{page - 1}"))
    if end < len(wishes):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"wish_page_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


@router.message(Command("delwish"))
async def cmd_delwish(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    wishes = await db.get_wishes(user_id)

    if not wishes:
        await message.answer("Ваш вишлист пока пуст. Нечего удалять.")
        return

    await message.answer(
        "Какое желание вы хотите удалить?",
        reply_markup=get_delete_wish_kb(wishes)
    )


@router.callback_query(F.data.startswith("del_wish_"))
async def process_del_wish(callback: types.CallbackQuery):
    wish_id = int(callback.data.split("_")[-1])
    wish = await db.get_wish_by_id(wish_id)
    await db.delete_wish_by_id(wish_id, callback.from_user.id)
    await callback.message.edit_text(f"✅ Желание '{wish['title']}' удалено.")


@router.callback_query(F.data.startswith("wish_page_"))
async def process_wish_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    wishes = await db.get_wishes(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=get_delete_wish_kb(wishes, page))
