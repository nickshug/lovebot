from datetime import datetime
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# --- Клавиатуры для комплиментов ---
def get_send_time_kb() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с выбором времени отправки комплимента.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Отправить сейчас", callback_data="send_now"),
        InlineKeyboardButton(text="Отправить позже", callback_data="send_later")
    )
    return builder.as_markup()


def get_date_selection_kb() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с выбором быстрой даты.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Сегодня", callback_data="date_today"),
        InlineKeyboardButton(text="Завтра", callback_data="date_tomorrow")
    )
    return builder.as_markup()


def get_skip_attachment_kb() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой "Пропустить" для шага с вложением.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Отправить без вложения", callback_data="skip_attachment")
    )
    return builder.as_markup()


# --- Клавиатуры для календаря ---
def get_events_period_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора периода просмотра событий."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗓️ На сегодня", callback_data="events_today"),
        InlineKeyboardButton(text="🗓️ На неделю", callback_data="events_week")
    )
    builder.row(
        InlineKeyboardButton(text="🗓️ На месяц", callback_data="events_month"),
        InlineKeyboardButton(text="🗓️ Все предстоящие", callback_data="events_all")
    )
    return builder.as_markup()


def get_skip_details_kb() -> InlineKeyboardMarkup:
    """Кнопка для пропуска ввода деталей события."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="skip_details"))
    return builder.as_markup()


def get_delete_event_kb(events: list, page: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру для удаления событий с пагинацией."""
    builder = InlineKeyboardBuilder()
    EVENTS_PER_PAGE = 5
    start = page * EVENTS_PER_PAGE
    end = start + EVENTS_PER_PAGE

    for event in events[start:end]:
        event_datetime = datetime.fromisoformat(event['event_date'])
        event_str = event_datetime.strftime('%d.%m %H:%M')
        builder.row(InlineKeyboardButton(
            text=f"❌ {event_str} - {event['title'][:20]}",
            callback_data=f"del_event_{event['event_id']}"
        ))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"event_page_{page - 1}"))
    if end < len(events):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"event_page_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


# --- Клавиатура для настроек ---
def get_settings_kb(settings: dict) -> InlineKeyboardMarkup:
    """Клавиатура для меню настроек."""
    builder = InlineKeyboardBuilder()

    # Блок напоминаний о событиях
    reminders_status = f"Включены (в {settings['reminder_time']})" if settings['reminders_enabled'] else "Выключены"
    builder.row(InlineKeyboardButton(text=f"Напоминания о событиях: {reminders_status}", callback_data="noop"))
    if settings['reminders_enabled']:
        builder.row(
            InlineKeyboardButton(text="✏️ Изменить время", callback_data="settings_changetime"),
            InlineKeyboardButton(text="🔕 Выключить", callback_data="settings_disable")
        )
    else:
        builder.row(InlineKeyboardButton(text="🔔 Включить", callback_data="settings_enable"))

    # Блок "Вопрос дня"
    qotd_status = f"Включен ({settings['qotd_send_time']} / {settings['qotd_summary_time']})" if settings[
        'qotd_enabled'] else "Выключен"
    builder.row(InlineKeyboardButton(text=f"Вопрос дня: {qotd_status}", callback_data="noop"))
    if settings['qotd_enabled']:
        builder.row(
            InlineKeyboardButton(text="✏️ Настроить время", callback_data="settings_qotd_changetime"),
            InlineKeyboardButton(text="🔕 Выключить", callback_data="settings_qotd_disable")
        )
    else:
        builder.row(InlineKeyboardButton(text="🔔 Включить", callback_data="settings_qotd_enable"))

    return builder.as_markup()

def get_answer_qotd_kb() -> InlineKeyboardMarkup:
    """Кнопка для ответа на Вопрос Дня."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Ответить", callback_data="answer_qotd"))
    return builder.as_markup()


def get_qotd_archive_kb(current_index: int, total_answers: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для навигации по архиву ответов."""
    builder = InlineKeyboardBuilder()

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Предыдущий", callback_data=f"qotd_archive_{current_index - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"{current_index + 1}/{total_answers}", callback_data="noop"))

    if current_index < total_answers - 1:
        nav_buttons.append(InlineKeyboardButton(text="Следующий ➡️", callback_data=f"qotd_archive_{current_index + 1}"))

    builder.row(*nav_buttons)
    return builder.as_markup()

