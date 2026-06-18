"""
🎌 ANIME BOT - To'liq versiya
Barcha funksiyalar bitta faylda

O'rnatish:
    pip install python-telegram-bot asyncpg

PostgreSQL bazasi yaratish:
    CREATE DATABASE anime_bot;

Sozlash:
    BOT_TOKEN, ADMIN_IDS, DB_CONFIG ni o'zgartiring
"""

import os
import logging
import asyncpg
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler,
    ConversationHandler
)

# =============================================
# ⚙️ SOZLAMALAR - BU YERNI O'ZGARTIRING
# =============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "your_bot_username")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "7164685036").split(",")]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:password@localhost/anime_bot")

DEFAULT_SETTINGS = {
    "welcome_message": "🎌 Xush kelibsiz! Anime kodini yuboring.",
    "anime_code_prompt": "🔢 Anime kodini yuboring",
    "not_found_message": "😔 Anime topilmadi",
    "subscribe_message": "📢 Quyidagi kanallarga obuna bo'ling",
    "check_button": "✅ Tekshirish"
}

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# =============================================
# 🗄️ MA'LUMOTLAR BAZASI
# =============================================
class Database:
    def __init__(self):
        self.pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(dsn=DATABASE_URL, ssl="require" if "render.com" in DATABASE_URL else None)
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

    # --- USERS ---
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

    async def get_all_user_ids(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [r["user_id"] for r in rows]

    # --- ADMINS ---
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

    async def is_admin(self, user_id):
        if user_id in ADMIN_IDS:
            return True
        async with self.pool.acquire() as conn:
            result = await conn.fetchval("SELECT admin_id FROM admins WHERE admin_id=$1", user_id)
            return result is not None

    # --- ANIMES ---
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

    async def update_anime_name(self, code, new_name):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET name=$1 WHERE code=$2", new_name, code)

    async def update_anime_photo(self, code, photo_id):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET photo_id=$1 WHERE code=$2", photo_id, code)

    async def update_anime_description(self, code, description):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET description=$1 WHERE code=$2", description, code)

    async def update_anime_code(self, old_code, new_code):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET code=$1 WHERE code=$2", new_code, old_code)

    async def delete_anime(self, code):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM animes WHERE code=$1", code)

    async def increment_views(self, code):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE animes SET views=views+1 WHERE code=$1", code)

    # --- EPISODES ---
    async def add_episode(self, anime_code, episode_number, file_id, file_type="video"):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO episodes (anime_code, episode_number, file_id, file_type)
                VALUES ($1, $2, $3, $4)
            """, anime_code, episode_number, file_id, file_type)

    async def get_episodes(self, anime_code):
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM episodes WHERE anime_code=$1 ORDER BY episode_number", anime_code
            )

    async def get_episode(self, anime_code, episode_number):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM episodes WHERE anime_code=$1 AND episode_number=$2",
                anime_code, episode_number
            )

    # --- SUBSCRIPTION CHANNELS ---
    async def add_sub_channel(self, channel_id, channel_name):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO subscription_channels (channel_id, channel_name)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """, channel_id, channel_name)

    async def remove_sub_channel(self, channel_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM subscription_channels WHERE channel_id=$1", channel_id)

    async def get_sub_channels(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM subscription_channels")

    # --- POST CHANNELS ---
    async def add_post_channel(self, channel_id, channel_name):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO post_channels (channel_id, channel_name)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """, channel_id, channel_name)

    async def remove_post_channel(self, channel_id):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM post_channels WHERE channel_id=$1", channel_id)

    async def get_post_channels(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM post_channels")

    # --- BOT SETTINGS ---
    async def get_setting(self, key):
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT value FROM bot_settings WHERE key=$1", key)

    async def set_setting(self, key, value):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bot_settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value=$2
            """, key, value)

db = Database()

# =============================================
# 🔑 CONVERSATION STATES
# =============================================
(
    ADD_ANIME_CODE, ADD_ANIME_NAME, ADD_ANIME_DESC, ADD_ANIME_PHOTO,
    ADD_EPISODE_CODE, ADD_EPISODE_FILES,
    EDIT_NAME, EDIT_PHOTO, EDIT_DESC, EDIT_CODE,
    ADD_SUB_CHANNEL, ADD_POST_CHANNEL,
    ADD_ADMIN_STATE, REMOVE_ADMIN_STATE,
    SET_WELCOME, SET_NOT_FOUND, SET_SUB_MSG,
    POST_SELECT_ANIME, POST_SELECT_CHANNEL,
) = range(19)

# =============================================
# 🛡️ ADMIN TEKSHIRISH
# =============================================
async def admin_required(update: Update) -> bool:
    user_id = update.effective_user.id
    if not await db.is_admin(user_id):
        if update.message:
            await update.message.reply_text("❌ Siz admin emassiz!")
        elif update.callback_query:
            await update.callback_query.answer("❌ Siz admin emassiz!", show_alert=True)
        return False
    return True

# =============================================
# 👥 FOYDALANUVCHI FUNKSIYALARI
# =============================================
async def check_user_subscription(bot, user_id):
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username, user.full_name)

    # Deep link orqali anime kodi kelsa
    if context.args:
        code = context.args[0].upper()
        anime = await db.get_anime(code)
        if anime:
            await send_anime_info(update.message, context, anime)
            return

    welcome = await db.get_setting("welcome_message")
    await update.message.reply_text(welcome)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    await db.add_user(user.id, user.username, user.full_name)

    # Obuna tekshirish
    not_subscribed = await check_user_subscription(context.bot, user.id)
    if not_subscribed:
        await send_subscription_message(update.message, not_subscribed)
        return

    # Kod yoki nom bo'yicha qidirish
    anime = await db.get_anime(text.upper())
    if anime:
        await send_anime_info(update.message, context, anime)
        return

    results = await db.get_anime_by_name(text)
    if results:
        buttons = [
            [InlineKeyboardButton(f"🎌 {a['name']} [{a['code']}]", callback_data=f"watch_{a['code']}")]
            for a in results[:8]
        ]
        await update.message.reply_text(
            f"🔎 '{text}' bo'yicha natijalar:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        not_found = await db.get_setting("not_found_message")
        await update.message.reply_text(not_found)

async def send_subscription_message(message, not_subscribed):
    sub_msg = await db.get_setting("subscribe_message")
    check_btn = await db.get_setting("check_button")
    buttons = [
        [InlineKeyboardButton(
            f"📢 {ch['channel_name'] or ch['channel_id']}",
            url=f"https://t.me/{ch['channel_id'].replace('@', '')}"
        )]
        for ch in not_subscribed
    ]
    buttons.append([InlineKeyboardButton(check_btn, callback_data="check_sub")])
    await message.reply_text(sub_msg, reply_markup=InlineKeyboardMarkup(buttons))

async def send_anime_info(message, context, anime):
    episodes = await db.get_episodes(anime["code"])
    await db.increment_views(anime["code"])

    caption = f"🎌 *{anime['name']}*\n"
    if anime["description"]:
        caption += f"\n📝 {anime['description']}\n"
    caption += f"\n🔢 Kod: `{anime['code']}`"
    caption += f"\n🎬 Qismlar soni: {len(episodes)}"
    caption += f"\n👁 Ko'rishlar: {anime['views'] + 1}"

    buttons = []
    if episodes:
        row = []
        for ep in episodes:
            row.append(InlineKeyboardButton(
                f"▶️ {ep['episode_number']}-qism",
                callback_data=f"watch_{anime['code']}_{ep['episode_number']}"
            ))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None

    if anime["photo_id"]:
        await message.reply_photo(
            photo=anime["photo_id"],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await message.reply_text(caption, parse_mode="Markdown", reply_markup=keyboard)

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    not_subscribed = await check_user_subscription(context.bot, query.from_user.id)
    if not_subscribed:
        await query.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)
    else:
        await query.answer("✅ Rahmat! Endi foydalanishingiz mumkin.", show_alert=True)
        await query.message.delete()

async def watch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    not_subscribed = await check_user_subscription(context.bot, query.from_user.id)
    if not_subscribed:
        sub_msg = await db.get_setting("subscribe_message")
        check_btn = await db.get_setting("check_button")
        buttons = [
            [InlineKeyboardButton(f"📢 {ch['channel_name'] or ch['channel_id']}",
             url=f"https://t.me/{ch['channel_id'].replace('@', '')}")]
            for ch in not_subscribed
        ]
        buttons.append([InlineKeyboardButton(check_btn, callback_data="check_sub")])
        await query.message.reply_text(sub_msg, reply_markup=InlineKeyboardMarkup(buttons))
        return

    parts = query.data.replace("watch_", "").split("_")
    anime_code = parts[0]
    anime = await db.get_anime(anime_code)
    if not anime:
        await query.message.reply_text("❌ Anime topilmadi.")
        return

    if len(parts) == 1:
        episodes = await db.get_episodes(anime_code)
        if not episodes:
            await query.message.reply_text("😔 Hozircha qism yo'q.")
            return
        buttons = []
        row = []
        for ep in episodes:
            row.append(InlineKeyboardButton(
                f"▶️ {ep['episode_number']}-qism",
                callback_data=f"watch_{anime_code}_{ep['episode_number']}"
            ))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        await query.message.reply_text(
            f"🎌 *{anime['name']}* — Qismni tanlang:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        ep_num = int(parts[1])
        episode = await db.get_episode(anime_code, ep_num)
        if not episode:
            await query.message.reply_text("❌ Qism topilmadi.")
            return

        caption = f"🎌 *{anime['name']}* — {ep_num}-qism"
        next_ep = await db.get_episode(anime_code, ep_num + 1)
        buttons = []
        if next_ep:
            buttons.append([InlineKeyboardButton(
                f"▶️ {ep_num + 1}-qism →",
                callback_data=f"watch_{anime_code}_{ep_num + 1}"
            )])
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None

        if episode["file_type"] == "video":
            await query.message.reply_video(
                video=episode["file_id"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await query.message.reply_document(
                document=episode["file_id"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )

# =============================================
# 🎛️ ADMIN PANEL
# =============================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_required(update):
        return
    await show_admin_panel(update.message)

async def show_admin_panel(message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Anime qo'shish", callback_data="admin_add_anime")],
        [InlineKeyboardButton("🗂 Animelar ro'yxati", callback_data="admin_anime_list")],
        [InlineKeyboardButton("➕ Qism qo'shish", callback_data="admin_add_episode")],
        [InlineKeyboardButton("🔒 Majburiy obuna", callback_data="admin_subscription")],
        [InlineKeyboardButton("📤 Kanalga post yuborish", callback_data="admin_post")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("🔊 Bot sozlari", callback_data="admin_settings")],
        [InlineKeyboardButton("🏧 Adminlar boshqaruvi", callback_data="admin_admins")],
    ])
    await message.reply_text(
        "🎛 *Boshqaruv paneli*\n\nBo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await admin_required(update):
        return
    data = query.data

    if data == "admin_back":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Anime qo'shish", callback_data="admin_add_anime")],
            [InlineKeyboardButton("🗂 Animelar ro'yxati", callback_data="admin_anime_list")],
            [InlineKeyboardButton("➕ Qism qo'shish", callback_data="admin_add_episode")],
            [InlineKeyboardButton("🔒 Majburiy obuna", callback_data="admin_subscription")],
            [InlineKeyboardButton("📤 Kanalga post yuborish", callback_data="admin_post")],
            [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton("🔊 Bot sozlari", callback_data="admin_settings")],
            [InlineKeyboardButton("🏧 Adminlar boshqaruvi", callback_data="admin_admins")],
        ])
        await query.message.edit_text(
            "🎛 *Boshqaruv paneli*\n\nBo'limni tanlang:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    elif data == "admin_add_anime":
        await query.message.reply_text("🔢 Anime kodini kiriting (masalan: NRT):")
        return ADD_ANIME_CODE

    elif data == "admin_anime_list":
        animes = await db.get_all_animes()
        if not animes:
            await query.message.edit_text("📭 Hozircha anime yo'q.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]]))
            return
        buttons = [
            [InlineKeyboardButton(f"🎌 {a['name']} [{a['code']}]", callback_data=f"anime_manage_{a['code']}")]
            for a in animes
        ]
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
        await query.message.edit_text("🗂 *Animelar ro'yxati:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "admin_add_episode":
        await query.message.reply_text("🔢 Qism qo'shish uchun anime kodini kiriting:")
        return ADD_EPISODE_CODE

    elif data == "admin_subscription":
        await show_sub_panel(query)

    elif data == "admin_post":
        await query.message.reply_text("🔢 Post yuborish uchun anime kodini kiriting:")
        return POST_SELECT_ANIME

    elif data == "admin_stats":
        total_users = await db.get_users_count()
        new_1 = await db.get_new_users_count(1)
        new_3 = await db.get_new_users_count(3)
        new_7 = await db.get_new_users_count(7)
        total_animes = await db.get_animes_count()
        text = (
            "📊 *Statistika*\n\n"
            f"👤 *Obunachilar:*\n"
            f"• Jami: {total_users} ta\n"
            f"• 1 kun ichida: +{new_1} ta\n"
            f"• 3 kun ichida: +{new_3} ta\n"
            f"• 7 kun ichida: +{new_7} ta\n\n"
            f"🎞 *Animelar:* {total_animes} ta"
        )
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]]))

    elif data == "admin_settings":
        await show_settings_panel(query)

    elif data == "admin_admins":
        await show_admins_panel(query)

    elif data == "admin_add_admin":
        await query.message.reply_text("🏧 Yangi admin Telegram ID sini kiriting:")
        return ADD_ADMIN_STATE

    elif data == "admin_remove_admin":
        admins = await db.get_admins()
        if not admins:
            await query.message.reply_text("Admin yo'q.")
            return
        buttons = [[InlineKeyboardButton(f"❌ {a}", callback_data=f"remove_admin_{a}")] for a in admins]
        await query.message.reply_text("O'chirish uchun admini tanlang:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("remove_admin_"):
        admin_id = int(data.replace("remove_admin_", ""))
        await db.remove_admin(admin_id)
        await query.message.edit_text(f"✅ Admin {admin_id} o'chirildi.")

    elif data.startswith("setting_"):
        setting = data.replace("setting_", "")
        if setting == "add_post_ch":
            await query.message.reply_text("📤 Post kanalini kiriting:\n@kanal_username Kanal nomi")
            return ADD_POST_CHANNEL
        elif setting == "remove_post_ch":
            channels = await db.get_post_channels()
            if not channels:
                await query.message.reply_text("Kanal yo'q.")
                return
            buttons = [[InlineKeyboardButton(f"❌ {ch['channel_name'] or ch['channel_id']}", callback_data=f"del_post_ch_{ch['channel_id']}")] for ch in channels]
            await query.message.reply_text("O'chirish:", reply_markup=InlineKeyboardMarkup(buttons))
        context.user_data["setting_key"] = setting
        prompts = {
            "welcome": "👋 Yangi xush kelibsiz xabarini kiriting:",
            "not_found": "😔 Topilmadi xabarini kiriting:",
            "sub_msg": "📢 Obuna xabarini kiriting:",
        }
        if setting in prompts:
            await query.message.reply_text(prompts[setting])
            return SET_WELCOME

    elif data.startswith("del_post_ch_"):
        ch_id = data.replace("del_post_ch_", "")
        await db.remove_post_channel(ch_id)
        await query.message.edit_text(f"✅ {ch_id} o'chirildi.")

# =============================================
# ANIME MANAGE CALLBACK
# =============================================
async def anime_manage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await admin_required(update):
        return
    data = query.data

    if data.startswith("anime_manage_"):
        code = data.replace("anime_manage_", "")
        anime = await db.get_anime(code)
        if not anime:
            await query.message.reply_text("❌ Topilmadi.")
            return
        context.user_data["edit_anime_code"] = code
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✒ Nomini o'zgartirish", callback_data=f"anime_edit_name_{code}")],
            [InlineKeyboardButton("🏞 Rasmini o'zgartirish", callback_data=f"anime_edit_photo_{code}")],
            [InlineKeyboardButton("🎞 Tavsifini o'zgartirish", callback_data=f"anime_edit_desc_{code}")],
            [InlineKeyboardButton("🔢 Kodini o'zgartirish", callback_data=f"anime_edit_code_{code}")],
            [InlineKeyboardButton("🗑 Animeni o'chirish", callback_data=f"anime_delete_{code}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_anime_list")],
        ])
        episodes = await db.get_episodes(code)
        await query.message.edit_text(
            f"🎌 *{anime['name']}*\n"
            f"Kod: `{code}`\n"
            f"Qismlar: {len(episodes)}\n"
            f"Ko'rishlar: {anime['views']}\n\n"
            f"Nimani o'zgartirmoqchisiz?",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

    elif data.startswith("anime_edit_name_"):
        context.user_data["edit_anime_code"] = data.replace("anime_edit_name_", "")
        await query.message.reply_text("✒ Yangi nomini kiriting:")
        return EDIT_NAME

    elif data.startswith("anime_edit_photo_"):
        context.user_data["edit_anime_code"] = data.replace("anime_edit_photo_", "")
        await query.message.reply_text("🏞 Yangi rasmini yuboring:")
        return EDIT_PHOTO

    elif data.startswith("anime_edit_desc_"):
        context.user_data["edit_anime_code"] = data.replace("anime_edit_desc_", "")
        await query.message.reply_text("🎞 Yangi tavsifini kiriting:")
        return EDIT_DESC

    elif data.startswith("anime_edit_code_"):
        context.user_data["edit_anime_code"] = data.replace("anime_edit_code_", "")
        await query.message.reply_text("🔢 Yangi kodini kiriting:")
        return EDIT_CODE

    elif data.startswith("anime_delete_"):
        code = data.replace("anime_delete_", "")
        await db.delete_anime(code)
        await query.message.edit_text(
            f"🗑 `{code}` o'chirildi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="admin_anime_list")]])
        )

    elif data == "admin_anime_list":
        animes = await db.get_all_animes()
        if not animes:
            await query.message.edit_text("📭 Anime yo'q.")
            return
        buttons = [
            [InlineKeyboardButton(f"🎌 {a['name']} [{a['code']}]", callback_data=f"anime_manage_{a['code']}")]
            for a in animes
        ]
        buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
        await query.message.edit_text("🗂 *Animelar:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

# =============================================
# SUBSCRIPTION PANEL
# =============================================
async def show_sub_panel(query):
    channels = await db.get_sub_channels()
    text = "🔒 *Majburiy obuna kanallari:*\n\n"
    if channels:
        for ch in channels:
            text += f"• {ch['channel_name'] or ch['channel_id']} (`{ch['channel_id']}`)\n"
    else:
        text += "Hozircha kanal yo'q.\n"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="sub_add")],
        [InlineKeyboardButton("❌ Kanal o'chirish", callback_data="sub_remove")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")],
    ])
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await admin_required(update):
        return
    data = query.data

    if data == "sub_add":
        await query.message.reply_text(
            "Kanal ID va nomini kiriting:\n"
            "Format: @kanal_username Kanal nomi"
        )
        return ADD_SUB_CHANNEL

    elif data == "sub_remove":
        channels = await db.get_sub_channels()
        if not channels:
            await query.message.reply_text("Kanal yo'q.")
            return
        buttons = [[InlineKeyboardButton(f"❌ {ch['channel_name'] or ch['channel_id']}", callback_data=f"sub_del_{ch['channel_id']}")] for ch in channels]
        await query.message.reply_text("O'chirish:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("sub_del_"):
        ch_id = data.replace("sub_del_", "")
        await db.remove_sub_channel(ch_id)
        await query.message.edit_text(f"✅ `{ch_id}` o'chirildi.", parse_mode="Markdown")

# =============================================
# SETTINGS PANEL
# =============================================
async def show_settings_panel(query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👋 Xush kelibsiz xabari", callback_data="setting_welcome")],
        [InlineKeyboardButton("😔 Topilmadi xabari", callback_data="setting_not_found")],
        [InlineKeyboardButton("📢 Obuna xabari", callback_data="setting_sub_msg")],
        [InlineKeyboardButton("➕ Post kanal qo'shish", callback_data="setting_add_post_ch")],
        [InlineKeyboardButton("❌ Post kanal o'chirish", callback_data="setting_remove_post_ch")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")],
    ])
    await query.message.edit_text("🔊 *Bot sozlari:*", parse_mode="Markdown", reply_markup=keyboard)

async def show_admins_panel(query):
    admins = await db.get_admins()
    text = "🏧 *Adminlar:*\n\n"
    for a in admins:
        text += f"• `{a}`\n"
    if not admins:
        text += "Qo'shimcha admin yo'q.\n"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Admin qo'shish", callback_data="admin_add_admin")],
        [InlineKeyboardButton("❌ Admin o'chirish", callback_data="admin_remove_admin")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")],
    ])
    await query.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

