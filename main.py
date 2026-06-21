import os
import asyncio
import asyncpg
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)

# =====================
# SOZLAMALAR
# =====================
TOKEN = os.getenv("BOT_TOKEN", "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI")
BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot")
ADMIN_IDS = [
    int(os.getenv("ADMIN_ID_1", "7164685036")),
    int(os.getenv("ADMIN_ID_2", "7164685036")),
    int(os.getenv("ADMIN_ID_3", "7164685036")),
]
DB_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
pool = None

# =====================
# DATABASE
# =====================
async def db_init():
    global pool
    pool = await asyncpg.create_pool(dsn=DB_URL, ssl="require")
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            joined_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS animes (
            code TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            photo_id TEXT,
            views INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS episodes (
            id SERIAL PRIMARY KEY,
            anime_code TEXT REFERENCES animes(code) ON DELETE CASCADE,
            ep_num INT,
            file_id TEXT,
            file_type TEXT DEFAULT 'video'
        );
        CREATE TABLE IF NOT EXISTS sub_channels (
            channel_id TEXT PRIMARY KEY,
            channel_name TEXT
        );
        CREATE TABLE IF NOT EXISTS post_channels (
            channel_id TEXT PRIMARY KEY,
            channel_name TEXT
        );
        CREATE TABLE IF NOT EXISTS downloads (
            id SERIAL PRIMARY KEY,
            anime_code TEXT,
            ep_num INT,
            user_id BIGINT,
            dl_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    settings = {
        "welcome": "🎌 Xush kelibsiz Miraziz Anime!\n\nAnime kodini yoki nomini kiriting:",
        "not_found": "❌ Anime topilmadi! Boshqa kodni kiriting iltimos.",
        "sub_msg": "📢 Quyidagi kanallarga obuna bo'ling:",
        "contact": "👤 Admin bilan bog'lanish: @admin",
        "search_prompt": "🔎 Anime kodini yoki nomini kiriting:",
    }
    for k, v in settings.items():
        await pool.execute("INSERT INTO bot_settings(key,value) VALUES($1,$2) ON CONFLICT DO NOTHING", k, v)

async def get_setting(key):
    row = await pool.fetchrow("SELECT value FROM bot_settings WHERE key=$1", key)
    return row["value"] if row else ""

# =====================
# STATES
# =====================
class AddAnime(StatesGroup):
    name = State()
    code = State()
    desc = State()
    photo = State()
    episodes = State()

class AddEpisodes(StatesGroup):
    code = State()
    files = State()

class EditField(StatesGroup):
    value = State()

class AddSubChan(StatesGroup):
    waiting = State()

class AddPostChan(StatesGroup):
    waiting = State()

class PostAnime(StatesGroup):
    code = State()

class SetSetting(StatesGroup):
    value = State()

class SearchAnime(StatesGroup):
    waiting = State()

# =====================
# HELPERS
# =====================
async def is_admin(user_id):
    return user_id in ADMIN_IDS

async def check_sub(user_id):
    channels = await pool.fetch("SELECT * FROM sub_channels")
    not_sub = []
    for ch in channels:
        try:
            m = await bot.get_chat_member(ch["channel_id"], user_id)
            if m.status in ["left", "kicked"]:
                not_sub.append(ch)
        except:
            not_sub.append(ch)
    return not_sub

def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔎 Anime qidirish")],
        [KeyboardButton(text="📋 Barcha animelar"), KeyboardButton(text="⭐ Admin")],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Anime qo'shish"), KeyboardButton(text="🗂 Animelar ro'yxati")],
        [KeyboardButton(text="➕ Qism qo'shish"), KeyboardButton(text="📤 Kanalga post")],
        [KeyboardButton(text="🔒 Obuna kanali"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="🔊 Bot sozlari"), KeyboardButton(text="🔙 Orqaga")],
    ], resize_keyboard=True)

