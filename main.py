import os
import asyncio
import asyncpg
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7164685036"))
DB_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
pool = None

async def db_init():
    global pool
    pool = await asyncpg.create_pool(dsn=DB_URL, ssl="require")
    await pool.execute("""
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
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            joined_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS admins (
            admin_id BIGINT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS downloads (
            id SERIAL PRIMARY KEY,
            anime_code TEXT,
            ep_num INT,
            user_id BIGINT,
            downloaded_at TIMESTAMP DEFAULT NOW()
        );
    """)
    # Default sozlamalar
    await pool.execute("INSERT INTO bot_settings(key,value) VALUES('welcome','🎌 Xush kelibsiz! Anime kodini yuboring.') ON CONFLICT DO NOTHING")
    await pool.execute("INSERT INTO bot_settings(key,value) VALUES('not_found','😔 Anime topilmadi.') ON CONFLICT DO NOTHING")
    await pool.execute("INSERT INTO bot_settings(key,value) VALUES('sub_msg','📢 Quyidagi kanallarga obuna bo''ling') ON CONFLICT DO NOTHING")
    await pool.execute("INSERT INTO bot_settings(key,value) VALUES('contact','Admin: @admin') ON CONFLICT DO NOTHING")

# =====================
# STATES
# =====================
class AddAnime(StatesGroup):
    code = State()
    name = State()
    desc = State()
    photo = State()

class AddEp(StatesGroup):
    code = State()
    files = State()

class EditAnime(StatesGroup):
    value = State()

class AddSub(StatesGroup):
    waiting = State()

class AddPostChan(StatesGroup):
    waiting = State()

class PostState(StatesGroup):
    code = State()

class AddAdminState(StatesGroup):
    waiting = State()

class SetSetting(StatesGroup):
    key = State()
    value = State()

# =====================
# HELPERS
# =====================
async def is_admin(user_id):
    if user_id == ADMIN_ID:
        return True
    row = await pool.fetchrow("SELECT admin_id FROM admins WHERE admin_id=$1", user_id)
    return row is not None

async def get_setting(key):
    row = await pool.fetchrow("SELECT value FROM bot_settings WHERE key=$1", key)
    return row["value"] if row else ""

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

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="add_anime")],
        [InlineKeyboardButton(text="🗂 Animelar ro'yxati", callback_data="anime_list")],
        [InlineKeyboardButton(text="➕ Qism qo'shish", callback_data="add_ep")],
        [InlineKeyboardButton(text="🔒 Majburiy obuna", callback_data="sub_chan")],
        [InlineKeyboardButton(text="📤 Kanalga post", callback_data="post_anime")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton(text="🔊 Bot sozlari", callback_data="bot_settings")],
        [InlineKeyboardButton(text="🏧 Adminlar", callback_data="admins")],
    ])

async def send_anime(msg, anime):
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1 ORDER BY ep_num", anime["code"])
    await pool.execute("UPDATE animes SET views=views+1 WHERE code=$1", anime["code"])
    cap = f"🎌 <b>{anime['name']}</b>\n"
    if anime["description"]:
        cap += f"📝 {anime['description']}\n"
    cap += f"\n🔢 Kod: <code>{anime['code']}</code>\n🎬 Qismlar: {len(eps)}\n👁 Ko'rishlar: {anime['views']+1}"
    btns = []
    row = []
    for ep in eps:
        row.append(InlineKeyboardButton(text=f"▶️ {ep['ep_num']}-qism", callback_data=f"watch_{anime['code']}_{ep['ep_num']}"))
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
# USER HANDLERS
# =====================
@dp.message(CommandStart())
async def start(msg: Message):
    await pool.execute("INSERT INTO users(user_id) VALUES($1) ON CONFLICT DO NOTHING", msg.from_user.id)
    args = msg.text.split()
    if len(args) > 1:
        anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", args[1].upper())
        if anime:
            await send_anime(msg, anime)
            return
    welcome = await get_setting("welcome")
    await msg.answer(welcome)

@dp.message(Command("admin"))
async def admin(msg: Message):
    if not await is_admin(msg.from_user.id):
        return await msg.answer("❌ Siz admin emassiz!")
    await msg.answer("🎛 <b>Boshqaruv paneli</b>", parse_mode="HTML", reply_markup=admin_kb())

@dp.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Bekor qilindi.")

@dp.message(Command("done"), AddEp.files)
async def done(msg: Message, state: FSMContext):
    d = await state.get_data()
    total = d.get("ep_num", 1) - 1
    await msg.answer(f"✅ {total} ta qism saqlandi! Kod: <code>{d.get('code')}</code>", parse_mode="HTML")
    await state.clear()

