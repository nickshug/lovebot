import aiosqlite
import logging
from datetime import datetime
import pytz
from src.config import BASE_DIR

DB_PATH = BASE_DIR / "lovebot.db"


async def db_start():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                partner_id INTEGER UNIQUE,
                start_date TEXT
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_compliments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                text TEXT,
                caption TEXT,
                attachment_type TEXT,
                attachment_file_id TEXT,
                send_at TIMESTAMP NOT NULL
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                couple_id INTEGER NOT NULL,
                event_date TIMESTAMP NOT NULL,
                title TEXT NOT NULL,
                details TEXT
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS wishlist (
                wish_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                link TEXT,
                photo_file_id TEXT,
                booked_by_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS couple_settings (
                couple_id INTEGER PRIMARY KEY,
                reminders_enabled BOOLEAN DEFAULT FALSE,
                reminder_time TEXT DEFAULT '09:00',
                qotd_enabled BOOLEAN DEFAULT FALSE,
                qotd_send_time TEXT DEFAULT '12:00',
                qotd_summary_time TEXT DEFAULT '20:00'
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                couple_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                answer_user1 TEXT,
                user1_id INTEGER,
                answer_user2 TEXT,
                user2_id INTEGER,
                question_date DATE NOT NULL,
                UNIQUE(couple_id, question_date)
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                couple_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                media_file_id TEXT NOT NULL,
                description TEXT,
                added_at DATE NOT NULL
            )""")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS movie_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                couple_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                UNIQUE(couple_id, title)
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS date_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                couple_id INTEGER NOT NULL,
                idea_text TEXT NOT NULL,
                is_completed BOOLEAN DEFAULT FALSE,
                UNIQUE(couple_id, idea_text)
            )
        """)
        await db.commit()
        logging.info("База данных успешно инициализирована.")

async def add_scheduled_compliment(sender_id, receiver_id, text, send_at, caption=None, attachment_type=None, attachment_file_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO scheduled_compliments 
               (sender_id, receiver_id, text, caption, send_at, attachment_type, attachment_file_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sender_id, receiver_id, text, caption, send_at, attachment_type, attachment_file_id)
        )
        await db.commit()

async def get_due_compliments():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        moscow_tz = pytz.timezone("Europe/Moscow")
        now_aware = datetime.now(moscow_tz)
        now_iso = now_aware.isoformat()
        cursor = await db.execute("SELECT * FROM scheduled_compliments WHERE send_at <= ?", (now_iso,))
        return await cursor.fetchall()

async def delete_compliment(compliment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM scheduled_compliments WHERE id = ?", (compliment_id,))
        await db.commit()

async def add_questions_to_db():
    questions_file_path = BASE_DIR / "questions.txt"
    try:
        with open(questions_file_path, 'r', encoding='utf-8') as f:
            questions_list = [line.strip() for line in f if line.strip()]
        if not questions_list: return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executemany("INSERT OR IGNORE INTO questions (text) VALUES (?)", [(q,) for q in questions_list])
            await db.commit()
            logging.info(f"Добавлено/обновлено {len(questions_list)} вопросов из файла.")
    except FileNotFoundError:
        logging.error(f"Файл с вопросами не найден: {questions_file_path}.")

async def get_today_question_for_couple(couple_id: int):
    today = datetime.now().date()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT da.*, q.text as question_text FROM daily_answers da
               JOIN questions q ON da.question_id = q.question_id
               WHERE da.couple_id = ? AND da.question_date = ?""",
            (couple_id, today)
        )
        return await cursor.fetchone()

async def get_qotd_archive(couple_id: int):
    """Получает весь архив ответов на вопросы дня для пары."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT da.*, q.text as question_text FROM daily_answers da
               JOIN questions q ON da.question_id = q.question_id
               WHERE da.couple_id = ? AND (da.answer_user1 IS NOT NULL OR da.answer_user2 IS NOT NULL)
               ORDER BY da.question_date DESC""",
            (couple_id,)
        )
        return await cursor.fetchall()


async def get_random_question():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM questions ORDER BY RANDOM() LIMIT 1")
        return await cursor.fetchone()

async def add_custom_question(text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO questions (text) VALUES (?)", (text,))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def create_daily_question_entry(couple_id: int, question_id: int, user1_id: int, user2_id: int):
    today = datetime.now().date()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO daily_answers 
               (couple_id, question_id, user1_id, user2_id, question_date) 
               VALUES (?, ?, ?, ?, ?)""",
            (couple_id, question_id, user1_id, user2_id, today)
        )
        await db.commit()