async def send_anime_info(msg, anime):
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1 ORDER BY ep_num", anime["code"])
    await pool.execute("UPDATE animes SET views=views+1 WHERE code=$1", anime["code"])
    cap = f"🎌 <b>{anime['name']}</b>\n"
    if anime["description"]:
        cap += f"📝 {anime['description']}\n"
    cap += f"\n🔢 Kod: <code>{anime['code']}</code>\n🎬 Qismlar: {len(eps)}\n👁 Ko'rishlar: {anime['views']+1}"
    btns = []
    row = []
    for ep in eps:
        row.append(InlineKeyboardButton(text=f"▶️ {ep['ep_num']}-qism", callback_data=f"ep_{anime['code']}_{ep['ep_num']}"))
        if len(row) == 3:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    kb = InlineKeyboardMarkup(inline_keyboard=btns) if btns else None
    if anime["photo_id"]:
        await msg.answer_photo(anime["photo_id"], caption=cap, parse_mode="HTML", reply_markup=kb)
    else:
        await msg.answer(cap, parse_mode="HTML", reply_markup=kb)

# =====================
# START
# =====================
@dp.message(Command("start"))
async def start(msg: Message):
    await pool.execute(
        "INSERT INTO users(user_id, username) VALUES($1,$2) ON CONFLICT DO NOTHING",
        msg.from_user.id, msg.from_user.username
    )
    args = msg.text.split()
    if len(args) > 1:
        anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", args[1].upper())
        if anime:
            await send_anime_info(msg, anime)
            return
    welcome = await get_setting("welcome")
    await msg.answer(welcome, reply_markup=main_kb())

@dp.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Bekor qilindi.", reply_markup=admin_kb() if await is_admin(msg.from_user.id) else main_kb())

@dp.message(Command("done"), AddEpisodes.files)
async def done_ep(msg: Message, state: FSMContext):
    d = await state.get_data()
    total = d.get("ep_num", 1) - 1
    await msg.answer(f"✅ Jami {total} ta qism saqlandi!\nKod: <code>{d.get('code')}</code>", parse_mode="HTML", reply_markup=admin_kb())
    await state.clear()

# =====================
# ADMIN PANEL
# =====================
@dp.message(F.text == "⭐ Admin")
async def admin_contact(msg: Message):
    contact = await get_setting("contact")
    await msg.answer(f"⭐ <b>Admin bilan bog'lanish:</b>\n\n{contact}", parse_mode="HTML")

@dp.message(Command("admin"))
async def admin_panel(msg: Message):
    if not await is_admin(msg.from_user.id):
        return await msg.answer("❌ Siz admin emassiz!")
    await msg.answer("🎛 <b>Boshqaruv paneli</b>", parse_mode="HTML", reply_markup=admin_kb())

