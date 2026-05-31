import os
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, html, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# 1. LOGGING VA SOZLAMALAR
logging.basicConfig(level=logging.INFO)

# ⚠️ TOKENNI SHU YERGA QO'YASAN, BRO:
TOKEN = "8931499273:AAEvhf-cHTkCP8klPQ7cbqIX_buedsxz98Q" 

# 👥 ADMINLAR RO'YXATI (Sening ID va Yangi Admin ID raqamlari)
ADMIN_IDS = [7164685036, 1234567890]  # 1234567890 o'rniga yangi admin ID sini yozasan

# 4) 🔊 BOTGA SOZLAR QOSHISH
TEXT_WELCOME = "Xush kelibsiz!"
TEXT_SEND_CODE = "animeni kodini yuboring"
TEXT_SUBSCRIBE = "kanalga obuna boling"
TEXT_NOT_FOUND = "anime topilmadi boshqa kodin kiritib koring"

# 5) 🔐 MAJBURI KANAL
REQUIRED_CHANNELS = [
    "@anime_movieuz",   
    "@Anicineuz",       
    "@kanal3",          
    "@kanal4",
    "@kanal5"
] 

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# MA'LUMOTLAR BAZASI TIZIMI
conn = sqlite3.connect("anime_parts_bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, join_date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS animes (code INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, photo_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, anime_code INTEGER, part_number INTEGER, file_id TEXT)")
conn.commit()

# HOLATLAR (FSM TIZIMI)
class AdminStates(StatesGroup):
    add_anime_photo = State()
    add_anime_title = State()
    add_anime_desc = State()
    
    add_only_part_code = State()
    add_only_part_video = State()
    
    edit_select_code = State()
    edit_field_choice = State()
    edit_new_value = State()
    
    delete_code = State()
    send_post = State()
    send_channel_post = State()

# OBUNA TEKSHIRISH
async def check_subscription(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        if "kanal" in channel: continue
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except Exception: continue
    return True

# 1) 🎛 BOSHQARISH BENARI (8) ⭐️ ADMIN TUGMASI CHQSIN)
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime Qo'shish", callback_data="adm_add"),
         InlineKeyboardButton(text="🗂 Animelarni Ro'yxati", callback_data="adm_list")],
        [InlineKeyboardButton(text="📦 Animeni Tahrirlash", callback_data="adm_edit"),
         InlineKeyboardButton(text="🗑 Animelarni O'chirish", callback_data="adm_delete")],
        [InlineKeyboardButton(text="🎬 Qism Qo'shish", callback_data="adm_add_part"),
         InlineKeyboardButton(text="📢 Kanalga Post", callback_data="adm_chan_post")],
        [InlineKeyboardButton(text="📣 Hammaga Xabar", callback_data="adm_post"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")]
    ])