async def save_answer(couple_id: int, user_id: int, answer: str):
    today = datetime.now().date()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user1_id FROM daily_answers WHERE couple_id = ? AND question_date = ?", (couple_id, today))
        row = await cursor.fetchone()
        if not row: return False
        column_to_update = "answer_user1" if user_id == row[0] else "answer_user2"
        await db.execute(
            f"UPDATE daily_answers SET {column_to_update} = ? WHERE couple_id = ? AND question_date = ?",
            (answer, couple_id, today)
        )
        await db.commit()
        return True

async def get_today_question_for_couple(couple_id: int):
    today = datetime.now().date()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT da.*, q.text as question_text FROM daily_answers da
               JOIN questions q ON da.question_id = q.question_id
               WHERE da.couple_id = ? AND da.question_date = ?""",
            (couple_id, today)
        )
        return await cursor.fetchone()

async def get_all_couples_with_settings():
    """Получает все пары и их настройки."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                s.couple_id,
                u.user_id as user1_id,
                u.partner_id as user2_id,
                s.reminders_enabled,
                s.reminder_time,
                s.qotd_enabled,
                s.qotd_send_time,
                s.qotd_summary_time
            FROM couple_settings s
            JOIN users u ON s.couple_id = MIN(u.user_id, u.partner_id)
            GROUP BY s.couple_id
        """)
        return await cursor.fetchall()

async def get_all_pairs():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id, partner_id FROM users WHERE partner_id IS NOT NULL")
        return await cursor.fetchall()

async def add_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if await cursor.fetchone() is None:
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
            await db.commit()
            logging.info(f"Добавлен новый пользователь: {username} (ID: {user_id})")

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def link_partners(user1_id: int, user2_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("UPDATE users SET partner_id = ?, start_date = ? WHERE user_id = ?", (user2_id, today, user1_id))
        await db.execute("UPDATE users SET partner_id = ?, start_date = ? WHERE user_id = ?", (user1_id, today, user2_id))
        await db.commit()
        logging.info(f"Пользователи {user1_id} и {user2_id} теперь партнеры.")
        couple_id = min(user1_id, user2_id)
        await get_couple_settings(couple_id)

async def get_partner(user_id: int):
    user_data = await get_user(user_id)
    if user_data and user_data['partner_id']:
        return await get_user(user_data['partner_id'])
    return None

async def unlink_partners(user_id: int):
    partner = await get_partner(user_id)
    if not partner: return False
    partner_id = partner['user_id']
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET partner_id = NULL, start_date = NULL WHERE user_id = ?", (user_id,))
        await db.execute("UPDATE users SET partner_id = NULL, start_date = NULL WHERE user_id = ?", (partner_id,))
        await db.commit()
        logging.info(f"Связь между {user_id} и {partner_id} разорвана.")
        return True

async def add_event(couple_id: int, event_date: datetime, title: str, details: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO events (couple_id, event_date, title, details) VALUES (?, ?, ?, ?)",
            (couple_id, event_date.isoformat(), title, details)
        )
        await db.commit()
        logging.info(f"Для пары {couple_id} добавлено событие '{title}' на {event_date}")

async def get_events_for_period(couple_id: int, start_date: datetime, end_date: datetime):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT *, strftime('%w', event_date) as weekday FROM events WHERE couple_id = ? AND event_date BETWEEN ? AND ? ORDER BY event_date",
            (couple_id, start_date.isoformat(), end_date.isoformat())
        )
        return await cursor.fetchall()

async def get_event_by_id(event_id: int, couple_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM events WHERE event_id = ? AND couple_id = ?", (event_id, couple_id)
        )
        return await cursor.fetchone()

async def delete_event_by_id(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        await db.commit()
        logging.info(f"Событие {event_id} удалено.")

async def get_couple_settings(couple_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM couple_settings WHERE couple_id = ?", (couple_id,))
        settings = await cursor.fetchone()
        if not settings:
            await db.execute("INSERT INTO couple_settings (couple_id) VALUES (?)", (couple_id,))
            await db.commit()
            cursor = await db.execute("SELECT * FROM couple_settings WHERE couple_id = ?", (couple_id,))
            settings = await cursor.fetchone()
        return settings

async def update_reminders_settings(couple_id: int, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ", ".join([f"{key} = ?" for key in kwargs])
        values = list(kwargs.values())
        values.append(couple_id)
        await db.execute(f"UPDATE couple_settings SET {fields} WHERE couple_id = ?", tuple(values))
        await db.commit()
        logging.info(f"Настройки для пары {couple_id} обновлены: {kwargs}")

async def get_couples_for_reminder(current_time_str: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                s.couple_id,
                u.user_id as user1_id,
                u.partner_id as user2_id
            FROM couple_settings s
            JOIN users u ON s.couple_id = MIN(u.user_id, u.partner_id)
            WHERE s.reminders_enabled = 1 AND s.reminder_time = ?
            GROUP BY s.couple_id
        """, (current_time_str,))
        return await cursor.fetchall()