@dp.message(F.text == "🔙 Orqaga")
async def back_main(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("🏠 Asosiy menyu", reply_markup=main_kb())

# =====================
# ANIME QO'SHISH
# =====================
@dp.message(F.text == "➕ Anime qo'shish")
async def add_anime_start(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
    await msg.answer("✍️ Anime nomini yozing:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddAnime.name)

@dp.message(AddAnime.name)
async def add_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("🔢 Anime kodini yozing (masalan: NRT, AOT):")
    await state.set_state(AddAnime.code)

@dp.message(AddAnime.code)
async def add_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    if await pool.fetchrow("SELECT code FROM animes WHERE code=$1", code):
        return await msg.answer("❌ Bu kod mavjud! Boshqa kod kiriting:")
    await state.update_data(code=code)
    await msg.answer("🎞 Tavsif yozing (/skip o'tkazish uchun):")
    await state.set_state(AddAnime.desc)

@dp.message(AddAnime.desc)
async def add_desc(msg: Message, state: FSMContext):
    await state.update_data(desc=None if msg.text.strip() == "/skip" else msg.text.strip())
    await msg.answer("🌄 Anime rasmini yuboring (/skip o'tkazish):")
    await state.set_state(AddAnime.photo)

@dp.message(AddAnime.photo)
async def add_photo(msg: Message, state: FSMContext):
    photo_id = None
    if msg.photo:
        photo_id = msg.photo[-1].file_id
    elif not msg.text or msg.text.strip() != "/skip":
        return await msg.answer("Rasm yuboring yoki /skip:")
    d = await state.get_data()
    await pool.execute(
        "INSERT INTO animes(code,name,description,photo_id) VALUES($1,$2,$3,$4)",
        d["code"], d["name"], d.get("desc"), photo_id
    )
    await state.update_data(ep_num=1)
    await msg.answer(
        f"✅ <b>{d['name']}</b> qo'shildi!\n\n"
        f"📤 Endi 1-qismni yuboring (video yoki fayl).\n"
        f"Tugatish: /done",
        parse_mode="HTML"
    )
    await state.set_state(AddAnime.episodes)

@dp.message(AddAnime.episodes, F.video | F.document)
async def add_anime_episode(msg: Message, state: FSMContext):
    d = await state.get_data()
    ep_num = d.get("ep_num", 1)
    code = d["code"]
    if msg.video:
        file_id, ftype = msg.video.file_id, "video"
    else:
        file_id, ftype = msg.document.file_id, "document"
    await pool.execute(
        "INSERT INTO episodes(anime_code,ep_num,file_id,file_type) VALUES($1,$2,$3,$4)",
        code, ep_num, file_id, ftype
    )
    await state.update_data(ep_num=ep_num + 1)
    await msg.answer(f"✅ {ep_num}-qism yuklandi!\n\n📤 Endi {ep_num+1}-qismni yuboring.\nTugatish: /done")

@dp.message(Command("done"), AddAnime.episodes)
async def done_anime_ep(msg: Message, state: FSMContext):
    d = await state.get_data()
    total = d.get("ep_num", 1) - 1
    await msg.answer(
        f"🎉 Anime to'liq saqlandi!\n"
        f"📦 Jami {total} ta qism\n"
        f"Kod: <code>{d['code']}</code>",
        parse_mode="HTML", reply_markup=admin_kb()
    )
    await state.clear()

# =====================
# QISM QO'SHISH (mavjud animega)
# =====================
@dp.message(F.text == "➕ Qism qo'shish")
async def add_ep_start(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
    await msg.answer("🔢 Anime kodini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddEpisodes.code)

@dp.message(AddEpisodes.code)
async def add_ep_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    if not anime:
        return await msg.answer("❌ Anime topilmadi! Kodni qayta kiriting:")
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1", code)
    next_num = len(eps) + 1
    await state.update_data(code=code, ep_num=next_num)
    await msg.answer(
        f"🎬 <b>{anime['name']}</b>\n"
        f"Mavjud qismlar: {len(eps)}\n\n"
        f"📤 {next_num}-qismni yuboring.\nTugatish: /done",
        parse_mode="HTML"
    )
    await state.set_state(AddEpisodes.files)

@dp.message(AddEpisodes.files, F.video | F.document)
async def add_ep_file(msg: Message, state: FSMContext):
    d = await state.get_data()
    ep_num, code = d["ep_num"], d["code"]
    if msg.video:
        file_id, ftype = msg.video.file_id, "video"
    else:
        file_id, ftype = msg.document.file_id, "document"
    await pool.execute(
        "INSERT INTO episodes(anime_code,ep_num,file_id,file_type) VALUES($1,$2,$3,$4)",
        code, ep_num, file_id, ftype
    )
    await state.update_data(ep_num=ep_num + 1)
    await msg.answer(f"✅ {ep_num}-qism yuklandi!\n📤 {ep_num+1}-qismni yuboring yoki /done.")

# =====================
# ANIMELAR RO'YXATI
# =====================
@dp.message(F.text == "🗂 Animelar ro'yxati")
async def anime_list(msg: Message):
    if not await is_admin(msg.from_user.id): return
    animes = await pool.fetch("SELECT * FROM animes ORDER BY name")
    if not animes:
        return await msg.answer("📭 Hozircha anime yo'q.")
    btns = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"manage_{a['code']}")] for a in animes]
    await msg.answer("🗂 <b>Animelar ro'yxati:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("manage_"))
async def cb_manage(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    code = cb.data.replace("manage_", "")
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    if not anime:
        return await cb.message.answer("❌ Topilmadi.")
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1", code)
    dl = await pool.fetchval("SELECT COUNT(*) FROM downloads WHERE anime_code=$1", code)
    await state.update_data(edit_code=code)
    btns = [
        [InlineKeyboardButton(text="✒ Nomini o'zgartirish", callback_data=f"edit_name_{code}")],
        [InlineKeyboardButton(text="🌄 Rasmini o'zgartirish", callback_data=f"edit_photo_{code}")],
        [InlineKeyboardButton(text="✏ Kodini o'zgartirish", callback_data=f"edit_code_{code}")],
        [InlineKeyboardButton(text="🎞 Tavsifini o'zgartirish", callback_data=f"edit_desc_{code}")],
        [InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data=f"delete_{code}")],
    ]
    await cb.message.edit_text(
        f"🎌 <b>{anime['name']}</b>\n"
        f"Kod: <code>{code}</code>\n"
        f"Qismlar: {len(eps)}\n"
        f"Ko'rishlar: {anime['views']}\n"
        f"📥 Yuklanganlar: {dl}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data.startswith("edit_"))
async def cb_edit(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    parts = cb.data.split("_", 2)
    field, code = parts[1], parts[2]
    await state.update_data(edit_code=code, edit_field=field)
    prompts = {
        "name": "✒ Yangi nomini kiriting:",
        "photo": "🌄 Yangi rasmini yuboring:",
        "code": "✏ Yangi kodini kiriting:",
        "desc": "🎞 Yangi tavsifini kiriting:"
    }
    await cb.message.answer(prompts[field])
    await state.set_state(EditField.value)

@dp.message(EditField.value)
async def fsm_edit(msg: Message, state: FSMContext):
    d = await state.get_data()
    code, field = d["edit_code"], d["edit_field"]
    if field == "name":
        await pool.execute("UPDATE animes SET name=$1 WHERE code=$2", msg.text.strip(), code)
    elif field == "desc":
        await pool.execute("UPDATE animes SET description=$1 WHERE code=$2", msg.text.strip(), code)
    elif field == "code":
        await pool.execute("UPDATE animes SET code=$1 WHERE code=$2", msg.text.strip().upper(), code)
    elif field == "photo":
        if not msg.photo:
            return await msg.answer("Rasm yuboring:")
        await pool.execute("UPDATE animes SET photo_id=$1 WHERE code=$2", msg.photo[-1].file_id, code)
    await msg.answer("✅ Yangilandi!", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data.startswith("delete_"))
async def cb_delete(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return
    code = cb.data.replace("delete_", "")
    await pool.execute("DELETE FROM animes WHERE code=$1", code)
    await cb.message.edit_text(f"🗑 <code>{code}</code> o'chirildi.", parse_mode="HTML")

# =====================
# QIDIRISH
# =====================
@dp.message(F.text == "🔎 Anime qidirish")
async def search_start(msg: Message, state: FSMContext):
    prompt = await get_setting("search_prompt")
    await msg.answer(prompt, reply_markup=ReplyKeyboardRemove())
    await state.set_state(SearchAnime.waiting)

@dp.message(F.text == "📋 Barcha animelar")
async def all_animes(msg: Message):
    await pool.execute("INSERT INTO users(user_id,username) VALUES($1,$2) ON CONFLICT DO NOTHING", msg.from_user.id, msg.from_user.username)
    animes = await pool.fetch("SELECT * FROM animes ORDER BY name")
    if not animes:
        return await msg.answer("📭 Hozircha anime yo'q.")
    btns = [[InlineKeyboardButton(text=f"🎌 {a['name']}", callback_data=f"show_{a['code']}")] for a in animes]
    await msg.answer("📋 <b>Barcha animelar:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("show_"))
async def cb_show(cb: CallbackQuery):
    await cb.answer()
    code = cb.data.replace("show_", "")
    not_sub = await check_sub(cb.from_user.id)
    if not_sub:
        sub_msg = await get_setting("sub_msg")
        btns = [[InlineKeyboardButton(text=f"📢 {c['channel_name']}", url=f"https://t.me/{c['channel_id'].replace('@','')}")] for c in not_sub]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        return await cb.message.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    if anime:
        await send_anime_info(cb.message, anime)

@dp.message(SearchAnime.waiting)
async def do_search(msg: Message, state: FSMContext):
    await state.clear()
    text = msg.text.strip()
    not_sub = await check_sub(msg.from_user.id)
    if not_sub:
        sub_msg = await get_setting("sub_msg")
        btns = [[InlineKeyboardButton(text=f"📢 {c['channel_name']}", url=f"https://t.me/{c['channel_id'].replace('@','')}")] for c in not_sub]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        return await msg.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", text.upper())
    if anime:
        await send_anime_info(msg, anime)
        await msg.answer("🏠", reply_markup=main_kb())
        return
    results = await pool.fetch("SELECT * FROM animes WHERE LOWER(name) LIKE $1", f"%{text.lower()}%")
    if results:
        btns = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"show_{a['code']}")] for a in results[:10]]
        await msg.answer("🔎 Natijalar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        not_found = await get_setting("not_found")
        await msg.answer(not_found, reply_markup=main_kb())

@dp.message(F.text, ~F.text.startswith("/"))
async def text_search(msg: Message):
    if await is_admin(msg.from_user.id): return
    await pool.execute("INSERT INTO users(user_id,username) VALUES($1,$2) ON CONFLICT DO NOTHING", msg.from_user.id, msg.from_user.username)
    not_sub = await check_sub(msg.from_user.id)
    if not_sub:
        sub_msg = await get_setting("sub_msg")
        btns = [[InlineKeyboardButton(text=f"📢 {c['channel_name']}", url=f"https://t.me/{c['channel_id'].replace('@','')}")] for c in not_sub]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        return await msg.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    text = msg.text.strip()
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1 OR LOWER(name)=LOWER($2)", text.upper(), text)
    if anime:
        return await send_anime_info(msg, anime)
    results = await pool.fetch("SELECT * FROM animes WHERE LOWER(name) LIKE $1", f"%{text.lower()}%")
    if results:
        btns = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"show_{a['code']}")] for a in results[:10]]
        await msg.answer("🔎 Natijalar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        not_found = await get_setting("not_found")
        await msg.answer(not_found)

# =====================
# OBUNA TEKSHIRISH
# =====================
@dp.callback_query(F.data == "check_sub")
async def cb_check(cb: CallbackQuery):
    not_sub = await check_sub(cb.from_user.id)
    if not_sub:
        await cb.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)
    else:
        await cb.answer("✅ Rahmat!", show_alert=True)
        await cb.message.delete()

# =====================
# EPISODE TOMOSHA
# =====================
@dp.callback_query(F.data.startswith("ep_"))
async def cb_episode(cb: CallbackQuery):
    await cb.answer()
    not_sub = await check_sub(cb.from_user.id)
    if not_sub:
        sub_msg = await get_setting("sub_msg")
        btns = [[InlineKeyboardButton(text=f"📢 {c['channel_name']}", url=f"https://t.me/{c['channel_id'].replace('@','')}")] for c in not_sub]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        return await cb.message.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    parts = cb.data.replace("ep_", "").split("_")
    code, ep_num = parts[0], int(parts[1])
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    ep = await pool.fetchrow("SELECT * FROM episodes WHERE anime_code=$1 AND ep_num=$2", code, ep_num)
    if not ep:
        return await cb.message.answer("❌ Qism topilmadi.")
    await pool.execute("INSERT INTO downloads(anime_code,ep_num,user_id) VALUES($1,$2,$3)", code, ep_num, cb.from_user.id)
    cap = f"🎌 <b>{anime['name']}</b> — {ep_num}-qism"
    next_ep = await pool.fetchrow("SELECT * FROM episodes WHERE anime_code=$1 AND ep_num=$2", code, ep_num + 1)
    kb = None
    if next_ep:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"▶️ {ep_num+1}-qism →", callback_data=f"ep_{code}_{ep_num+1}")
        ]])
    if ep["file_type"] == "video":
        await cb.message.answer_video(ep["file_id"], caption=cap, parse_mode="HTML", reply_markup=kb)
    else:
        await cb.message.answer_document(ep["file_id"], caption=cap, parse_mode="HTML", reply_markup=kb)

