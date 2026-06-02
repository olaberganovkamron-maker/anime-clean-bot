import os
import asyncio
import logging
import sqlite3
from threading import Thread
from flask import Flask
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

# ⚠️ SOZLAMALAR
TOKEN = "8931499273:AAEvhf-cHTkCP8klPQ7cbqIX_buedsxz98Q"
SUPER_ADMIN = 7164685036  # Sening ID raqaming (Asosiy Admin)

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🗄 MULTI-BAZA (SQLITE)
def init_db():
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            join_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS animes (
            code INTEGER PRIMARY KEY,
            title TEXT,
            description TEXT,
            photo_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_code INTEGER,
            part_number INTEGER,
            file_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

init_db()

# FSM - HOLATLAR
class AdminStates(StatesGroup):
    add_anime_photo = State()
    add_anime_title = State()
    add_anime_desc = State()
    edit_value = State()
    change_code_new = State()
    add_part_code = State()
    add_part_video = State()
    send_post = State()
    send_channel_post = State()
    channel_id = State()
    channel_name = State()
    channel_url = State()
    add_admin_id = State()

# ADMINLAR RO'YXATINI OLISH
def get_admins():
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    conn.close()
    admin_list = [SUPER_ADMIN]
    for row in rows:
        admin_list.append(row[0])
    return admin_list

# MAJBURIY OBUNA TEKSHIRISH
async def check_subscription(user_id: int) -> bool:
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM channels")
    rows = cursor.fetchall()
    conn.close()
    for row in rows:
        try:
            member = await bot.get_chat_member(chat_id=row[0], user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except Exception: continue
    return True

# 1-RASMDAGI "BOSHQARISH PANEL" TUGMALARI (100% BIR XIL)
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime Qo'shish", callback_data="adm_add"),
         InlineKeyboardButton(text="📂 Animelarni Ro'yxati", callback_data="adm_list")],
        [InlineKeyboardButton(text="🎬 Qism Qo'shish", callback_data="adm_add_part"),
         InlineKeyboardButton(text="📢 Kanalga Post", callback_data="adm_chan_post")],
        [InlineKeyboardButton(text="📣 Hammaga Xabar", callback_data="adm_post"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📋 Majburiy Kanallar", callback_data="adm_ch_manage"),
         InlineKeyboardButton(text="👮‍♂️ Adminlar", callback_data="adm_manage_admins")],
        [InlineKeyboardButton(text="📩 Kelgan Savollar", callback_data="adm_support_view")],
        [InlineKeyboardButton(text="🔍 Anime Qidirish", callback_data="user_search_mode")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, join_date) VALUES (?, ?)", (user_id, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

    if user_id in get_admins():
        await message.answer("🎛 <b>Boshqarish Paneli:</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
        return

    if not await check_subscription(user_id):
        conn = sqlite3.connect("anime_movieuz.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, url FROM channels")
        channels = cursor.fetchall()
        conn.close()
        
        if channels:
            buttons = []
            for name, url in channels:
                buttons.append([InlineKeyboardButton(text=f"📢 {name}", url=url)])
            buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
            await message.answer("Xush kelibsiz! Botdan foydalanish uchun kanallarga obuna boling:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
            return

    await message.answer("Xush kelibsiz! Animening kodini yoki nomini yuboring.")

# 🔍 GLOBAL ANIME QIDIRUV
@dp.message(F.text & ~F.text.startswith("/"))
async def search_anime(message: Message):
    if message.from_user.id not in get_admins() and not await check_subscription(message.from_user.id): return
    
    query = message.text.strip()
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    
    if query.isdigit():
        cursor.execute("SELECT code, title, description, photo_id FROM animes WHERE code = ?", (int(query),))
    else:
        cursor.execute("SELECT code, title, description, photo_id FROM animes WHERE LOWER(title) LIKE ?", (f"%{query.lower()}%",))
        
    res = cursor.fetchone()
    
    if res:
        code, title, description, photo_id = res
        cursor.execute("SELECT part_number FROM episodes WHERE anime_code = ? ORDER BY part_number ASC", (code,))
        episodes = cursor.fetchall()
        conn.close()
        
        caption = f"🎬 <b>{title}</b>\n\n📝 {description}\n\n🆔 Kod: {code}\n🎥 Jami qismlar: {len(episodes)} ta"
        buttons = []
        row = []
        for ep in episodes:
            p = ep[0]
            row.append(InlineKeyboardButton(text=f"{p}-qism", callback_data=f"play_{code}_{p}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        if photo_id: await message.answer_photo(photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        else: await message.answer(caption, parse_mode="HTML", reply_markup=kb)
    else:
        conn.close()
        await message.answer("uzur anime topilmadi boshqa kodin kirtib koring")

@dp.callback_query(F.data.startswith("play_"))
async def play_video(callback: CallbackQuery):
    _, code, p = callback.data.split("_")
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM episodes WHERE anime_code = ? AND part_number = ?", (int(code), int(p)))
    res = cursor.fetchone()
    conn.close()
    if res:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍿 kanallar tomosha qiling", callback_data="w")]])
        await callback.message.answer_video(video=res[0], caption=f"🎬 {p}-qism", reply_markup=kb)
    await callback.answer()

# 👮‍♂️ ADMINLARNI BOSHQARISH (NEW)
@dp.callback_query(F.data == "adm_manage_admins")
async def manage_admins(callback: CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN:
        await callback.answer("❌ Bu tugma faqat Asosiy Admin uchun!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi Admin Qo'shish", callback_data="add_admin_action")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_panel")]
    ])
    await callback.message.answer("👮‍♂️ Adminlarni boshqarish bo'limi:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "add_admin_action")
async def add_admin_id_req(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Yangi adminning raqamli ID sini yuboring:")
    await state.set_state(AdminStates.add_admin_id)
    await callback.answer()

@dp.message(AdminStates.add_admin_id)
async def add_admin_id_done(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Xato! ID raqamlardan iborat bo'lishi kerak.")
        return
    new_id = int(message.text.strip())
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
    conn.commit()
    conn.close()
    await message.answer("✅ Yangi admin muvaffaqiyatli tayinlandi!", reply_markup=get_admin_keyboard())
    await state.clear()

# 📡 KANAL BOSHQARUVI
@dp.callback_query(F.data == "adm_ch_manage")
async def adm_ch_manage(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_new_channel")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_panel")]
    ])
    await callback.message.answer("📡 Kanallarni boshqarish bo'limi:", reply_markup=kb)
    await callback.answer()

@dp.message(AdminStates.channel_id)
async def add_ch_name(message: Message, state: FSMContext):
    await state.update_data(ch_id=message.text.strip())
    await message.answer("📝 Kanal nomini kiriting:")
    await state.set_state(AdminStates.channel_name)

# 2-RASM: ANIME RO'YXATI VA PASIDAGI EDIT TUGMALARI (100% BIR XIL)
@dp.callback_query(F.data == "adm_list")
async def show_anime_list(callback: CallbackQuery):
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, title FROM animes")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.answer("Bazada anime yo'q.", reply_markup=get_admin_keyboard())
        await callback.answer()
        return
        
    await callback.message.answer(f"📦 <b>Barcha Animelar — jami {len(rows)} ta</b>\n\nBoshqarish uchun animeni bosing:", parse_mode="HTML")
    for code, title in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"#{code} — {title}", callback_data=f"view_anime_{code}")]])
        await callback.message.answer(f"📁 {title}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("view_anime_"))
async def view_anime_details(callback: CallbackQuery):
    code = int(callback.data.split("_")[2])
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, description, photo_id FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_code = ?", (code,))
    ep_count = cursor.fetchone()[0]
    conn.close()
    
    if not anime: return
    
    caption = f"🎬 <b>{anime[1]}</b>\n\n🆔 Kod: {anime[0]}\n🎬 Qismlar soni: {ep_count} ta\n📝 Tavsif: {anime[2]}\n🏞 Rasm: {'Bor ✅' if anime[3] else 'Yoq ❌'}"
    
    # 2-RASMDAGI BUR REQA TUGMALAR STRUKTURASI
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✒️ Nomini o'zgartirish", callback_data=f"edit_{code}_title")],
        [InlineKeyboardButton(text="🖼 Rasmini o'zgartirish", callback_data=f"edit_{code}_photo")],
        [InlineKeyboardButton(text="✒️ Tavsifini o'zgartirish", callback_data=f"edit_{code}_desc")],
        [InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data=f"edit_{code}_delete")],
        [InlineKeyboardButton(text="💳 Kodini o'zgartirish", callback_data=f"edit_{code}_changecode")],
        [InlineKeyboardButton(text=f"🎬 Qismlar ({ep_count})", callback_data=f"view_parts_{code}")],
        [InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data="adm_list")]
    ])
    
    if anime[3]: await callback.message.answer_photo(photo=anime[3], caption=caption, parse_mode="HTML", reply_markup=kb)
    else: await callback.message.answer(caption, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

# EDIT AMALLARI KODI
@dp.callback_query(F.data.startswith("edit_"))
async def edit_anime_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    code = int(parts[1])
    field = parts[2]
    
    if field == "delete":
        conn = sqlite3.connect("anime_movieuz.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM animes WHERE code = ?", (code,))
        cursor.execute("DELETE FROM episodes WHERE anime_code = ?", (code,))
        conn.commit()
        conn.close()
        await callback.message.answer(f"🗑 #{code} o'chirildi.", reply_markup=get_admin_keyboard())
    elif field == "changecode":
        await callback.message.answer(f"💳 #{code} uchun yangi KOD yuboring:")
        await state.update_data(old_code=code)
        await state.set_state(AdminStates.change_code_new)
    else:
        await state.update_data(edit_code=code, edit_field=field)
        await callback.message.answer(f"📝 Yangi qiymatni kiriting:")
        await state.set_state(AdminStates.edit_value)
    await callback.answer()

@dp.message(AdminStates.change_code_new)
async def change_code_proc(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    new_code = int(message.text.strip())
    data = await state.get_data()
    old_code = data['old_code']
    
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE animes SET code = ? WHERE code = ?", (new_code, old_code))
        cursor.execute("UPDATE episodes SET anime_code = ? WHERE anime_code = ?", (new_code, old_code))
        conn.commit()
        await message.answer(f"✅ Kod o'zgartirildi! {old_code} ➡️ {new_code}", reply_markup=get_admin_keyboard())
    except sqlite3.IntegrityError:
        await message.answer("❌ Bu kod band! Boshqa kod yozing:")
        conn.close()
        return
    conn.close()
    await state.clear()

@dp.message(AdminStates.edit_value)
async def edit_value_proc(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data['edit_code']
    field = data['edit_field']
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    if field == "title": cursor.execute("UPDATE animes SET title = ? WHERE code = ?", (message.text, code))
    elif field == "desc": cursor.execute("UPDATE animes SET description = ? WHERE code = ?", (message.text, code))
    elif field == "photo" and message.photo: cursor.execute("UPDATE animes SET photo_id = ? WHERE code = ?", (message.photo[-1].file_id, code))
    conn.commit()
    conn.close()
    await message.answer("✅ O'zgartirildi!", reply_markup=get_admin_keyboard())
    await state.clear()

# ANIME QO'SHISH
@dp.callback_query(F.data == "adm_add")
async def add_anime_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("1. Anime rasmini yuboring (/skip yozishingiz ham mumkin):")
    await state.set_state(AdminStates.add_anime_photo)
    await callback.answer()

@dp.message(AdminStates.add_anime_photo)
async def add_anime_photo(message: Message, state: FSMContext):
    if message.photo: await state.update_data(photo_id=message.photo[-1].file_id)
    else: await state.update_data(photo_id=None)
    await message.answer("2. Animening nomini kiriting:")
    await state.set_state(AdminStates.add_anime_title)

@dp.message(AdminStates.add_anime_title)
async def add_anime_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("3. Anime tavsifini yozing:")
    await state.set_state(AdminStates.add_anime_desc)

@dp.message(AdminStates.add_anime_desc)
async def add_anime_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO animes (title, description, photo_id) VALUES (?, ?, ?)", (data['title'], message.text.strip(), data['photo_id']))
    new_code = cursor.lastrowid
    conn.commit()
    conn.close()
    await message.answer(f"✅ Anime yaratildi!\n🆔 Kodi: <b>{new_code}</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    await state.clear()

# QISM QO'SHISH TIZIMI
@dp.callback_query(F.data == "adm_add_part")
async def add_part_init(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🎥 Qism qo'shmoqchi bo'lgan anime kodini kiriting:")
    await state.set_state(AdminStates.add_part_code)
    await callback.answer()

@dp.message(AdminStates.add_part_code)
async def add_part_code(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    code = int(message.text)
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM animes WHERE code = ?", (code,))
    res = cursor.fetchone()
    if not res:
        await message.answer("❌ Kod topilmadi!")
        conn.close()
        return
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_code = ?", (code,))
    next_part = cursor.fetchone()[0] + 1
    conn.close()
    await state.update_data(code=code, next_part=next_part)
    await message.answer(f"🎬 <b>{res[0]}</b>\n🎥 <b>{next_part}-qism</b> videosini yuboring (/done bilan tugatiladi):", parse_mode="HTML")
    await state.set_state(AdminStates.add_part_video)

@dp.message(AdminStates.add_part_video)
async def add_part_video(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data['code']
    next_part = data['next_part']
    if message.text == "/done":
        await message.answer("🎉 Saqlandi!", reply_markup=get_admin_keyboard())
        await state.clear()
        return
    if not message.video: return
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO episodes (anime_code, part_number, file_id) VALUES (?, ?, ?)", (code, next_part, message.video.file_id))
    conn.commit()
    conn.close()
    await message.answer(f"✅ {next_part}-qism saqlandi! {next_part+1}-qismni yuboring:", parse_mode="HTML")
    await state.update_data(next_part=next_part + 1)

# STATISTIKA
@dp.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery):
    conn = sqlite3.connect("anime_movieuz.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    u_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM animes")
    a_count = cursor.fetchone()[0]
    conn.close()
    await callback.message.answer(f"📊 Statistika:\n\n👤 obunachilar: {u_count} ta\n🎞 animelar: {a_count} ta", reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_to_panel")
async def back_to_panel(callback: CallbackQuery):
    await callback.message.answer("🎛 Boshqarish Paneli:", reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "check_subs")
async def check_subs_cb(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("Xush kelibsiz! Animening kodini yuboring.")
    else:
        await callback.answer("❌ Kanallarga a'zo bo'lmadingiz!", show_alert=True)

# 🌐 WEB SERVER (Render.com uchun majburiy)
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Online!"
def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

async def main():
    Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