@dp.message(F.text, ~F.text.startswith("/"))
async def search(msg: Message):
    await pool.execute("INSERT INTO users(user_id) VALUES($1) ON CONFLICT DO NOTHING", msg.from_user.id)
    not_sub = await check_sub(msg.from_user.id)
    if not_sub:
        sub_msg = await get_setting("sub_msg")
        btns = [[InlineKeyboardButton(text=f"📢 {c['channel_name']}", url=f"https://t.me/{c['channel_id'].replace('@','')}")] for c in not_sub]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        return await msg.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", msg.text.strip().upper())
    if anime:
        return await send_anime(msg, anime)

    results = await pool.fetch("SELECT * FROM animes WHERE LOWER(name) LIKE $1", f"%{msg.text.lower()}%")
    if results:
        btns = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"watch_{a['code']}")] for a in results[:8]]
        await msg.answer("🔎 Natijalar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        not_found = await get_setting("not_found")
        await msg.answer(not_found)

# =====================
# CALLBACKS - USER
# =====================
@dp.callback_query(F.data == "check_sub")
async def cb_check(cb: CallbackQuery):
    not_sub = await check_sub(cb.from_user.id)
    if not_sub:
        await cb.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)
    else:
        await cb.answer("✅ Rahmat!", show_alert=True)
        await cb.message.delete()

@dp.callback_query(F.data.startswith("watch_"))
async def cb_watch(cb: CallbackQuery):
    await cb.answer()
    not_sub = await check_sub(cb.from_user.id)
    if not_sub:
        sub_msg = await get_setting("sub_msg")
        btns = [[InlineKeyboardButton(text=f"📢 {c['channel_name']}", url=f"https://t.me/{c['channel_id'].replace('@','')}")] for c in not_sub]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        return await cb.message.answer(sub_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

    parts = cb.data.replace("watch_", "").split("_")
    code = parts[0]
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    if not anime:
        return await cb.message.answer("❌ Topilmadi.")
    if len(parts) == 1:
        return await send_anime(cb.message, anime)

    ep_num = int(parts[1])
    ep = await pool.fetchrow("SELECT * FROM episodes WHERE anime_code=$1 AND ep_num=$2", code, ep_num)
    if not ep:
        return await cb.message.answer("❌ Qism topilmadi.")

    # Yuklanganlar soni
    await pool.execute("INSERT INTO downloads(anime_code,ep_num,user_id) VALUES($1,$2,$3)", code, ep_num, cb.from_user.id)

    cap = f"🎌 <b>{anime['name']}</b> — {ep_num}-qism"
    next_ep = await pool.fetchrow("SELECT * FROM episodes WHERE anime_code=$1 AND ep_num=$2", code, ep_num + 1)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"▶️ {ep_num+1}-qism →", callback_data=f"watch_{code}_{ep_num+1}")]]) if next_ep else None

    if ep["file_type"] == "video":
        await cb.message.answer_video(ep["file_id"], caption=cap, parse_mode="HTML", reply_markup=kb)
    else:
        await cb.message.answer_document(ep["file_id"], caption=cap, parse_mode="HTML", reply_markup=kb)

# =====================
# CALLBACKS - ADMIN
# =====================
@dp.callback_query(F.data == "back")
async def cb_back(cb: CallbackQuery):
    await cb.message.edit_text("🎛 <b>Boshqaruv paneli</b>", parse_mode="HTML", reply_markup=admin_kb())