# =====================
# KANALGA POST
# =====================
@dp.message(F.text == "📤 Kanalga post")
async def post_start(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id): return
    await msg.answer("🔢 Anime kodini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(PostAnime.code)

@dp.message(PostAnime.code)
async def post_send(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    if not anime:
        return await msg.answer("❌ Topilmadi. Kodni qayta kiriting:")
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1", code)
    channels = await pool.fetch("SELECT * FROM post_channels")
    if not channels:
        await msg.answer("❌ Post kanali yo'q. Bot sozlaridan qo'shing.", reply_markup=admin_kb())
        await state.clear()
        return
    cap = f"🎌 <b>{anime['name']}</b>\n"
    if anime["description"]:
        cap += f"📝 {anime['description']}\n"
    cap += f"\n🔢 Kod: <code>{anime['code']}</code>\n🎬 {len(eps)} ta qism"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Tomosha qilish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
    ]])
    sent = 0
    for ch in channels:
        try:
            if anime["photo_id"]:
                await bot.send_photo(ch["channel_id"], anime["photo_id"], caption=cap, parse_mode="HTML", reply_markup=kb)
            else:
                await bot.send_message(ch["channel_id"], cap, parse_mode="HTML", reply_markup=kb)
            sent += 1
        except Exception as e:
            await msg.answer(f"❌ {ch['channel_id']}: {e}")
    await msg.answer(f"✅ {sent} ta kanalga post yuborildi!", reply_markup=admin_kb())
    await state.clear()