# =============================================
# 🔄 CONVERSATION HANDLERS - STEP FUNCTIONS
# =============================================

# --- Anime qo'shish ---
async def add_anime_code(update, context):
    code = update.message.text.strip().upper()
    if await db.get_anime(code):
        await update.message.reply_text(f"❌ '{code}' kodi mavjud. Boshqa kod kiriting:")
        return ADD_ANIME_CODE
    context.user_data["new_anime_code"] = code
    await update.message.reply_text("✒ Anime nomini kiriting:")
    return ADD_ANIME_NAME

async def add_anime_name(update, context):
    context.user_data["new_anime_name"] = update.message.text.strip()
    await update.message.reply_text("🎞 Tavsifini kiriting (o'tkazish: /skip):")
    return ADD_ANIME_DESC

async def add_anime_desc(update, context):
    context.user_data["new_anime_desc"] = None if update.message.text.strip() == "/skip" else update.message.text.strip()
    await update.message.reply_text("🏞 Rasmini yuboring (o'tkazish: /skip):")
    return ADD_ANIME_PHOTO

async def add_anime_photo(update, context):
    if update.message.text and update.message.text.strip() == "/skip":
        photo_id = None
    elif update.message.photo:
        photo_id = update.message.photo[-1].file_id
    else:
        await update.message.reply_text("Rasm yuboring yoki /skip:")
        return ADD_ANIME_PHOTO
    code = context.user_data["new_anime_code"]
    name = context.user_data["new_anime_name"]
    desc = context.user_data.get("new_anime_desc")
    await db.add_anime(code, name, desc, photo_id)
    await update.message.reply_text(f"✅ *{name}* qo'shildi!\nKod: `{code}`", parse_mode="Markdown")
    return ConversationHandler.END

