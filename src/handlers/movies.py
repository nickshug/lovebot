import logging
import random
import aiohttp
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.config import TMDB_API_KEY
from src.db import database as db
from src.states.user_states import Movie
from src.keyboards.inline import get_movie_genre_kb, get_movie_suggestion_kb, get_delete_movie_kb

router = Router()

# --- Настройки для API TMDb ---
TMDB_GENRE_MAP = {
    "comedy": 35, "romance": 10749, "scifi": 878, "thriller": 53
}
TMDB_IMG_BASE_URL = "https://image.tmdb.org/t/p/w500"


async def get_couple_id(user_id: int):
    partner = await db.get_partner(user_id)
    return min(user_id, partner['user_id']) if partner else None


async def get_random_movie_from_api(genre_id: int):
    """Получает случайный популярный фильм по жанру из TMDb API."""
    # Запрашиваем случайную страницу из первых 20 (чтобы не получать слишком нишевые фильмы)
    random_page = random.randint(1, 20)
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_genres={genre_id}&language=ru-RU&sort_by=popularity.desc&page={random_page}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data['results']:
                    return random.choice(data['results'])
    return None


# --- Кинорулетка ---

@router.message(Command("movie"))
async def cmd_movie(message: types.Message, state: FSMContext):
    await state.clear()
    if not await get_couple_id(message.from_user.id):
        return await message.answer("Эта команда доступна только для пар.")

    await state.set_state(Movie.choosing_genre)
    await message.answer("Какой жанр предпочитаете сегодня вечером?", reply_markup=get_movie_genre_kb())


async def show_random_movie(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    genre = data.get('current_genre')
    if not genre: return

    genre_id = TMDB_GENRE_MAP.get(genre)
    movie = await get_random_movie_from_api(genre_id)

    if not movie or not movie.get('poster_path'):
        await callback.answer("Не удалось найти фильм, попробуйте еще раз.", show_alert=True)
        return

    await state.update_data(current_movie=movie)

    poster_url = f"{TMDB_IMG_BASE_URL}{movie['poster_path']}"
    caption = f"<b>{movie['title']}</b>\n\n{movie['overview']}"

    try:
        # Отправляем фото с подписью
        await callback.message.answer_photo(
            photo=poster_url,
            caption=caption,
            reply_markup=get_movie_suggestion_kb()
        )
        await callback.message.delete()  # Удаляем старое сообщение с кнопками жанров
    except Exception as e:
        logging.error(f"Ошибка при отправке постера: {e}")
        await callback.message.answer("Не удалось загрузить постер, но вот информация о фильме:")
        await callback.message.answer(caption, reply_markup=get_movie_suggestion_kb())


@router.callback_query(Movie.choosing_genre, F.data.startswith("movie_genre_"))
async def process_genre_choice(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Ищу фильм для вас...")
    genre = callback.data.split("_")[-1]
    await state.update_data(current_genre=genre)
    await show_random_movie(callback, state)


@router.callback_query(Movie.choosing_genre, F.data == "movie_another")
async def process_another_movie(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Ищем другой вариант...")
    await callback.message.delete()
    await show_random_movie(callback, state)


@router.callback_query(Movie.choosing_genre, F.data == "movie_add_watchlist")
async def process_add_to_watchlist(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    movie = data.get('current_movie')
    if not movie: return

    couple_id = await get_couple_id(callback.from_user.id)
    success = await db.add_movie_to_watchlist(couple_id, movie['title'])

    if success:
        await callback.answer(f"'{movie['title']}' добавлен в ваш список просмотра!", show_alert=True)
    else:
        await callback.answer(f"'{movie['title']}' уже есть в вашем списке.", show_alert=True)


@router.callback_query(Movie.choosing_genre, F.data == "movie_lets_watch")
async def process_lets_watch(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    movie = data.get('current_movie')
    if not movie: return

    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        f"Отличный выбор! Сегодня вы смотрите '<b>{movie['title']}</b>'.\n\nПриятного просмотра! 🍿")

    partner = await db.get_partner(callback.from_user.id)
    try:
        await callback.bot.send_message(
            partner['user_id'],
            f"🔔 {callback.from_user.username} выбрал(а) фильм на вечер: '<b>{movie['title']}</b>'.\n\nГотовьте попкорн! 😉"
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить партнера о выборе фильма: {e}")


# --- Список просмотра ---

@router.message(Command("addmovie"))
async def cmd_addmovie(message: types.Message, state: FSMContext):
    await state.clear()
    if not await get_couple_id(message.from_user.id):
        return await message.answer("Эта команда доступна только для пар.")

    await state.set_state(Movie.waiting_for_movie_title)
    await message.answer("Введите название фильма, который хотите добавить в список просмотра.")


@router.message(Movie.waiting_for_movie_title, F.text)
async def process_add_movie_title(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    success = await db.add_movie_to_watchlist(couple_id, message.text)

    if success:
        await message.answer(f"Фильм '{message.text}' добавлен в ваш список просмотра!")
    else:
        await message.answer(f"Фильм '{message.text}' уже есть в вашем списке.")


@router.message(Command("watchlist"))
async def cmd_watchlist(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        return await message.answer("Эта команда доступна только для пар.")

    watchlist = await db.get_movie_watchlist(couple_id)
    if not watchlist:
        return await message.answer(
            "Ваш список просмотра пока пуст. Добавьте что-нибудь с помощью /movie или /addmovie.")

    text = "<b>🎬 Ваш список фильмов для просмотра:</b>\n\n"
    for i, movie in enumerate(watchlist, 1):
        text += f"{i}. {movie['title']}\n"

    await message.answer(text)


@router.message(Command("delmovie"))
async def cmd_delmovie(message: types.Message, state: FSMContext):
    await state.clear()
    couple_id = await get_couple_id(message.from_user.id)
    if not couple_id:
        return await message.answer("Эта команда доступна только для пар.")

    watchlist = await db.get_movie_watchlist(couple_id)
    if not watchlist:
        return await message.answer("Ваш список просмотра пуст. Нечего удалять.")

    await message.answer(
        "Какой фильм вы хотите удалить из списка?",
        reply_markup=get_delete_movie_kb(watchlist)
    )


@router.callback_query(F.data.startswith("del_movie_"))
async def process_del_movie(callback: types.CallbackQuery):
    movie_id = int(callback.data.split("_")[-1])
    couple_id = await get_couple_id(callback.from_user.id)

    await db.delete_movie_from_watchlist(movie_id, couple_id)
    await callback.answer("Фильм удален из списка.", show_alert=True)

    watchlist = await db.get_movie_watchlist(couple_id)
    if not watchlist:
        await callback.message.edit_text("Ваш список просмотра теперь пуст.")
    else:
        await callback.message.edit_text(
            "Какой фильм вы хотите удалить из списка?",
            reply_markup=get_delete_movie_kb(watchlist)
        )


@router.callback_query(F.data.startswith("movie_page_"))
async def process_movie_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    couple_id = await get_couple_id(callback.from_user.id)
    watchlist = await db.get_movie_watchlist(couple_id)
    await callback.message.edit_reply_markup(reply_markup=get_delete_movie_kb(watchlist, page))
