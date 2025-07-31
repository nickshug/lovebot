from aiogram.fsm.state import State, StatesGroup

class Pairing(StatesGroup):
    pass

class Actions(StatesGroup):
    waiting_for_compliment_text = State()
    waiting_for_send_time_choice = State()
    waiting_for_send_date = State()
    waiting_for_send_time = State()
    waiting_for_attachment = State()

class Calendar(StatesGroup):
    waiting_for_event_date = State()
    waiting_for_event_time = State()
    waiting_for_event_title = State()
    waiting_for_event_details = State()

class Settings(StatesGroup):
    waiting_for_reminder_time = State()
    waiting_for_qotd_send_time = State()
    waiting_for_qotd_summary_time = State()

class Wishlist(StatesGroup):
    waiting_for_title = State()
    waiting_for_link = State()
    waiting_for_photo = State()

class QOTD(StatesGroup):
    waiting_for_answer = State()
    waiting_for_new_question = State()

class Memory(StatesGroup):
    waiting_for_media = State()
    waiting_for_description = State()
    waiting_for_date = State()

class Movie(StatesGroup):
    choosing_genre = State()

class Movie(StatesGroup):
    choosing_genre = State()
    waiting_for_movie_title = State()

class DateIdea(StatesGroup):
    waiting_for_idea_text = State()