# --- Qism qo'shish ---
async def add_episode_code(update, context):
    code = update.message.text.strip().upper()
    anime = await db.get_anime(code)
    if not anime:
        await update.message.reply_text("❌ Anime topilmadi. Kodni qayta kiriting:")
        return ADD_EPISODE_CODE
    context.user_data["episode_anime_code"] = code
    episodes = await db.get_episodes(code)
    next_num = len(episodes) + 1
    context.user_data["episode_number"] = next_num
    await update.message.reply_text(
        f"🎬 *{anime['name']}*\n\n📤 {next_num}-qismni yuboring.\nTugatish: /done",
        parse_mode="Markdown"
    )
    return ADD_EPISODE_FILES

async def add_episode_file(update, context):
    code = context.user_data["episode_anime_code"]
    ep_num = context.user_data["episode_number"]
    if update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
    else:
        await update.message.reply_text("Video yoki fayl yuboring:")
        return ADD_EPISODE_FILES
    await db.add_episode(code, ep_num, file_id, file_type)
    context.user_data["episode_number"] = ep_num + 1
    await update.message.reply_text(f"✅ {ep_num}-qism saqlandi!\n📤 {ep_num + 1}-qismni yuboring yoki /done.")
    return ADD_EPISODE_FILES

async def done_episodes(update, context):
    code = context.user_data.get("episode_anime_code", "")
    total = context.user_data.get("episode_number", 1) - 1
    await update.message.reply_text(f"✅ Jami {total} ta qism saqlandi! Kod: `{code}`", parse_mode="Markdown")
    return ConversationHandler.END