# =====================
# STATISTIKA
# =====================
@dp.message(F.text == "📊 Statistika")
async def stats(msg: Message):
    if not await is_admin(msg.from_user.id): return
    total = await pool.fetchval("SELECT COUNT(*) FROM users")
    n1 = await pool.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= $1", datetime.now() - timedelta(days=1))
    n3 = await pool.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= $1", datetime.now() - timedelta(days=3))
    n7 = await pool.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= $1", datetime.now() - timedelta(days=7))
    animes = await pool.fetchval("SELECT COUNT(*) FROM animes")
    dls = await pool.fetchval("SELECT COUNT(*) FROM downloads")
    await msg.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👤 <b>Obunachilar soni:</b> {total}\n"
        f"• 1 kun: +{n1}\n"
        f"• 3 kun: +{n3}\n"
        f"• 7 kun: +{n7}\n\n"
        f"🎞 <b>Animelar soni:</b> {animes}\n"
        f"📥 <b>Yuklanganlar soni:</b> {dls}",
        parse_mode="HTML"
    )

# =====================
# OBUNA KANALI
# =====================
@dp.message(F.text == "🔒 Obuna kanali")
async def sub_panel(msg: Message):
    if not await is_admin(msg.from_user.id): return
    channels = await pool.fetch("SELECT * FROM sub_channels")
    text = "🔒 <b>Obuna kanallari:</b>\n" + "\n".join([f"• {c['channel_name']} ({c['channel_id']})" for c in channels]) if channels else "🔒 Kanal yo'q."
    btns = [[InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_sub")]]
    for c in channels:
        btns.append([InlineKeyboardButton(text=f"❌ {c['channel_name']}", callback_data=f"del_sub_{c['channel_id']}")])
    await msg.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data == "add_sub")
async def cb_add_sub(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    await cb.message.answer("Kanal kiriting:\n@kanal_username Kanal nomi")
    await state.set_state(AddSubChan.waiting)

@dp.message(AddSubChan.waiting)
async def fsm_sub(msg: Message, state: FSMContext):
    parts = msg.text.strip().split(" ", 1)
    ch_id, ch_name = parts[0], parts[1] if len(parts) > 1 else parts[0]
    await pool.execute("INSERT INTO sub_channels(channel_id,channel_name) VALUES($1,$2) ON CONFLICT DO NOTHING", ch_id, ch_name)
    await msg.answer(f"✅ {ch_name} qo'shildi!", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data.startswith("del_sub_"))
async def cb_del_sub(cb: CallbackQuery):
    ch_id = cb.data.replace("del_sub_", "")
    await pool.execute("DELETE FROM sub_channels WHERE channel_id=$1", ch_id)
    await cb.message.edit_text(f"✅ {ch_id} o'chirildi.")

# =====================
# BOT SOZLARI
# =====================
@dp.message(F.text == "🔊 Bot sozlari")
async def bot_settings(msg: Message):
    if not await is_admin(msg.from_user.id): return
    btns = [
        [InlineKeyboardButton(text="👋 Xush kelibsiz xabari", callback_data="set_welcome")],
        [InlineKeyboardButton(text="❌ Topilmadi xabari", callback_data="set_not_found")],
        [InlineKeyboardButton(text="📢 Obuna xabari", callback_data="set_sub_msg")],
        [InlineKeyboardButton(text="⭐ Admin kontakt", callback_data="set_contact")],
        [InlineKeyboardButton(text="🔎 Qidiruv xabari", callback_data="set_search_prompt")],
        [InlineKeyboardButton(text="📤 Post kanal qo'shish", callback_data="add_post_chan")],
        [InlineKeyboardButton(text="❌ Post kanal o'chirish", callback_data="del_post_chan")],
    ]
    await msg.answer("🔊 <b>Bot sozlari:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("set_"))
async def cb_set(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    key = cb.data.replace("set_", "")
    prompts = {
        "welcome": "👋 Yangi xush kelibsiz xabarini kiriting:",
        "not_found": "❌ Yangi topilmadi xabarini kiriting:",
        "sub_msg": "📢 Yangi obuna xabarini kiriting:",
        "contact": "⭐ Admin kontakt matnini kiriting:",
        "search_prompt": "🔎 Yangi qidiruv xabarini kiriting:",
    }
    await cb.message.answer(prompts.get(key, "Yangi qiymat:"))
    await state.update_data(setting_key=key)
    await state.set_state(SetSetting.value)

@dp.message(SetSetting.value)
async def fsm_setting(msg: Message, state: FSMContext):
    d = await state.get_data()
    await pool.execute("INSERT INTO bot_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=$2", d["setting_key"], msg.text.strip())
    await msg.answer("✅ Sozlama yangilandi!", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data == "add_post_chan")
async def cb_add_post(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    await cb.message.answer("Post kanalini kiriting:\n@kanal_username Kanal nomi")
    await state.set_state(AddPostChan.waiting)

@dp.message(AddPostChan.waiting)
async def fsm_post_chan(msg: Message, state: FSMContext):
    parts = msg.text.strip().split(" ", 1)
    ch_id, ch_name = parts[0], parts[1] if len(parts) > 1 else parts[0]
    await pool.execute("INSERT INTO post_channels(channel_id,channel_name) VALUES($1,$2) ON CONFLICT DO NOTHING", ch_id, ch_name)
    await msg.answer(f"✅ Post kanali {ch_name} qo'shildi!", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data == "del_post_chan")
async def cb_del_post(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return
    channels = await pool.fetch("SELECT * FROM post_channels")
    if not channels:
        return await cb.message.answer("Kanal yo'q.")
    btns = [[InlineKeyboardButton(text=f"❌ {c['channel_name']}", callback_data=f"rm_post_{c['channel_id']}")] for c in channels]
    await cb.message.answer("O'chirish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("rm_post_"))
async def cb_rm_post(cb: CallbackQuery):
    ch_id = cb.data.replace("rm_post_", "")
    await pool.execute("DELETE FROM post_channels WHERE channel_id=$1", ch_id)
    await cb.message.edit_text(f"✅ {ch_id} o'chirildi.")

# =====================
# RENDER WEB SERVER
# =====================
async def web_server(request):
    return web.Response(text="Bot is running!")

async def main():
    await db_init()
    app = web.Application()
    app.router.add_get("/", web_server)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()
    print("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
