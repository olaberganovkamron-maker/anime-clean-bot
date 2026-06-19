"""
🎌 ANIME BOT - Aiogram versiya
Render.com ga tayyor

O'rnatish:
    pip install aiogram asyncpg

Sozlash:
    BOT_TOKEN, BOT_USERNAME, ADMIN_IDS ni o'zgartiring
"""

import os
import asyncio
import logging
import asyncpg
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# =============================================
# ⚙️ SOZLAMALAR
# =============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "your_bot_username")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",")]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost/anime_bot")

DEFAULT_SETTINGS = {
    "welcome_message": "🎌 Xush kelibsiz! Anime kodini yuboring.",
    "not_found_message": "😔 Anime topilmadi",
    "subscribe_message": "📢 Quyidagi kanallarga obuna bo'ling",
    "check_button": "✅ Tekshirish"
}

logging.basicConfig(level=logging.INFO)

# =============================================
# 🗄️ DATABASE
# =============================================
class Database:
    def __init__(self):
        self.pool = None

    async def init(self):
        ssl = "require" if "render.com" in DATABASE_URL or "amazonaws" in DATABASE_URL else None
        self.pool = await asyncpg.create_pool(dsn=DATABASE_URL, ssl=ssl)
        await self.create_tables()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    joined_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS admins (
                    admin_id BIGINT PRIMARY KEY,
                    added_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS animes (
                    id SERIAL PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    photo_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    views INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS episodes (
                    id SERIAL PRIMARY KEY,
                    anime_code TEXT REFERENCES animes(code) ON DELETE CASCADE,
                    episode_number INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    file_type TEXT DEFAULT 'video',
                    added_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS subscription_channels (
                    id SERIAL PRIMARY KEY,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_name TEXT
                );
                CREATE TABLE IF NOT EXISTS post_channels (
                    id SERIAL PRIMARY KEY,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_name TEXT
                );
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            for key, value in DEFAULT_SETTINGS.items():
                await conn.execute("""
                    INSERT INTO bot_settings (key, value)
                    VALUES ($1, $2) ON CONFLICT (key) DO NOTHING
                """, key, value)

    async def add_user(self, user_id, username, full_name):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, full_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET username=$2, full_name=$3
            """, user_id, username, full_name)

    async def get_users_count(self):
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM users")

    async def get_new_users_count(self, days):
        async with self.pool.acquire() as conn:
            since = datetime.now() - timedelta(days=days)
            return await conn.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= $1", since)

    async def is_admin(self, user_id):
        if user_id in ADMIN_IDS:
            return True
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT admin_id FROM admins WHERE admin_id=$1", user_id) is not None

    async def add_admin(self, admin_id):
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO admins (admin_id) VALUES ($1) ON CONFLICT DO NOTHING", admin_id)

    async def remove_admin(self, admin_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM admins WHERE admin_id=$1", admin_id)

    async def get_admins(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT admin_id FROM admins")
            return [r["admin_id"] for r in rows]

    async def add_anime(self, code, name, description=None, photo_id=None):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO animes (code, name, description, photo_id)
                VALUES ($1, $2, $3, $4)
            """, code, name, description, photo_id)

    async def get_anime(self, code):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM animes WHERE code=$1", code)

    async def get_anime_by_name(self, name):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM animes WHERE LOWER(name) LIKE $1", f"%{name.lower()}%")

    async def get_all_animes(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM animes ORDER BY created_at DESC")

    async def get_animes_count(self):
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM animes")

    async def update_anime_name(self, code, val):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET name=$1 WHERE code=$2", val, code)

    async def update_anime_photo(self, code, val):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET photo_id=$1 WHERE code=$2", val, code)

    async def update_anime_description(self, code, val):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET description=$1 WHERE code=$2", val, code)

    async def update_anime_code(self, old, new):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET code=$1 WHERE code=$2", new, old)

    async def delete_anime(self, code):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM animes WHERE code=$1", code)

    async def increment_views(self, code):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET views=views+1 WHERE code=$1", code)

    async def add_episode(self, anime_code, episode_number, file_id, file_type="video"):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO episodes (anime_code, episode_number, file_id, file_type)
                VALUES ($1, $2, $3, $4)
            """, anime_code, episode_number, file_id, file_type)

    async def get_episodes(self, anime_code):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM episodes WHERE anime_code=$1 ORDER BY episode_number", anime_code)

    async def get_episode(self, anime_code, ep_num):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM episodes WHERE anime_code=$1 AND episode_number=$2", anime_code, ep_num)

    async def add_sub_channel(self, channel_id, channel_name):
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO subscription_channels (channel_id, channel_name) VALUES ($1, $2) ON CONFLICT DO NOTHING", channel_id, channel_name)

    async def remove_sub_channel(self, channel_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM subscription_channels WHERE channel_id=$1", channel_id)

    async def get_sub_channels(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM subscription_channels")

    async def add_post_channel(self, channel_id, channel_name):
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO post_channels (channel_id, channel_name) VALUES ($1, $2) ON CONFLICT DO NOTHING", channel_id, channel_name)

    async def remove_post_channel(self, channel_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM post_channels WHERE channel_id=$1", channel_id)

    async def get_post_channels(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM post_channels")

    async def get_setting(self, key):
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT value FROM bot_settings WHERE key=$1", key)

    async def set_setting(self, key, value):
        async with self.pool.acquire() as conn:
            await conn.execute("INSERT INTO bot_settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value=$2", key, value)

db = Database()

# =============================================
# 📋 FSM STATES
# =============================================
class AddAnime(StatesGroup):
    code = State()
    name = State()
    desc = State()
    photo = State()

class AddEpisode(StatesGroup):
    code = State()
    files = State()

class EditAnime(StatesGroup):
    name = State()
    photo = State()
    desc = State()
    code = State()

class AddSubChannel(StatesGroup):
    waiting = State()

class AddPostChannel(StatesGroup):
    waiting = State()

class AddAdminState(StatesGroup):
    waiting = State()

class UpdateSetting(StatesGroup):
    waiting = State()

class PostAnime(StatesGroup):
    code = State()
    channel = State()

# =============================================
# 🔧 HELPERS
# =============================================
def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="admin_add_anime")],
        [InlineKeyboardButton(text="🗂 Animelar ro'yxati", callback_data="admin_anime_list")],
        [InlineKeyboardButton(text="➕ Qism qo'shish", callback_data="admin_add_episode")],
        [InlineKeyboardButton(text="🔒 Majburiy obuna", callback_data="admin_subscription")],
        [InlineKeyboardButton(text="📤 Kanalga post yuborish", callback_data="admin_post")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔊 Bot sozlari", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🏧 Adminlar boshqaruvi", callback_data="admin_admins")],
    ])

async def check_subscription(bot: Bot, user_id: int):
    channels = await db.get_sub_channels()
    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_subscribed.append(ch)
        except:
            not_subscribed.append(ch)
    return not_subscribed

async def send_anime_info(message: Message, anime, bot: Bot):
    episodes = await db.get_episodes(anime["code"])
    await db.increment_views(anime["code"])

    caption = f"🎌 <b>{anime['name']}</b>\n"
    if anime["description"]:
        caption += f"\n📝 {anime['description']}\n"
    caption += f"\n🔢 Kod: <code>{anime['code']}</code>"
    caption += f"\n🎬 Qismlar: {len(episodes)}"
    caption += f"\n👁 Ko'rishlar: {anime['views'] + 1}"

    buttons = []
    if episodes:
        row = []
        for ep in episodes:
            row.append(InlineKeyboardButton(
                text=f"▶️ {ep['episode_number']}-qism",
                callback_data=f"watch_{anime['code']}_{ep['episode_number']}"
            ))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    if anime["photo_id"]:
        await message.answer_photo(photo=anime["photo_id"], caption=caption, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

# =============================================
# 👤 USER HANDLERS
# =============================================
async def cmd_start(message: Message, bot: Bot):
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    args = message.text.split()
    if len(args) > 1:
        code = args[1].upper()
        anime = await db.get_anime(code)
        if anime:
            await send_anime_info(message, anime, bot)
            return
    welcome = await db.get_setting("welcome_message")
    await message.answer(welcome)

async def handle_text(message: Message, bot: Bot):
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = message.text.strip()

    not_sub = await check_subscription(bot, message.from_user.id)
    if not_sub:
        sub_msg = await db.get_setting("subscribe_message")
        check_btn = await db.get_setting("check_button")
        buttons = [[InlineKeyboardButton(text=f"📢 {ch['channel_name'] or ch['channel_id']}", url=f"https://t.me/{ch['channel_id'].replace('@', '')}")] for ch in not_sub]
        buttons.append([InlineKeyboardButton(text=check_btn, callback_data="check_sub")])
        await message.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    anime = await db.get_anime(text.upper())
    if anime:
        await send_anime_info(message, anime, bot)
        return

    results = await db.get_anime_by_name(text)
    if results:
        buttons = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"watch_{a['code']}")] for a in results[:8]]
        await message.answer(f"🔎 '{text}' bo'yicha natijalar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        not_found = await db.get_setting("not_found_message")
        await message.answer(not_found)

async def cb_check_sub(callback: CallbackQuery, bot: Bot):
    not_sub = await check_subscription(bot, callback.from_user.id)
    if not_sub:
        await callback.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)
    else:
        await callback.answer("✅ Rahmat! Endi foydalanishingiz mumkin.", show_alert=True)
        await callback.message.delete()

async def cb_watch(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    not_sub = await check_subscription(bot, callback.from_user.id)
    if not_sub:
        sub_msg = await db.get_setting("subscribe_message")
        check_btn = await db.get_setting("check_button")
        buttons = [[InlineKeyboardButton(text=f"📢 {ch['channel_name'] or ch['channel_id']}", url=f"https://t.me/{ch['channel_id'].replace('@', '')}")] for ch in not_sub]
        buttons.append([InlineKeyboardButton(text=check_btn, callback_data="check_sub")])
        await callback.message.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    parts = callback.data.replace("watch_", "").split("_")
    anime_code = parts[0]
    anime = await db.get_anime(anime_code)
    if not anime:
        await callback.message.answer("❌ Anime topilmadi.")
        return

    if len(parts) == 1:
        episodes = await db.get_episodes(anime_code)
        if not episodes:
            await callback.message.answer("😔 Hozircha qism yo'q.")
            return
        buttons = []
        row = []
        for ep in episodes:
            row.append(InlineKeyboardButton(text=f"▶️ {ep['episode_number']}-qism", callback_data=f"watch_{anime_code}_{ep['episode_number']}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        await callback.message.answer(f"🎌 <b>{anime['name']}</b> — Qismni tanlang:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        ep_num = int(parts[1])
        episode = await db.get_episode(anime_code, ep_num)
        if not episode:
            await callback.message.answer("❌ Qism topilmadi.")
            return
        caption = f"🎌 <b>{anime['name']}</b> — {ep_num}-qism"
        next_ep = await db.get_episode(anime_code, ep_num + 1)
        buttons = []
        if next_ep:
            buttons.append([InlineKeyboardButton(text=f"▶️ {ep_num + 1}-qism →", callback_data=f"watch_{anime_code}_{ep_num + 1}")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        if episode["file_type"] == "video":
            await callback.message.answer_video(video=episode["file_id"], caption=caption, parse_mode="HTML", reply_markup=keyboard)
        else:
            await callback.message.answer_document(document=episode["file_id"], caption=caption, parse_mode="HTML", reply_markup=keyboard)

# =============================================
# 🎛️ ADMIN HANDLERS
# =============================================
async def cmd_admin(message: Message):
    if not await db.is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz!")
        return
    await message.answer("🎛 <b>Boshqaruv paneli</b>\n\nBo'limni tanlang:", parse_mode="HTML", reply_markup=admin_keyboard())

async def cb_admin(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("❌ Admin emassiz!", show_alert=True)
        return
    await callback.answer()
    data = callback.data

    if data == "admin_back":
        await callback.message.edit_text("🎛 <b>Boshqaruv paneli</b>\n\nBo'limni tanlang:", parse_mode="HTML", reply_markup=admin_keyboard())

    elif data == "admin_add_anime":
        await callback.message.answer("🔢 Anime kodini kiriting (masalan: NRT):")
        await state.set_state(AddAnime.code)

    elif data == "admin_anime_list":
        animes = await db.get_all_animes()
        if not animes:
            await callback.message.edit_text("📭 Hozircha anime yo'q.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]]))
            return
        buttons = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"anime_manage_{a['code']}")] for a in animes]
        buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")])
        await callback.message.edit_text("🗂 <b>Animelar ro'yxati:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    elif data == "admin_add_episode":
        await callback.message.answer("🔢 Qism qo'shish uchun anime kodini kiriting:")
        await state.set_state(AddEpisode.code)

    elif data == "admin_subscription":
        channels = await db.get_sub_channels()
        text = "🔒 <b>Majburiy obuna kanallari:</b>\n\n"
        text += "\n".join([f"• {ch['channel_name']} ({ch['channel_id']})" for ch in channels]) if channels else "Kanal yo'q."
        buttons = [
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="sub_add")],
            [InlineKeyboardButton(text="❌ Kanal o'chirish", callback_data="sub_remove")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")],
        ]
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    elif data == "admin_post":
        await callback.message.answer("🔢 Post yuborish uchun anime kodini kiriting:")
        await state.set_state(PostAnime.code)

    elif data == "admin_stats":
        total = await db.get_users_count()
        n1 = await db.get_new_users_count(1)
        n3 = await db.get_new_users_count(3)
        n7 = await db.get_new_users_count(7)
        animes = await db.get_animes_count()
        text = (f"📊 <b>Statistika</b>\n\n"
                f"👤 <b>Obunachilar:</b>\n• Jami: {total}\n• 1 kun: +{n1}\n• 3 kun: +{n3}\n• 7 kun: +{n7}\n\n"
                f"🎞 <b>Animelar:</b> {animes}")
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")]]))

    elif data == "admin_settings":
        buttons = [
            [InlineKeyboardButton(text="👋 Xush kelibsiz xabari", callback_data="setting_welcome")],
            [InlineKeyboardButton(text="😔 Topilmadi xabari", callback_data="setting_not_found")],
            [InlineKeyboardButton(text="📢 Obuna xabari", callback_data="setting_sub_msg")],
            [InlineKeyboardButton(text="➕ Post kanal qo'shish", callback_data="setting_add_post_ch")],
            [InlineKeyboardButton(text="❌ Post kanal o'chirish", callback_data="setting_remove_post_ch")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")],
        ]
        await callback.message.edit_text("🔊 <b>Bot sozlari:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    elif data == "admin_admins":
        admins = await db.get_admins()
        text = "🏧 <b>Adminlar:</b>\n\n" + "\n".join([f"• <code>{a}</code>" for a in admins]) if admins else "🏧 <b>Adminlar:</b>\n\nQo'shimcha admin yo'q."
        buttons = [
            [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin_add_admin")],
            [InlineKeyboardButton(text="❌ Admin o'chirish", callback_data="admin_remove_admin")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")],
        ]
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    elif data == "admin_add_admin":
        await callback.message.answer("🏧 Yangi admin Telegram ID sini kiriting:")
        await state.set_state(AddAdminState.waiting)

    elif data == "admin_remove_admin":
        admins = await db.get_admins()
        if not admins:
            await callback.message.answer("Admin yo'q.")
            return
        buttons = [[InlineKeyboardButton(text=f"❌ {a}", callback_data=f"remove_admin_{a}")] for a in admins]
        await callback.message.answer("O'chirish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    elif data.startswith("remove_admin_"):
        admin_id = int(data.replace("remove_admin_", ""))
        await db.remove_admin(admin_id)
        await callback.message.edit_text(f"✅ Admin {admin_id} o'chirildi.")

    elif data.startswith("setting_"):
        setting = data.replace("setting_", "")
        if setting == "add_post_ch":
            await callback.message.answer("📤 Kanal kiriting:\n@kanal_username Kanal nomi")
            await state.set_state(AddPostChannel.waiting)
        elif setting == "remove_post_ch":
            channels = await db.get_post_channels()
            if not channels:
                await callback.message.answer("Kanal yo'q.")
                return
            buttons = [[InlineKeyboardButton(text=f"❌ {ch['channel_name'] or ch['channel_id']}", callback_data=f"del_post_ch_{ch['channel_id']}")] for ch in channels]
            await callback.message.answer("O'chirish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        elif setting in ("welcome", "not_found", "sub_msg"):
            prompts = {"welcome": "👋 Yangi xush kelibsiz xabarini kiriting:", "not_found": "😔 Topilmadi xabarini kiriting:", "sub_msg": "📢 Obuna xabarini kiriting:"}
            await callback.message.answer(prompts[setting])
            await state.update_data(setting_key=setting)
            await state.set_state(UpdateSetting.waiting)

    elif data.startswith("del_post_ch_"):
        ch_id = data.replace("del_post_ch_", "")
        await db.remove_post_channel(ch_id)
        await callback.message.edit_text(f"✅ {ch_id} o'chirildi.")

# --- Anime manage ---
async def cb_anime_manage(callback: CallbackQuery, state: FSMContext):
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()
    data = callback.data

    if data.startswith("anime_manage_"):
        code = data.replace("anime_manage_", "")
        anime = await db.get_anime(code)
        if not anime:
            await callback.message.answer("❌ Topilmadi.")
            return
        await state.update_data(edit_code=code)
        episodes = await db.get_episodes(code)
        buttons = [
            [InlineKeyboardButton(text="✒ Nomini o'zgartirish", callback_data=f"anime_edit_name_{code}")],
            [InlineKeyboardButton(text="🏞 Rasmini o'zgartirish", callback_data=f"anime_edit_photo_{code}")],
            [InlineKeyboardButton(text="🎞 Tavsifini o'zgartirish", callback_data=f"anime_edit_desc_{code}")],
            [InlineKeyboardButton(text="🔢 Kodini o'zgartirish", callback_data=f"anime_edit_code_{code}")],
            [InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data=f"anime_delete_{code}")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_anime_list")],
        ]
        await callback.message.edit_text(
            f"🎌 <b>{anime['name']}</b>\nKod: <code>{code}</code>\nQismlar: {len(episodes)}\nKo'rishlar: {anime['views']}\n\nNimani o'zgartirmoqchisiz?",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    elif data.startswith("anime_edit_name_"):
        await state.update_data(edit_code=data.replace("anime_edit_name_", ""))
        await callback.message.answer("✒ Yangi nomini kiriting:")
        await state.set_state(EditAnime.name)

    elif data.startswith("anime_edit_photo_"):
        await state.update_data(edit_code=data.replace("anime_edit_photo_", ""))
        await callback.message.answer("🏞 Yangi rasmini yuboring:")
        await state.set_state(EditAnime.photo)

    elif data.startswith("anime_edit_desc_"):
        await state.update_data(edit_code=data.replace("anime_edit_desc_", ""))
        await callback.message.answer("🎞 Yangi tavsifini kiriting:")
        await state.set_state(EditAnime.desc)

    elif data.startswith("anime_edit_code_"):
        await state.update_data(edit_code=data.replace("anime_edit_code_", ""))
        await callback.message.answer("🔢 Yangi kodini kiriting:")
        await state.set_state(EditAnime.code)

    elif data.startswith("anime_delete_"):
        code = data.replace("anime_delete_", "")
        await db.delete_anime(code)
        await callback.message.edit_text(f"🗑 <code>{code}</code> o'chirildi.", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_anime_list")]]))

    elif data == "admin_anime_list":
        animes = await db.get_all_animes()
        if not animes:
            await callback.message.edit_text("📭 Anime yo'q.")
            return
        buttons = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"anime_manage_{a['code']}")] for a in animes]
        buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")])
        await callback.message.edit_text("🗂 <b>Animelar:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# --- Sub channel callbacks ---
async def cb_sub(callback: CallbackQuery, state: FSMContext):
    if not await db.is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()
    data = callback.data
    if data == "sub_add":
        await callback.message.answer("Kanal kiriting:\n@kanal_username Kanal nomi")
        await state.set_state(AddSubChannel.waiting)
    elif data == "sub_remove":
        channels = await db.get_sub_channels()
        if not channels:
            await callback.message.answer("Kanal yo'q.")
            return
        buttons = [[InlineKeyboardButton(text=f"❌ {ch['channel_name'] or ch['channel_id']}", callback_data=f"sub_del_{ch['channel_id']}")] for ch in channels]
        await callback.message.answer("O'chirish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    elif data.startswith("sub_del_"):
        ch_id = data.replace("sub_del_", "")
        await db.remove_sub_channel(ch_id)
        await callback.message.edit_text(f"✅ {ch_id} o'chirildi.")

# =============================================
# 📝 FSM STEPS
# =============================================

# Anime qo'shish
async def fsm_anime_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    if await db.get_anime(code):
        await message.answer(f"❌ '{code}' kodi mavjud. Boshqa kod:")
        return
    await state.update_data(code=code)
    await message.answer("✒ Anime nomini kiriting:")
    await state.set_state(AddAnime.name)

async def fsm_anime_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("🎞 Tavsifini kiriting (/skip o'tkazish):")
    await state.set_state(AddAnime.desc)

async def fsm_anime_desc(message: Message, state: FSMContext):
    await state.update_data(desc=None if message.text.strip() == "/skip" else message.text.strip())
    await message.answer("🏞 Rasmini yuboring (/skip o'tkazish):")
    await state.set_state(AddAnime.photo)

async def fsm_anime_photo(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/skip":
        photo_id = None
    elif message.photo:
        photo_id = message.photo[-1].file_id
    else:
        await message.answer("Rasm yuboring yoki /skip:")
        return
    data = await state.get_data()
    await db.add_anime(data["code"], data["name"], data.get("desc"), photo_id)
    await message.answer(f"✅ <b>{data['name']}</b> qo'shildi!\nKod: <code>{data['code']}</code>", parse_mode="HTML")
    await state.clear()

# Qism qo'shish
async def fsm_episode_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    anime = await db.get_anime(code)
    if not anime:
        await message.answer("❌ Anime topilmadi. Kodni qayta kiriting:")
        return
    episodes = await db.get_episodes(code)
    next_num = len(episodes) + 1
    await state.update_data(code=code, ep_num=next_num)
    await message.answer(f"🎬 <b>{anime['name']}</b>\n\n📤 {next_num}-qismni yuboring.\nTugatish: /done", parse_mode="HTML")
    await state.set_state(AddEpisode.files)

async def fsm_episode_file(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data["code"]
    ep_num = data["ep_num"]
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    else:
        await message.answer("Video yoki fayl yuboring:")
        return
    await db.add_episode(code, ep_num, file_id, file_type)
    await state.update_data(ep_num=ep_num + 1)
    await message.answer(f"✅ {ep_num}-qism saqlandi!\n📤 {ep_num + 1}-qismni yuboring yoki /done.")

async def fsm_done(message: Message, state: FSMContext):
    data = await state.get_data()
    total = data.get("ep_num", 1) - 1
    await message.answer(f"✅ Jami {total} ta qism saqlandi! Kod: <code>{data.get('code', '')}</code>", parse_mode="HTML")
    await state.clear()

# Anime tahrirlash
async def fsm_edit_name(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_anime_name(data["edit_code"], message.text.strip())
    await message.answer("✅ Nom yangilandi!")
    await state.clear()

async def fsm_edit_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Rasm yuboring:")
        return
    data = await state.get_data()
    await db.update_anime_photo(data["edit_code"], message.photo[-1].file_id)
    await message.answer("✅ Rasm yangilandi!")
    await state.clear()

async def fsm_edit_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_anime_description(data["edit_code"], message.text.strip())
    await message.answer("✅ Tavsif yangilandi!")
    await state.clear()

async def fsm_edit_code(message: Message, state: FSMContext):
    data = await state.get_data()
    new_code = message.text.strip().upper()
    await db.update_anime_code(data["edit_code"], new_code)
    await message.answer(f"✅ Kod <code>{data['edit_code']}</code> → <code>{new_code}</code>", parse_mode="HTML")
    await state.clear()

# Sub kanal
async def fsm_sub_channel(message: Message, state: FSMContext):
    parts = message.text.strip().split(" ", 1)
    ch_id = parts[0]
    ch_name = parts[1] if len(parts) > 1 else ch_id
    await db.add_sub_channel(ch_id, ch_name)
    await message.answer(f"✅ {ch_name} (<code>{ch_id}</code>) qo'shildi!", parse_mode="HTML")
    await state.clear()

# Post kanal
async def fsm_post_channel(message: Message, state: FSMContext):
    parts = message.text.strip().split(" ", 1)
    ch_id = parts[0]
    ch_name = parts[1] if len(parts) > 1 else ch_id
    await db.add_post_channel(ch_id, ch_name)
    await message.answer(f"✅ Post kanali {ch_name} qo'shildi!", parse_mode="HTML")
    await state.clear()

# Admin qo'shish
async def fsm_add_admin(message: Message, state: FSMContext):
    try:
        admin_id = int(message.text.strip())
        await db.add_admin(admin_id)
        await message.answer(f"✅ Admin {admin_id} qo'shildi!")
    except:
        await message.answer("❌ Noto'g'ri ID:")
        return
    await state.clear()

# Sozlama
async def fsm_update_setting(message: Message, state: FSMContext):
    data = await state.get_data()
    mapping = {"welcome": "welcome_message", "not_found": "not_found_message", "sub_msg": "subscribe_message"}
    key = mapping.get(data.get("setting_key"))
    if key:
        await db.set_setting(key, message.text.strip())
        await message.answer("✅ Sozlama yangilandi!")
    await state.clear()

# Post yuborish
async def fsm_post_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    anime = await db.get_anime(code)
    if not anime:
        await message.answer("❌ Topilmadi. Kodni qayta kiriting:")
        return
    await state.update_data(post_code=code)
    channels = await db.get_post_channels()
    if not channels:
        await message.answer("❌ Post kanali sozlanmagan. /admin > Bot sozlari")
        await state.clear()
        return
    buttons = [[InlineKeyboardButton(text=f"📢 {ch['channel_name'] or ch['channel_id']}", callback_data=f"post_ch_{ch['channel_id']}")] for ch in channels]
    buttons.append([InlineKeyboardButton(text="📢 Barcha kanallarga", callback_data="post_ch_all")])
    await message.answer("Qaysi kanalga?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(PostAnime.channel)

async def cb_post_channel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    code = data.get("post_code")
    anime = await db.get_anime(code)
    episodes = await db.get_episodes(code)

    caption = f"🎌 <b>{anime['name']}</b>\n"
    if anime["description"]:
        caption += f"\n📝 {anime['description']}\n"
    caption += f"\n🔢 Kod: <code>{anime['code']}</code>\n🎬 Qismlar: {len(episodes)}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Tomosha qilish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
    ]])

    async def send_to(ch_id):
        try:
            if anime["photo_id"]:
                await bot.send_photo(ch_id, anime["photo_id"], caption=caption, parse_mode="HTML", reply_markup=keyboard)
            else:
                await bot.send_message(ch_id, caption, parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            await callback.message.answer(f"❌ {ch_id} ga xato: {e}")

    if callback.data == "post_ch_all":
        channels = await db.get_post_channels()
        for ch in channels:
            await send_to(ch["channel_id"])
        await callback.message.answer("✅ Barcha kanallarga yuborildi!")
    else:
        ch_id = callback.data.replace("post_ch_", "")
        await send_to(ch_id)
        await callback.message.answer(f"✅ {ch_id} ga yuborildi!")

    await state.clear()

async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.")

# =============================================
# 🚀 MAIN
# =============================================
async def main():
    await db.init()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Commands
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(fsm_done, Command("done"), AddEpisode.files)

    # FSM
    dp.message.register(fsm_anime_code, AddAnime.code)
    dp.message.register(fsm_anime_name, AddAnime.name)
    dp.message.register(fsm_anime_desc, AddAnime.desc)
    dp.message.register(fsm_anime_photo, AddAnime.photo)
    dp.message.register(fsm_episode_code, AddEpisode.code)
    dp.message.register(fsm_episode_file, AddEpisode.files)
    dp.message.register(fsm_edit_name, EditAnime.name)
    dp.message.register(fsm_edit_photo, EditAnime.photo)
    dp.message.register(fsm_edit_desc, EditAnime.desc)
    dp.message.register(fsm_edit_code, EditAnime.code)
    dp.message.register(fsm_sub_channel, AddSubChannel.waiting)
    dp.message.register(fsm_post_channel, AddPostChannel.waiting)
    dp.message.register(fsm_add_admin, AddAdminState.waiting)
    dp.message.register(fsm_update_setting, UpdateSetting.waiting)
    dp.message.register(fsm_post_code, PostAnime.code)

    # Callbacks
    dp.callback_query.register(cb_check_sub, F.data == "check_sub")
    dp.callback_query.register(cb_watch, F.data.startswith("watch_"))
    dp.callback_query.register(cb_admin, F.data.startswith("admin_") | F.data.startswith("setting_") | F.data.startswith("remove_admin_") | F.data.startswith("del_post_ch_"))
    dp.callback_query.register(cb_anime_manage, F.data.startswith("anime_"))
    dp.callback_query.register(cb_sub, F.data.startswith("sub_"))
    dp.callback_query.register(cb_post_channel, F.data.startswith("post_ch_"), PostAnime.channel)

    # Text messages
    dp.message.register(handle_text, F.text)

    print("🎌 Anime Bot (aiogram) ishga tushdi! ✅")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