# --- Anime tahrirlash ---
async def edit_name(update, context):
    await db.update_anime_name(context.user_data["edit_anime_code"], update.message.text.strip())
    await update.message.reply_text("✅ Nom yangilandi!")
    return ConversationHandler.END

async def edit_photo(update, context):
    if not update.message.photo:
        await update.message.reply_text("Rasm yuboring:")
        return EDIT_PHOTO
    await db.update_anime_photo(context.user_data["edit_anime_code"], update.message.photo[-1].file_id)
    await update.message.reply_text("✅ Rasm yangilandi!")
    return ConversationHandler.END

async def edit_desc(update, context):
    await db.update_anime_description(context.user_data["edit_anime_code"], update.message.text.strip())
    await update.message.reply_text("✅ Tavsif yangilandi!")
    return ConversationHandler.END

async def edit_code(update, context):
    old_code = context.user_data["edit_anime_code"]
    new_code = update.message.text.strip().upper()
    await db.update_anime_code(old_code, new_code)
    await update.message.reply_text(f"✅ Kod `{old_code}` → `{new_code}`", parse_mode="Markdown")
    return ConversationHandler.END

# --- Obuna kanal qo'shish ---
async def add_sub_channel(update, context):
    parts = update.message.text.strip().split(" ", 1)
    ch_id = parts[0]
    ch_name = parts[1] if len(parts) > 1 else ch_id
    await db.add_sub_channel(ch_id, ch_name)
    await update.message.reply_text(f"✅ {ch_name} (`{ch_id}`) qo'shildi!", parse_mode="Markdown")
    return ConversationHandler.END

