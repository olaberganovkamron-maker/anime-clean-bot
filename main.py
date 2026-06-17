import os
import asyncio
import logging
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ==================== SOZLAMALAR (CONFIG) ====================
# Render'da "Environment Variables" bo'limiga BOT_TOKEN va ADMIN_ID qo'shing.
# Termux'da ishlatsangiz, pastdagi "BOTFATHER_DAN..." va "123456789" o'rniga
# to'g'ridan-to'g'ri o'z token/ID'ingizni yozishingiz mumkin.

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7164685036"))
DB_NAME = "anime_bot.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==================== BAZA (DATABASE) ====================

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS animes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            photo_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            file_type TEXT DEFAULT 'video',
            FOREIGN KEY (anime_id) REFERENCES animes(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            channel_username TEXT,
            channel_title TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)

    conn.commit()
    conn.close()


# ---------- ANIME FUNKSIYALARI ----------

def add_anime(code, name, description=None, photo_file_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO animes (code, name, description, photo_file_id) VALUES (?, ?, ?, ?)",
        (code, name, description, photo_file_id)
    )
    conn.commit()
    anime_id = cur.lastrowid
    conn.close()
    return anime_id


def get_anime_by_code(code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM animes WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row


def get_anime_by_id(anime_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM animes WHERE id = ?", (anime_id,))
    row = cur.fetchone()
    conn.close()
    return row


def search_anime_by_name(name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM animes WHERE name LIKE ?", (f"%{name}%",))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_all_animes():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM animes ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def update_anime_field(anime_id, field, value):
    allowed = {"name", "description", "photo_file_id", "code"}
    if field not in allowed:
        raise ValueError("Noto'g'ri maydon")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE animes SET {field} = ? WHERE id = ?", (value, anime_id))
    conn.commit()
    conn.close()


def delete_anime(anime_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM episodes WHERE anime_id = ?", (anime_id,))
    cur.execute("DELETE FROM animes WHERE id = ?", (anime_id,))
    conn.commit()
    conn.close()


def count_animes():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM animes")
    c = cur.fetchone()["c"]
    conn.close()
    return c


# ---------- QISMLAR FUNKSIYALARI ----------

def add_episode(anime_id, episode_number, file_id, file_type="video"):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO episodes (anime_id, episode_number, file_id, file_type) VALUES (?, ?, ?, ?)",
        (anime_id, episode_number, file_id, file_type)
    )
    conn.commit()
    conn.close()


def get_episodes_by_anime(anime_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM episodes WHERE anime_id = ? ORDER BY episode_number ASC",
        (anime_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_next_episode_number(anime_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT MAX(episode_number) as max_num FROM episodes WHERE anime_id = ?",
        (anime_id,)
    )
    row = cur.fetchone()
    conn.close()
    return (row["max_num"] or 0) + 1


def get_episode_by_id(episode_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    row = cur.fetchone()
    conn.close()
    return row


# ---------- FOYDALANUVCHI FUNKSIYALARI ----------

def add_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()


def is_user_exists(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def count_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM users")
    c = cur.fetchone()["c"]
    conn.close()
    return c


def count_users_since(days):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) as c FROM users WHERE joined_at >= datetime('now', ?)",
        (f"-{days} days",)
    )
    c = cur.fetchone()["c"]
    conn.close()
    return c


def get_all_user_ids():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = [r["user_id"] for r in cur.fetchall()]
    conn.close()
    return rows


# ---------- KANALLAR (MAJBURIY OBUNA) ----------

def add_required_channel(channel_id, channel_username, channel_title):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO required_channels (channel_id, channel_username, channel_title) VALUES (?, ?, ?)",
        (channel_id, channel_username, channel_title)
    )
    conn.commit()
    conn.close()


def get_required_channels():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM required_channels")
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_required_channel(channel_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM required_channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()


# ---------- ADMINLAR ----------

def add_admin(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()


def remove_admin(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_all_admins():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins")
    rows = [r["user_id"] for r in cur.fetchall()]
    conn.close()
    return rows


# ---------- YUKLAB OLISHLAR (COUNTER) ----------

def log_download(episode_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO downloads (episode_id, user_id) VALUES (?, ?)",
        (episode_id, user_id)
    )
    conn.commit()
    conn.close()


def count_downloads():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM downloads")
    c = cur.fetchone()["c"]
    conn.close()
    return c


# ==================== YORDAMCHI FUNKSIYALAR ====================

def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    return user_id in get_all_admins()


def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🍿 Anime kodi orqali qidirish")],
        [KeyboardButton(text="🔎 Anime nomi orqali qidirish")],
    ]
    if is_admin(user_id):
        buttons.append([KeyboardButton(text="🎛 Boshqaruv paneli")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="➕ Anime qo'shish"), KeyboardButton(text="🗂 Animelar ro'yxati")],
        [KeyboardButton(text="🔒 Majburiy obuna"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="🏧 Adminlar qo'shish/o'chirish")],
        [KeyboardButton(text="⬅️ Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def anime_list_inline_keyboard(animes):
    rows = []
    for anime in animes:
        rows.append([
            InlineKeyboardButton(text=anime["name"], callback_data=f"anime_view_{anime['id']}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def anime_edit_keyboard(anime_id: int):
    rows = [
        [InlineKeyboardButton(text="✒ Nomini o'zgartirish", callback_data=f"edit_name_{anime_id}")],
        [InlineKeyboardButton(text="🏞 Rasmini o'zgartirish", callback_data=f"edit_photo_{anime_id}")],
        [InlineKeyboardButton(text="🎞 Tavsifini o'zgartirish", callback_data=f"edit_desc_{anime_id}")],
        [InlineKeyboardButton(text="🔢 Kodini o'zgartirish", callback_data=f"edit_code_{anime_id}")],
        [InlineKeyboardButton(text="➕ Qism qo'shish", callback_data=f"add_episode_{anime_id}")],
        [InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data=f"delete_anime_{anime_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ==================== FSM HOLATLARI ====================

class AddAnime(StatesGroup):
    waiting_name = State()
    waiting_code = State()
    waiting_description = State()
    waiting_photo = State()


class EditAnime(StatesGroup):
    waiting_new_name = State()
    waiting_new_code = State()
    waiting_new_description = State()
    waiting_new_photo = State()


class AddEpisode(StatesGroup):
    waiting_video = State()


# ==================== START ====================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    add_user(message.from_user.id)
    await message.answer(
        "Xush kelibsiz! 🎬\nAnime kodi yoki nomi orqali qidirishingiz mumkin.",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )


@dp.message(F.text == "⬅️ Asosiy menyu")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu", reply_markup=main_menu_keyboard(message.from_user.id))


# ==================== ADMIN PANEL ====================

@dp.message(F.text == "🎛 Boshqaruv paneli")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🎛 Boshqaruv paneli", reply_markup=admin_panel_keyboard())


# ---------- ANIME QO'SHISH ----------

@dp.message(F.text == "➕ Anime qo'shish")
async def add_anime_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddAnime.waiting_name)
    await message.answer("Anime nomini kiriting:")


@dp.message(AddAnime.waiting_name)
async def add_anime_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddAnime.waiting_code)
    await message.answer("Anime kodini kiriting (masalan: 1001):")


@dp.message(AddAnime.waiting_code)
async def add_anime_code(message: Message, state: FSMContext):
    code = message.text.strip()
    if get_anime_by_code(code):
        await message.answer("⚠️ Bu kod band, boshqa kod kiriting:")
        return
    await state.update_data(code=code)
    await state.set_state(AddAnime.waiting_description)
    await message.answer("Anime tavsifini kiriting (yoki /skip):")


@dp.message(AddAnime.waiting_description)
async def add_anime_description(message: Message, state: FSMContext):
    description = None if message.text == "/skip" else message.text
    await state.update_data(description=description)
    await state.set_state(AddAnime.waiting_photo)
    await message.answer("Anime rasmini yuboring (yoki /skip):")


@dp.message(AddAnime.waiting_photo, F.photo)
async def add_anime_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    data = await state.get_data()
    add_anime(
        code=data["code"],
        name=data["name"],
        description=data.get("description"),
        photo_file_id=photo_file_id,
    )
    await state.clear()
    await message.answer(
        f"✅ Anime qo'shildi!\n🎬 {data['name']}\n🔢 Kod: {data['code']}\n\n"
        f"Endi qism qo'shish uchun animelar ro'yxatidan tanlang.",
        reply_markup=admin_panel_keyboard()
    )


@dp.message(AddAnime.waiting_photo, F.text == "/skip")
async def add_anime_skip_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    add_anime(
        code=data["code"],
        name=data["name"],
        description=data.get("description"),
        photo_file_id=None,
    )
    await state.clear()
    await message.answer(
        f"✅ Anime qo'shildi!\n🎬 {data['name']}\n🔢 Kod: {data['code']}",
        reply_markup=admin_panel_keyboard()
    )


# ---------- ANIMELAR RO'YXATI ----------

@dp.message(F.text == "🗂 Animelar ro'yxati")
async def anime_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    animes = get_all_animes()
    if not animes:
        await message.answer("Hozircha animelar yo'q.")
        return
    await message.answer(
        "🗂 Animelar ro'yxati (tahrirlash uchun bosing):",
        reply_markup=anime_list_inline_keyboard(animes)
    )


@dp.callback_query(F.data.startswith("anime_view_"))
async def anime_view(callback: CallbackQuery):
    anime_id = int(callback.data.split("_")[-1])
    anime = get_anime_by_id(anime_id)
    if not anime:
        await callback.answer("Topilmadi", show_alert=True)
        return
    episodes = get_episodes_by_anime(anime_id)
    text = (
        f"🎬 {anime['name']}\n"
        f"🔢 Kod: {anime['code']}\n"
        f"🎞 Tavsif: {anime['description'] or '—'}\n"
        f"📺 Qismlar soni: {len(episodes)}"
    )
    if anime["photo_file_id"]:
        await callback.message.answer_photo(
            anime["photo_file_id"], caption=text, reply_markup=anime_edit_keyboard(anime_id)
        )
    else:
        await callback.message.answer(text, reply_markup=anime_edit_keyboard(anime_id))
    await callback.answer()


# ---------- ANIME TAHRIRLASH ----------

@dp.callback_query(F.data.startswith("edit_name_"))
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    anime_id = int(callback.data.split("_")[-1])
    await state.update_data(anime_id=anime_id)
    await state.set_state(EditAnime.waiting_new_name)
    await callback.message.answer("Yangi nomni kiriting:")
    await callback.answer()


@dp.message(EditAnime.waiting_new_name)
async def edit_name_save(message: Message, state: FSMContext):
    data = await state.get_data()
    update_anime_field(data["anime_id"], "name", message.text)
    await state.clear()
    await message.answer("✅ Nomi o'zgartirildi.", reply_markup=admin_panel_keyboard())


@dp.callback_query(F.data.startswith("edit_code_"))
async def edit_code_start(callback: CallbackQuery, state: FSMContext):
    anime_id = int(callback.data.split("_")[-1])
    await state.update_data(anime_id=anime_id)
    await state.set_state(EditAnime.waiting_new_code)
    await callback.message.answer("Yangi kodni kiriting:")
    await callback.answer()


@dp.message(EditAnime.waiting_new_code)
async def edit_code_save(message: Message, state: FSMContext):
    code = message.text.strip()
    if get_anime_by_code(code):
        await message.answer("⚠️ Bu kod band, boshqa kod kiriting:")
        return
    data = await state.get_data()
    update_anime_field(data["anime_id"], "code", code)
    await state.clear()
    await message.answer("✅ Kodi o'zgartirildi.", reply_markup=admin_panel_keyboard())


@dp.callback_query(F.data.startswith("edit_desc_"))
async def edit_desc_start(callback: CallbackQuery, state: FSMContext):
    anime_id = int(callback.data.split("_")[-1])
    await state.update_data(anime_id=anime_id)
    await state.set_state(EditAnime.waiting_new_description)
    await callback.message.answer("Yangi tavsifni kiriting:")
    await callback.answer()


@dp.message(EditAnime.waiting_new_description)
async def edit_desc_save(message: Message, state: FSMContext):
    data = await state.get_data()
    update_anime_field(data["anime_id"], "description", message.text)
    await state.clear()
    await message.answer("✅ Tavsifi o'zgartirildi.", reply_markup=admin_panel_keyboard())


@dp.callback_query(F.data.startswith("edit_photo_"))
async def edit_photo_start(callback: CallbackQuery, state: FSMContext):
    anime_id = int(callback.data.split("_")[-1])
    await state.update_data(anime_id=anime_id)
    await state.set_state(EditAnime.waiting_new_photo)
    await callback.message.answer("Yangi rasmni yuboring:")
    await callback.answer()


@dp.message(EditAnime.waiting_new_photo, F.photo)
async def edit_photo_save(message: Message, state: FSMContext):
    data = await state.get_data()
    update_anime_field(data["anime_id"], "photo_file_id", message.photo[-1].file_id)
    await state.clear()
    await message.answer("✅ Rasmi o'zgartirildi.", reply_markup=admin_panel_keyboard())


# ---------- ANIMENI O'CHIRISH ----------

@dp.callback_query(F.data.startswith("delete_anime_"))
async def delete_anime_confirm(callback: CallbackQuery):
    anime_id = int(callback.data.split("_")[-1])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_delete_{anime_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_delete"),
    ]])
    await callback.message.answer("Rostdan ham o'chirmoqchimisiz?", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete_"))
async def delete_anime_do(callback: CallbackQuery):
    anime_id = int(callback.data.split("_")[-1])
    delete_anime(anime_id)
    await callback.message.answer("🗑 Anime o'chirildi.")
    await callback.answer()


@dp.callback_query(F.data == "cancel_delete")
async def delete_anime_cancel(callback: CallbackQuery):
    await callback.message.answer("Bekor qilindi.")
    await callback.answer()


# ---------- QISM QO'SHISH ----------

@dp.callback_query(F.data.startswith("add_episode_"))
async def add_episode_start(callback: CallbackQuery, state: FSMContext):
    anime_id = int(callback.data.split("_")[-1])
    await state.update_data(anime_id=anime_id)
    await state.set_state(AddEpisode.waiting_video)
    next_num = get_next_episode_number(anime_id)
    await callback.message.answer(
        f"{next_num}-qism uchun videoni yuboring.\n"
        f"Tugatish uchun /done yozing."
    )
    await callback.answer()


@dp.message(AddEpisode.waiting_video, F.video)
async def add_episode_save(message: Message, state: FSMContext):
    data = await state.get_data()
    anime_id = data["anime_id"]
    episode_num = get_next_episode_number(anime_id)
    add_episode(anime_id, episode_num, message.video.file_id, "video")
    await message.answer(
        f"{episode_num}-qism saqlandi ✅\nKeyingi qismni yuboring yoki /done bilan tugating."
    )


@dp.message(AddEpisode.waiting_video, Command("done"))
async def add_episode_done(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Qismlar qo'shish tugatildi.", reply_markup=admin_panel_keyboard())


# ==================== ISHGA TUSHIRISH ====================

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