async def add_wish(user_id: int, title: str, link: str = None, photo_file_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO wishlist (user_id, title, link, photo_file_id) VALUES (?, ?, ?, ?)",
            (user_id, title, link, photo_file_id)
        )
        await db.commit()
        logging.info(f"Пользователь {user_id} добавил желание '{title}'")

async def get_wishes(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM wishlist WHERE user_id = ?", (user_id,))
        return await cursor.fetchall()

async def get_wish_by_id(wish_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM wishlist WHERE wish_id = ?", (wish_id,))
        return await cursor.fetchone()

async def delete_wish_by_id(wish_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM wishlist WHERE wish_id = ? AND user_id = ?", (wish_id, user_id))
        await db.commit()
        logging.info(f"Пользователь {user_id} удалил желание {wish_id}")

async def book_wish(wish_id: int, booker_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE wishlist SET booked_by_id = ? WHERE wish_id = ?", (booker_id, wish_id))
        await db.commit()

async def unbook_wish(wish_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE wishlist SET booked_by_id = NULL WHERE wish_id = ?", (wish_id,))
        await db.commit()

async def add_memory(couple_id: int, media_type: str, media_file_id: str, description: str):
    """Добавляет новое воспоминание."""
    today = datetime.now().date()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO memories (couple_id, media_type, media_file_id, description, added_at) VALUES (?, ?, ?, ?, ?)",
            (couple_id, media_type, media_file_id, description, today)
        )
        await db.commit()
        logging.info(f"Для пары {couple_id} добавлено новое воспоминание.")

async def get_random_memory(couple_id: int):
    """Получает случайное воспоминание для пары."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM memories WHERE couple_id = ? ORDER BY RANDOM() LIMIT 1", (couple_id,))
        return await cursor.fetchone()

async def get_all_memories(couple_id: int):
    """Получает все воспоминания для пары в хронологическом порядке."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM memories WHERE couple_id = ? ORDER BY added_at DESC", (couple_id,))
        return await cursor.fetchall()

async def add_movie_to_watchlist(couple_id: int, title: str):
    """Добавляет фильм в список просмотра пары."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO movie_watchlist (couple_id, title) VALUES (?, ?)",
                (couple_id, title)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError: # Если такой фильм уже есть
            return False

async def get_movie_watchlist(couple_id: int):
    """Получает список фильмов для просмотра для пары."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM movie_watchlist WHERE couple_id = ? ORDER BY id", (couple_id,))
        return await cursor.fetchall()

async def delete_movie_from_watchlist(movie_id: int, couple_id: int):
    """Удаляет фильм из списка просмотра."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM movie_watchlist WHERE id = ? AND couple_id = ?", (movie_id, couple_id))
        await db.commit()

async def add_date_idea(couple_id: int, idea_text: str):
    """Добавляет новую идею для свидания."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO date_ideas (couple_id, idea_text) VALUES (?, ?)",
                (couple_id, idea_text)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def get_date_ideas(couple_id: int):
    """Получает все идеи для свиданий для пары."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM date_ideas WHERE couple_id = ? ORDER BY is_completed, id", (couple_id,))
        return await cursor.fetchall()

async def toggle_date_idea_status(idea_id: int, couple_id: int):
    """Переключает статус выполнения идеи."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Инвертируем текущее значение is_completed
        await db.execute(
            "UPDATE date_ideas SET is_completed = NOT is_completed WHERE id = ? AND couple_id = ?",
            (idea_id, couple_id)
        )
        await db.commit()

async def delete_date_idea(idea_id: int, couple_id: int):
    """Удаляет идею для свидания."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM date_ideas WHERE id = ? AND couple_id = ?", (idea_id, couple_id))
        await db.commit()