# --- Post kanal qo'shish ---
async def add_post_channel(update, context):
    parts = update.message.text.strip().split(" ", 1)
    ch_id = parts[0]
    ch_name = parts[1] if len(parts) > 1 else ch_id
    await db.add_post_channel(ch_id, ch_name)
    await update.message.reply_text(f"✅ Post kanali {ch_name} qo'shildi!", parse_mode="Markdown")
    return ConversationHandler.END

# --- Admin qo'shish ---
async def add_admin_state(update, context):
    try:
        admin_id = int(update.message.text.strip())
        await db.add_admin(admin_id)
        await update.message.reply_text(f"✅ Admin {admin_id} qo'shildi!")
    except:
        await update.message.reply_text("❌ Noto'g'ri ID. Raqam kiriting:")
        return ADD_ADMIN_STATE
    return ConversationHandler.END

# --- Sozlama o'zgartirish ---
async def update_setting(update, context):
    setting = context.user_data.get("setting_key")
    mapping = {
        "welcome": "welcome_message",
        "not_found": "not_found_message",
        "sub_msg": "subscribe_message",
    }
    key = mapping.get(setting)
    if key:
        await db.set_setting(key, update.message.text.strip())
        await update.message.reply_text("✅ Sozlama yangilandi!")
    return ConversationHandler.END