# START BUYRUG'I
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    date_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT OR IGNORE INTO users (user_id, join_date) VALUES (?, ?)", (user_id, date_str))
    conn.commit()
    
    # 5) 🔐 MAJBURI KANAL TEKSHIRISH
    if not await check_subscription(user_id):
        buttons = []
        for ch in REQUIRED_CHANNELS:
            if "kanal" in ch: continue
            buttons.append([InlineKeyboardButton(text=f"📢 {ch} ga a'zo bo'lish", url=f"https://t.me/{ch.replace('@','')}")])
        buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
        await message.answer(TEXT_SUBSCRIBE, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    # 8) ⭐️ ADMIN TUGMASI CHQSIN
    if user_id in ADMIN_IDS:
        await message.answer("🎛 <b>Boshqarish Paneli:</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        await message.answer(TEXT_WELCOME)
        await message.answer(TEXT_SEND_CODE)

# 10) 🎬 OZIM OZIM UCHUN ANIMENI QIDIRISH
@dp.message(F.text.isdigit())
async def search_anime(message: Message):
    if not await check_subscription(message.from_user.id): return
    code = int(message.text)
    cursor.execute("SELECT title, description, photo_id FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    
    if anime:
        title, desc, photo_id = anime
        cursor.execute("SELECT part_number FROM episodes WHERE anime_code = ? ORDER BY part_number ASC", (code,))
        episodes = cursor.fetchall()
        
        caption = f"🎬 <b>{title}</b>\n\n📝 {desc}\n\n🆔 Kod: {code}\n🎥 Jami qismlar: {len(episodes)} ta"
        
        buttons = []
        row = []
        for ep in episodes:
            part_num = ep[0]
            row.append(InlineKeyboardButton(text=f"{part_num}-qism", callback_data=f"get_part_{code}_{part_num}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        if photo_id: await message.answer_photo(photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        else: await message.answer(caption, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(TEXT_NOT_FOUND)

@dp.callback_query(F.data.startswith("get_part_"))
async def callback_get_part(callback: CallbackQuery):
    _, _, code, part_num = callback.data.split("_")
    cursor.execute("SELECT file_id FROM episodes WHERE anime_code = ? AND part_number = ?", (int(code), int(part_num)))
    res = cursor.fetchone()
    if res:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍿 kanallar tomosha qiling", callback_data="watch_now")]])
        await callback.message.answer_video(video=res[0], caption=f"🎬 Qism: {part_num}\n🆔 Kod: {code}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "watch_now")
async def watch_callback(callback: CallbackQuery):
    await callback.answer("Yoqimli tomosha tilaymiz! 🍿")

# --- ⚙️ ADMIN AMALLARI ---

# 2) ➕ ANIME QOSHIAH
@dp.callback_query(F.data == "adm_add")
async def add_anime_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("1. Anime uchun rasm (poster) yuboring:")
    await state.set_state(AdminStates.add_anime_photo)
    await callback.answer()

@dp.message(AdminStates.add_anime_photo)
async def add_photo(message: Message, state: FSMContext):
    if message.photo: await state.update_data(photo_id=message.photo[-1].file_id)
    else: await state.update_data(photo_id=None)
    await message.answer("2. Animening nomini kiriting:")
    await state.set_state(AdminStates.add_anime_title)

@dp.message(AdminStates.add_anime_title)
async def add_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("3. Anime haqida tavsif (opisaniya) yozing:")
    await state.set_state(AdminStates.add_anime_desc)

@dp.message(AdminStates.add_anime_desc)
async def add_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT INTO animes (title, description, photo_id) VALUES (?, ?, ?)", (data['title'], message.text, data.get('photo_id')))
    conn.commit()
    new_code = cursor.lastrowid
    await message.answer(f"✅ Yangi anime muvaffaqiyatli yaratildi!\n🎬 Nomi: {data['title']}\n🆔 Kodi: <b>{new_code}</b>\n\n💡 Qismlarni yuklash uchun '🎬 Qism Qo'shish' tugmasidan foydalaning.", parse_mode="HTML", reply_markup=get_admin_keyboard())
    await state.clear()

# 3) 🗂 ANIMELARNI ROYHATI
@dp.callback_query(F.data == "adm_list")
async def adm_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    cursor.execute("SELECT code, title FROM animes ORDER BY code DESC LIMIT 20")
    rows = cursor.fetchall()
    text = "🗂 <b>Animelar ro'yxati (Oxirgi 20 ta):</b>\n\n" if rows else "Bazada anime yo'q."
    for row in rows: text += f"🆔 {row[0]} — {row[1]}\n"
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()

# 10) 🎬 QISM QO'SHISH TIZIMI
@dp.callback_query(F.data == "adm_add_part")
async def add_part_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("🎥 Qism qo'shmoqchi bo'lgan anime kodini kiriting:")
    await state.set_state(AdminStates.add_only_part_code)
    await callback.answer()

@dp.message(AdminStates.add_only_part_code)
async def add_part_code_rec(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqamli kod kiriting!")
        return
    code = int(message.text)
    cursor.execute("SELECT title FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    if not anime:
        await message.answer("❌ Anime topilmadi! Qayta kiriting:")
        return
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_code = ?", (code,))
    next_part = cursor.fetchone()[0] + 1
    await state.update_data(anime_code=code, current_part=next_part)
    await message.answer(f"🎬 <b>{anime[0]}</b> tanlandi.\n🎥 Ketma-ketlikda <b>{next_part}-qism</b> videosini yuboring:\n(Tugatish uchun /done deb yozing)", parse_mode="HTML")
    await state.set_state(AdminStates.add_only_part_video)

@dp.message(AdminStates.add_only_part_video)
async def add_part_video_loop(message: Message, state: FSMContext):
    if message.text == "/done":
        await message.answer("🎉 Qismlar saqlandi!", reply_markup=get_admin_keyboard())
        await state.clear()
        return
    if not message.video:
        await message.answer("❌ Faqat video formatda yuboring!")
        return
    data = await state.get_data()
    cursor.execute("INSERT INTO episodes (anime_code, part_number, file_id) VALUES (?, ?, ?)", (data['anime_code'], data['current_part'], message.video.file_id))
    conn.commit()
    await message.answer(f"<i>Qabul qilindi!</i>\nNom: {data['current_part']}-qism\n\nKeyingi <b>{data['current_part'] + 1}-qismni</b> yuboring:\n(Tugatish uchun /done yozing)", parse_mode="HTML")
    await state.update_data(current_part=data['current_part'] + 1)

# 6) 📤 KANALGA POST YUBORISH
@dp.callback_query(F.data == "adm_chan_post")
async def chan_post_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("📢 Kanalga yuboriladigan anime kodini kiriting:")
    await state.set_state(AdminStates.send_channel_post)
    await callback.answer()

@dp.message(AdminStates.send_channel_post)
async def chan_post_done(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    code = int(message.text)
    cursor.execute("SELECT title, description, photo_id FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    if not anime:
        await message.answer("❌ Topilmadi!")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍿 kanallar tomosha qiling", url=f"https://t.me/{(await bot.get_me()).username}?start=true")]])
    caption = f"🔥 <b>Yangi Anime!</b>\n\n🎬 Nomi: {anime[0]}\n📝 Haqida: {anime[1]}\n\n🆔 Bot uchun qidiruv kodi: <code>{code}</code>"
    try:
        if anime[2]: await bot.send_photo(chat_id=REQUIRED_CHANNELS[0], photo=anime[2], caption=caption, parse_mode="HTML", reply_markup=kb)
        else: await bot.send_message(chat_id=REQUIRED_CHANNELS[0], text=caption, parse_mode="HTML", reply_markup=kb)
        await message.answer("✅ Kanalga post yuborildi!", reply_markup=get_admin_keyboard())
    except Exception as e:
        await message.answer(f"❌ Xato (Bot kanalda admin bo'lishi shart): {e}", reply_markup=get_admin_keyboard())
    await state.clear()

# 6) 📤 HAMMAGA XABAR (REKLAMA)
@dp.callback_query(F.data == "adm_post")
async def post_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("📣 Reklama matnini kiriting:")
    await state.set_state(AdminStates.send_post)
    await callback.answer()

@dp.message(AdminStates.send_post)
async def post_done(message: Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users"); all_users = cursor.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍿 kanallar tomosha qiling", callback_data="watch_now")]])
    success = 0
    for user in all_users:
        try:
            await bot.send_message(chat_id=user[0], text=message.text, reply_markup=kb)
            success += 1
            await asyncio.sleep(0.05)
        except Exception: continue
    await message.answer(f"✅ Tarqatildi: {success} ta odamga.", reply_markup=get_admin_keyboard())
    await state.clear()

# 7) 📊 STATISTIKA
@dp.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    cursor.execute("SELECT COUNT(*) FROM users"); total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM animes"); total_animes = cursor.fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    day1 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    day2 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date = ?", (today,)); cnt_today = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date = ?", (day1,)); cnt_day1 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date = ?", (day2,)); cnt_day2 = cursor.fetchone()[0]
    
    stat_text = (
        f"👤Obunachilar soni:{total_users}\n"
        f"1kun-{cnt_today}\n"
        f"2kun-{cnt_day1}\n"
        f"3kun-{cnt_day2}\n"
        f"🎥Animelarni soni-{total_animes}"
    )
    await callback.message.answer(stat_text, reply_markup=get_admin_keyboard())
    await callback.answer()

# 9) 🎞 ANIMELAR UCHUN TAHRIRLASH
@dp.callback_query(F.data == "adm_edit")
async def edit_anime_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("🖋 Tahrir qilmoqchi bo'lgan anime kodini yuboring:")
    await state.set_state(AdminStates.edit_select_code)
    await callback.answer()

@dp.message(AdminStates.edit_select_code)
async def edit_code_rec(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    await state.update_data(edit_code=int(message.text))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖋animeni nomi ozgartitish", callback_data="field_title")],
        [InlineKeyboardButton(text="🏞animeni rasmnin ozgtartirish", callback_data="field_photo")],
        [InlineKeyboardButton(text="🖋animeni tavsifni ozgartirish", callback_data="field_desc")]
    ])
    await message.answer("Nimani o'zgartiramiz?", reply_markup=kb)
    await state.set_state(AdminStates.edit_field_choice)

@dp.callback_query(AdminStates.edit_field_choice, F.data.startswith("field_"))
async def edit_field_sel(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[1]
    await state.update_data(edit_field=field)
    await callback.message.answer(f"Yangi qiymatni kiriting/yuboring:")
    await state.set_state(AdminStates.edit_new_value)
    await callback.answer()

@dp.message(AdminStates.edit_new_value)
async def edit_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data['edit_code']
    field = data['edit_field']
    if field == "title": cursor.execute("UPDATE animes SET title = ? WHERE code = ?", (message.text, code))
    elif field == "desc": cursor.execute("UPDATE animes SET description = ? WHERE code = ?", (message.text, code))
    elif field == "photo" and message.photo: cursor.execute("UPDATE animes SET photo_id = ? WHERE code = ?", (message.photo[-1].file_id, code))
    conn.commit()
    await message.answer("✅ Muvaffaqiyatli o'zgartirildi!", reply_markup=get_admin_keyboard())
    await state.clear()

# 9) 🗑 ANIMELARNI O'CHIRISH TUGMASI
@dp.callback_query(F.data == "adm_delete")
async def delete_anime_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("🗑 O'chirib tashlamoqchi bo'lgan anime kodini yuboring:")
    await state.set_state(AdminStates.delete_code)
    await callback.answer()

@dp.message(AdminStates.delete_code)
async def delete_anime_done(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    code = int(message.text)
    cursor.execute("DELETE FROM animes WHERE code = ?", (code,))
    cursor.execute("DELETE FROM episodes WHERE anime_code = ?", (code,))
    conn.commit()
    await message.answer(f"✅ Kod {code} bo'lgan anime butunlay o'chirildi.", reply_markup=get_admin_keyboard())
    await state.clear()

# OBUNA QAYTA TEKSHIRISH
@dp.callback_query(F.data == "check_subs")
async def callback_check_subs(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer(TEXT_WELCOME)
        await callback.message.answer(TEXT_SEND_CODE)
        if callback.from_user.id in ADMIN_IDS: await callback.message.answer("🎛 Boshqarish Paneli:", reply_markup=get_admin_keyboard())
    else: await callback.answer("❌ Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

async def main(): await dp.start_polling(bot)
if __name__ == "__main__": asyncio.run(main())