@dp.callback_query(F.data == "stats")
async def cb_stats(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return
    total = await pool.fetchval("SELECT COUNT(*) FROM users")
    n1 = await pool.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= $1", datetime.now() - timedelta(days=1))
    n3 = await pool.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= $1", datetime.now() - timedelta(days=3))
    n7 = await pool.fetchval("SELECT COUNT(*) FROM users WHERE joined_at >= $1", datetime.now() - timedelta(days=7))
    animes = await pool.fetchval("SELECT COUNT(*) FROM animes")
    downloads = await pool.fetchval("SELECT COUNT(*) FROM downloads")
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👤 <b>Obunachilar:</b>\n"
        f"• Jami: {total}\n"
        f"• 1 kun: +{n1}\n"
        f"• 3 kun: +{n3}\n"
        f"• 7 kun: +{n7}\n\n"
        f"🎞 <b>Animelar:</b> {animes}\n"
        f"📥 <b>Yuklanganlar:</b> {downloads}"
    )
    await cb.message.edit_text(text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")]]))

# --- Anime qo'shish ---
@dp.callback_query(F.data == "add_anime")
async def cb_add_anime(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    await cb.message.answer("🔢 Anime kodini kiriting (masalan: NRT):")
    await state.set_state(AddAnime.code)

@dp.message(AddAnime.code)
async def fsm_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    if await pool.fetchrow("SELECT code FROM animes WHERE code=$1", code):
        return await msg.answer("❌ Bu kod mavjud. Boshqa kod:")
    await state.update_data(code=code)
    await msg.answer("✒ Nomini kiriting:")
    await state.set_state(AddAnime.name)

@dp.message(AddAnime.name)
async def fsm_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("🎞 Tavsif kiriting (/skip):")
    await state.set_state(AddAnime.desc)

@dp.message(AddAnime.desc)
async def fsm_desc(msg: Message, state: FSMContext):
    await state.update_data(desc=None if msg.text == "/skip" else msg.text.strip())
    await msg.answer("🏞 Rasm yuboring (/skip):")
    await state.set_state(AddAnime.photo)

@dp.message(AddAnime.photo)
async def fsm_photo(msg: Message, state: FSMContext):
    photo = None
    if msg.photo:
        photo = msg.photo[-1].file_id
    elif msg.text != "/skip":
        return await msg.answer("Rasm yuboring yoki /skip:")
    d = await state.get_data()
    await pool.execute("INSERT INTO animes(code,name,description,photo_id) VALUES($1,$2,$3,$4)", d["code"], d["name"], d.get("desc"), photo)
    await msg.answer(f"✅ <b>{d['name']}</b> qo'shildi!\nKod: <code>{d['code']}</code>", parse_mode="HTML")
    await state.clear()

# --- Animelar ro'yxati ---
@dp.callback_query(F.data == "anime_list")
async def cb_list(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return
    animes = await pool.fetch("SELECT * FROM animes ORDER BY code")
    if not animes:
        return await cb.message.edit_text("📭 Anime yo'q.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back")]]))
    btns = [[InlineKeyboardButton(text=f"🎌 {a['name']} [{a['code']}]", callback_data=f"manage_{a['code']}")] for a in animes]
    btns.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")])
    await cb.message.edit_text("🗂 <b>Animelar:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("manage_"))
async def cb_manage(cb: CallbackQuery, state: FSMContext):
    code = cb.data.replace("manage_", "")
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1", code)
    downloads = await pool.fetchval("SELECT COUNT(*) FROM downloads WHERE anime_code=$1", code)
    await state.update_data(edit_code=code)
    btns = [
        [InlineKeyboardButton(text="✒ Nom", callback_data=f"edit_name_{code}"),
         InlineKeyboardButton(text="🏞 Rasm", callback_data=f"edit_photo_{code}")],
        [InlineKeyboardButton(text="🎞 Tavsif", callback_data=f"edit_desc_{code}"),
         InlineKeyboardButton(text="🔢 Kod", callback_data=f"edit_code_{code}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delete_{code}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="anime_list")],
    ]
    await cb.message.edit_text(
        f"🎌 <b>{anime['name']}</b>\n"
        f"Kod: <code>{code}</code>\n"
        f"Qismlar: {len(eps)}\n"
        f"Ko'rishlar: {anime['views']}\n"
        f"📥 Yuklanganlar: {downloads}",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )

@dp.callback_query(F.data.startswith("delete_"))
async def cb_delete(cb: CallbackQuery):
    code = cb.data.replace("delete_", "")
    await pool.execute("DELETE FROM animes WHERE code=$1", code)
    await cb.message.edit_text(f"🗑 <code>{code}</code> o'chirildi.", parse_mode="HTML")

@dp.callback_query(F.data.startswith("edit_"))
async def cb_edit(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split("_", 2)
    field, code = parts[1], parts[2]
    await state.update_data(edit_code=code, edit_field=field)
    prompts = {"name": "✒ Yangi nomini:", "photo": "🏞 Yangi rasmini yuboring:", "desc": "🎞 Yangi tavsifini:", "code": "🔢 Yangi kodini:"}
    await cb.message.answer(prompts[field])
    await state.set_state(EditAnime.value)

@dp.message(EditAnime.value)
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
    await msg.answer("✅ Yangilandi!")
    await state.clear()

# --- Qism qo'shish ---
@dp.callback_query(F.data == "add_ep")
async def cb_add_ep(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    await cb.message.answer("🔢 Anime kodini kiriting:")
    await state.set_state(AddEp.code)

@dp.message(AddEp.code)
async def fsm_ep_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    if not anime:
        return await msg.answer("❌ Topilmadi. Kodni qayta kiriting:")
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1", code)
    next_num = len(eps) + 1
    await state.update_data(code=code, ep_num=next_num)
    await msg.answer(f"🎬 <b>{anime['name']}</b>\n📤 {next_num}-qismni yuboring.\nTugatish: /done", parse_mode="HTML")
    await state.set_state(AddEp.files)

@dp.message(AddEp.files, F.video | F.document)
async def fsm_ep_file(msg: Message, state: FSMContext):
    d = await state.get_data()
    ep_num, code = d["ep_num"], d["code"]
    if msg.video:
        file_id, ftype = msg.video.file_id, "video"
    else:
        file_id, ftype = msg.document.file_id, "document"
    await pool.execute("INSERT INTO episodes(anime_code,ep_num,file_id,file_type) VALUES($1,$2,$3,$4)", code, ep_num, file_id, ftype)
    await state.update_data(ep_num=ep_num + 1)
    await msg.answer(f"✅ {ep_num}-qism saqlandi!\n📤 {ep_num+1}-qismni yuboring yoki /done.")

# --- Majburiy obuna ---
@dp.callback_query(F.data == "sub_chan")
async def cb_sub(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return
    channels = await pool.fetch("SELECT * FROM sub_channels")
    text = "🔒 <b>Obuna kanallari:</b>\n" + "\n".join([f"• {c['channel_name']} ({c['channel_id']})" for c in channels]) if channels else "🔒 Kanal yo'q."
    btns = [[InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_sub")]]
    for c in channels:
        btns.append([InlineKeyboardButton(text=f"❌ {c['channel_name']}", callback_data=f"del_sub_{c['channel_id']}")])
    btns.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")])
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data == "add_sub")
async def cb_add_sub(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Kanal kiriting:\n@kanal_username Kanal nomi")
    await state.set_state(AddSub.waiting)

@dp.message(AddSub.waiting)
async def fsm_sub(msg: Message, state: FSMContext):
    parts = msg.text.strip().split(" ", 1)
    ch_id, ch_name = parts[0], parts[1] if len(parts) > 1 else parts[0]
    await pool.execute("INSERT INTO sub_channels(channel_id,channel_name) VALUES($1,$2) ON CONFLICT DO NOTHING", ch_id, ch_name)
    await msg.answer(f"✅ {ch_name} qo'shildi!")
    await state.clear()

@dp.callback_query(F.data.startswith("del_sub_"))
async def cb_del_sub(cb: CallbackQuery):
    ch_id = cb.data.replace("del_sub_", "")
    await pool.execute("DELETE FROM sub_channels WHERE channel_id=$1", ch_id)
    await cb.message.edit_text(f"✅ {ch_id} o'chirildi.")

# --- Bot sozlari ---
@dp.callback_query(F.data == "bot_settings")
async def cb_settings(cb: CallbackQuery):
    if not await is_admin(cb.from_user.id): return
    welcome = await get_setting("welcome")
    not_found = await get_setting("not_found")
    contact = await get_setting("contact")
    btns = [
        [InlineKeyboardButton(text="👋 Xush kelibsiz xabari", callback_data="set_welcome")],
        [InlineKeyboardButton(text="😔 Topilmadi xabari", callback_data="set_not_found")],
        [InlineKeyboardButton(text="📢 Obuna xabari", callback_data="set_sub_msg")],
        [InlineKeyboardButton(text="⭐ Admin kontakt", callback_data="set_contact")],
        [InlineKeyboardButton(text="➕ Post kanal qo'shish", callback_data="add_post_chan")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")],
    ]
    text = (f"🔊 <b>Bot sozlari:</b>\n\n"
            f"👋 Xush kelibsiz: {welcome[:30]}...\n"
            f"😔 Topilmadi: {not_found[:30]}\n"
            f"⭐ Kontakt: {contact}")
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("set_"))
async def cb_set(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    key = cb.data.replace("set_", "")
    prompts = {
        "welcome": "👋 Yangi xush kelibsiz xabarini kiriting:",
        "not_found": "😔 Yangi topilmadi xabarini kiriting:",
        "sub_msg": "📢 Yangi obuna xabarini kiriting:",
        "contact": "⭐ Admin kontakt matnini kiriting (masalan: Admin: @username):"
    }
    await cb.message.answer(prompts.get(key, "Yangi qiymatni kiriting:"))
    await state.update_data(setting_key=key)
    await state.set_state(SetSetting.value)

@dp.message(SetSetting.value)
async def fsm_setting(msg: Message, state: FSMContext):
    d = await state.get_data()
    await pool.execute("INSERT INTO bot_settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=$2", d["setting_key"], msg.text.strip())
    await msg.answer("✅ Sozlama yangilandi!")
    await state.clear()

@dp.callback_query(F.data == "add_post_chan")
async def cb_add_post(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Post kanalini kiriting:\n@kanal_username Kanal nomi")
    await state.set_state(AddPostChan.waiting)

@dp.message(AddPostChan.waiting)
async def fsm_post_chan(msg: Message, state: FSMContext):
    parts = msg.text.strip().split(" ", 1)
    ch_id, ch_name = parts[0], parts[1] if len(parts) > 1 else parts[0]
    await pool.execute("INSERT INTO post_channels(channel_id,channel_name) VALUES($1,$2) ON CONFLICT DO NOTHING", ch_id, ch_name)
    await msg.answer(f"✅ Post kanali {ch_name} qo'shildi!")
    await state.clear()

# --- Adminlar ---
@dp.callback_query(F.data == "admins")
async def cb_admins(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    admins = await pool.fetch("SELECT * FROM admins")
    text = "🏧 <b>Adminlar:</b>\n" + "\n".join([f"• <code>{a['admin_id']}</code>" for a in admins]) if admins else "🏧 Qo'shimcha admin yo'q."
    btns = [
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin")],
    ]
    for a in admins:
        btns.append([InlineKeyboardButton(text=f"❌ {a['admin_id']}", callback_data=f"del_admin_{a['admin_id']}")])
    btns.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")])
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data == "add_admin")
async def cb_add_admin(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ADMIN_ID: return
    await cb.message.answer("🏧 Yangi admin Telegram ID sini kiriting:")
    await state.set_state(AddAdminState.waiting)

@dp.message(AddAdminState.waiting)
async def fsm_add_admin(msg: Message, state: FSMContext):
    try:
        admin_id = int(msg.text.strip())
        await pool.execute("INSERT INTO admins(admin_id) VALUES($1) ON CONFLICT DO NOTHING", admin_id)
        await msg.answer(f"✅ Admin {admin_id} qo'shildi!")
    except:
        await msg.answer("❌ Noto'g'ri ID. Raqam kiriting:")
        return
    await state.clear()

@dp.callback_query(F.data.startswith("del_admin_"))
async def cb_del_admin(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID: return
    admin_id = int(cb.data.replace("del_admin_", ""))
    await pool.execute("DELETE FROM admins WHERE admin_id=$1", admin_id)
    await cb.message.edit_text(f"✅ Admin {admin_id} o'chirildi.")

# --- Admin bilan bog'lanish ---
@dp.message(Command("contact"))
async def contact(msg: Message):
    contact_text = await get_setting("contact")
    await msg.answer(f"⭐ <b>Admin bilan bog'lanish:</b>\n\n{contact_text}", parse_mode="HTML")

# --- Post yuborish ---
@dp.callback_query(F.data == "post_anime")
async def cb_post(cb: CallbackQuery, state: FSMContext):
    if not await is_admin(cb.from_user.id): return
    await cb.message.answer("🔢 Post yuborish uchun anime kodini kiriting:")
    await state.set_state(PostState.code)

@dp.message(PostState.code)
async def fsm_post(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    anime = await pool.fetchrow("SELECT * FROM animes WHERE code=$1", code)
    if not anime:
        return await msg.answer("❌ Topilmadi. Kodni qayta kiriting:")
    eps = await pool.fetch("SELECT * FROM episodes WHERE anime_code=$1", code)
    channels = await pool.fetch("SELECT * FROM post_channels")
    if not channels:
        await msg.answer("❌ Post kanali yo'q. Bot sozlari > Post kanal qo'shish.")
        await state.clear()
        return
    cap = f"🎌 <b>{anime['name']}</b>\n"
    if anime["description"]:
        cap += f"📝 {anime['description']}\n"
    cap += f"\n🔢 Kod: <code>{anime['code']}</code>\n🎬 {len(eps)} qism"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Tomosha qilish", url=f"https://t.me/{BOT_USERNAME}?start={code}")
    ]])
    for ch in channels:
        try:
            if anime["photo_id"]:
                await bot.send_photo(ch["channel_id"], anime["photo_id"], caption=cap, parse_mode="HTML", reply_markup=kb)
            else:
                await bot.send_message(ch["channel_id"], cap, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            await msg.answer(f"❌ {ch['channel_id']}: {e}")
    await msg.answer("✅ Post yuborildi!")
    await state.clear()

# =====================
# MAIN
# =====================
async def main():
    await db_init()
    print("✅ Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