# --- Клавиатуры для вишлиста ---
def get_wishlist_choice_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора, чей вишлист посмотреть."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎁 Мой вишлист", callback_data="wishlist_my"),
        InlineKeyboardButton(text="💖 Вишлист партнера", callback_data="wishlist_partner")
    )
    return builder.as_markup()


def get_skip_photo_kb() -> InlineKeyboardMarkup:
    """Кнопка для пропуска добавления фото в вишлист."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="skip_photo"))
    return builder.as_markup()


def get_skip_link_kb() -> InlineKeyboardMarkup:
    """Кнопка для пропуска добавления ссылки в вишлист."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Пропустить", callback_data="skip_link"))
    return builder.as_markup()


def get_memory_view_kb(current_index: int, total_memories: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для навигации по воспоминаниям."""
    builder = InlineKeyboardBuilder()

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"memory_view_{current_index - 1}"))

    nav_buttons.append(InlineKeyboardButton(text=f"{current_index + 1}/{total_memories}", callback_data="noop"))

    if current_index < total_memories - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"memory_view_{current_index + 1}"))

    builder.row(*nav_buttons)
    return builder.as_markup()


def get_movie_genre_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора жанра фильма."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎭 Комедия", callback_data="movie_genre_comedy"),
        InlineKeyboardButton(text="💖 Романтика", callback_data="movie_genre_romance")
    )
    builder.row(
        InlineKeyboardButton(text="🚀 Фантастика", callback_data="movie_genre_scifi"),
        InlineKeyboardButton(text="❓ Триллер", callback_data="movie_genre_thriller")
    )
    return builder.as_markup()


def get_movie_suggestion_kb() -> InlineKeyboardMarkup:
    """Клавиатура с действиями для предложенного фильма."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎲 Другой вариант", callback_data="movie_another"),
        InlineKeyboardButton(text="➕ В список", callback_data="movie_add_watchlist")
    )
    builder.row(InlineKeyboardButton(text="✅ Отлично, смотрим!", callback_data="movie_lets_watch"))
    return builder.as_markup()


def get_delete_movie_kb(movies: list, page: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру для удаления фильмов с пагинацией."""
    builder = InlineKeyboardBuilder()
    MOVIES_PER_PAGE = 5
    start = page * MOVIES_PER_PAGE
    end = start + MOVIES_PER_PAGE

    for movie in movies[start:end]:
        builder.row(InlineKeyboardButton(
            text=f"❌ {movie['title'][:30]}",
            callback_data=f"del_movie_{movie['id']}"
        ))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"movie_page_{page - 1}"))
    if end < len(movies):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"movie_page_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


def get_date_ideas_kb(ideas: list) -> InlineKeyboardMarkup:
    """Создает клавиатуру-чеклист для идей свиданий."""
    builder = InlineKeyboardBuilder()
    for idea in ideas:
        status_icon = "✅" if idea['is_completed'] else "⬜️"
        builder.row(InlineKeyboardButton(
            text=f"{status_icon} {idea['idea_text']}",
            callback_data=f"toggle_idea_{idea['id']}"
        ))
    return builder.as_markup()


def get_delete_date_idea_kb(ideas: list, page: int = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру для удаления идей с пагинацией."""
    builder = InlineKeyboardBuilder()
    IDEAS_PER_PAGE = 5
    start = page * IDEAS_PER_PAGE
    end = start + IDEAS_PER_PAGE

    for idea in ideas[start:end]:
        builder.row(InlineKeyboardButton(
            text=f"❌ {idea['idea_text'][:30]}",
            callback_data=f"del_idea_{idea['id']}"
        ))

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"idea_page_{page - 1}"))
    if end < len(ideas):
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"idea_page_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()

def get_confirm_unlink_kb() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения разрыва связи."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💔 Да, разорвать", callback_data="confirm_unlink"),
        InlineKeyboardButton(text="❤️ Нет, отмена", callback_data="cancel_unlink")
    )
    return builder.as_markup()