# --- Post yuborish ---
async def post_select_anime(update, context):
    code = update.message.text.strip().upper()
    anime = await db.get_anime(code)
    if not anime:
        await update.message.reply_text("❌ Topilmadi. Kodni qayta kiriting:")
        return POST_SELECT_ANIME
    context.user_data["post_anime_code"] = code
    channels = await db.get_post_channels()
    if not channels:
        await update.message.reply_text("❌ Post kanali sozlanmagan. /admin > Bot sozlari")
        return ConversationHandler.END
    buttons = [
        [InlineKeyboardButton(f"📢 {ch['channel_name'] or ch['channel_id']}", callback_data=f"post_ch_{ch['channel_id']}")]
        for ch in channels
    ]
    buttons.append([InlineKeyboardButton("📢 Barcha kanallarga", callback_data="post_ch_all")])
    await update.message.reply_text("Qaysi kanalga?", reply_markup=InlineKeyboardMarkup(buttons))
    return POST_SELECT_CHANNEL

async def post_channel_callback(update, context):
    query = update.callback_query
    await query.answer()
    code = context.user_data.get("post_anime_code")
    anime = await db.get_anime(code)
    episodes = await db.get_episodes(code)

    caption = f"🎌 *{anime['name']}*\n"
    if anime["description"]:
        caption += f"\n📝 {anime['description']}\n"
    caption += f"\n🔢 Kod: `{anime['code']}`\n🎬 Qismlar: {len(episodes)}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("▶️ Tomosha qilish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
    ]])

    async def send_to(ch_id):
        try:
            if anime["photo_id"]:
                await context.bot.send_photo(ch_id, anime["photo_id"], caption=caption, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await context.bot.send_message(ch_id, caption, parse_mode="Markdown", reply_markup=keyboard)
            return True
        except Exception as e:
            await query.message.reply_text(f"❌ {ch_id} ga xato: {e}")
            return False

    if query.data == "post_ch_all":
        channels = await db.get_post_channels()
        for ch in channels:
            await send_to(ch["channel_id"])
        await query.message.reply_text("✅ Barcha kanallarga yuborildi!")
    else:
        ch_id = query.data.replace("post_ch_", "")
        if await send_to(ch_id):
            await query.message.reply_text(f"✅ {ch_id} ga yuborildi!")

    return ConversationHandler.END

# --- Cancel ---
async def cancel(update, context):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

# =============================================
# 🚀 ASOSIY FUNKSIYA
# =============================================
async def post_init(application):
    await db.init()

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Asosiy buyruqlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", lambda u, c: admin_callback(u, c)))

    # Anime qo'shish conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_add_anime$")],
        states={
            ADD_ANIME_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_anime_code)],
            ADD_ANIME_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_anime_name)],
            ADD_ANIME_DESC: [MessageHandler(filters.TEXT, add_anime_desc)],
            ADD_ANIME_PHOTO: [
                MessageHandler(filters.PHOTO, add_anime_photo),
                MessageHandler(filters.TEXT, add_anime_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Qism qo'shish conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_add_episode$")],
        states={
            ADD_EPISODE_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_episode_code)],
            ADD_EPISODE_FILES: [
                MessageHandler(filters.VIDEO | filters.Document.ALL, add_episode_file),
                CommandHandler("done", done_episodes),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Anime tahrirlash conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(anime_manage_callback, pattern="^anime_edit_")],
        states={
            EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_name)],
            EDIT_PHOTO: [MessageHandler(filters.PHOTO, edit_photo)],
            EDIT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_desc)],
            EDIT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Obuna kanal conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(subscription_callback, pattern="^sub_add$")],
        states={
            ADD_SUB_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sub_channel)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Admin qo'shish conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_add_admin$")],
        states={
            ADD_ADMIN_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_state)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Sozlama o'zgartirish conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^setting_(welcome|not_found|sub_msg)$")],
        states={
            SET_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_setting)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Post kanal qo'shish conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^setting_add_post_ch$")],
        states={
            ADD_POST_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_post_channel)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Post yuborish conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback, pattern="^admin_post$")],
        states={
            POST_SELECT_ANIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_select_anime)],
            POST_SELECT_CHANNEL: [CallbackQueryHandler(post_channel_callback, pattern="^post_ch_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(anime_manage_callback, pattern="^anime_"))
    app.add_handler(CallbackQueryHandler(subscription_callback, pattern="^sub_"))
    app.add_handler(CallbackQueryHandler(watch_callback, pattern="^watch_"))
    app.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_sub$"))

    # Xabar handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🎌 Anime Bot ishga tushdi! ✅")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
