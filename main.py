import os
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# LOGGING & SOZLAMALAR
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8869934360:AAF0GLfrwS5oiTJDzunDW-Mb23idr5c-hng"  # Bot tokeningizni kiriting
ADMIN_ID = 7164685036  # O'zingizning Telegram ID'ingizni kiriting

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# FLASK (Render 24/7 ishlashi uchun)
app = Flask('')

@app.route('/')
def home():
    return "Bot status: Active"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# BAZA BILAN ISHLASH (SQLite)
def init_db():
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    # Foydalanuvchilar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY, 
                        join_date TEXT)''')
    # Animelar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS animes (
                        code TEXT PRIMARY KEY, 
                        name TEXT, 
                        photo TEXT, 
                        description TEXT)''')
    # Qismlar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS episodes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        anime_code TEXT, 
                        ep_number INTEGER, 
                        file_id TEXT)''')
    # Majburiy kanallar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (
                        url TEXT PRIMARY KEY, 
                        chat_id TEXT)''')
    conn.commit()
    conn.close()

init_db()

# FSM STATE-LAR (Holatlar)
class AdminStates(StatesGroup):
    add_anime_code = State()
    add_anime_name = State()
    add_anime_photo = State()
    add_anime_desc = State()
    
    add_episode_video = State()
    
    edit_name = State()
    edit_photo = State()
    edit_desc = State()
    edit_code = State()
    
    add_channel_url = State()
    add_channel_id = State()
    
    post_text = State()
    post_inline = State()
    
    user_request = State()

# TUGMALAR (KEYBOARDS)
def get_admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎛 Boshqarish paneli")]
    ], resize_keyboard=True)

def get_panel_markup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="panel_add_anime"),
         InlineKeyboardButton(text="🗂 Animelar ro'yxati", callback_data="panel_list_anime")],
        [InlineKeyboardButton(text="🔒 Majburiy kanallar", callback_data="panel_channels"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="panel_stats")],
        [InlineKeyboardButton(text="📤 Kanalga post", callback_data="panel_send_post")]
    ])

# MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI
async def check_subscription(user_id):
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT url, chat_id FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    not_subscribed = []
    for url, chat_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append((url, chat_id))
        except Exception:
            # Agar bot kanalda admin bo'lmasa yoki xato bo'lsa
            pass
    return not_subscribed

# ---- USER QISMI ----

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user_id
    
    # Bazaga foydalanuvchini qo'shish
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (user_id, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

    # Majburiy obunani tekshirish
    not_subbed = await check_subscription(user_id)
    if not_subbed:
        buttons = [[InlineKeyboardButton(text="Obuna bo'lish", url=url)] for url, _ in not_subbed]
        buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("🔊 Kanallarga obuna bo'ling, tekshirish tugmasini bosing:", reply_markup=markup)
        return

    if user_id == ADMIN_ID:
        await message.answer("Xush kelibsiz! Anime kodini yuboring:", reply_markup=get_admin_menu())
    else:
        await message.answer("Xush kelibsiz! Anime kodini yuboring:")

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery):
    not_subbed = await check_subscription(call.from_user.id)
    if not_subbed:
        await call.answer("Uzur, hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        await call.message.answer("Rahmat! Endi anime kodini yuborishingiz mumkin.")

# ANIME QIDIRISH (KOD ORQALI)
@dp.message(F.text & ~F.text.startswith('/'))
async def search_anime(message: types.Message, state: FSMContext):
    if message.text == "🎛 Boshqarish paneli" and message.from_user.id == ADMIN_ID:
        await message.answer("Boshqaruv paneli:", reply_markup=get_panel_markup())
        return

    user_id = message.from_user.id
    not_subbed = await check_subscription(user_id)
    if not_subbed:
        buttons = [[InlineKeyboardButton(text="Obuna bo'lish", url=url)] for url, _ in not_subbed]
        buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
        await message.answer("🔊 Kanallarga obuna bo'ling, tekshirish tugmasini bosing:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    code = message.text.strip()
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, photo, description FROM animes WHERE code=?", (code,))
    anime = cursor.fetchone()
    
    if anime:
        name, photo, desc = anime
        cursor.execute("SELECT ep_number, file_id FROM episodes WHERE anime_code=? ORDER BY ep_number ASC", (code,))
        episodes = cursor.fetchall()
        conn.close()
        
        caption = f"🎬 **{name}**\n\n📝 Tavsif: {desc}\n🔢 Kodi: {code}"
        
        # Qismlar tugmalari
        buttons = []
        row = []
        for ep_num, file_id in episodes:
            row.append(InlineKeyboardButton(text=f"{ep_num}-qism", callback_data=f"play_{code}_{ep_num}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        if photo and photo != "Yo'q":
            await message.answer_photo(photo=photo, caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        else:
            await message.answer(text=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        conn.close()
        # Topilmagan holat uchun admin bilan aloqa tugmasi
        btn = [[InlineKeyboardButton(text="⭐️ Adminga murojaat", callback_data="req_admin")]]
        await message.answer("🔊 Uzur, anime topilmadi, boshqa kod kiritib ko'ring yoki adminga yozing.", reply_markup=InlineKeyboardMarkup(inline_keyboard=btn))

@dp.callback_query(F.data.startswith("play_"))
async def play_episode(call: types.CallbackQuery):
    _, code, ep_num = call.data.split("_")
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM episodes WHERE anime_code=? AND ep_number=?", (code, int(ep_num)))
    ep = cursor.fetchone()
    conn.close()
    
    if ep:
        await bot.send_video(chat_id=call.from_user.id, video=ep[0], caption=f"🎬 {ep_num}-qism")
        await call.answer()
    else:
        await call.answer("Qism topilmadi!", show_alert=True)

# ADMIN BILAN ALOQA (10-BAND)
@dp.callback_query(F.data == "req_admin")
async def req_admin(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Qidirayotgan anime nomingizni yozib qoldiring. Admin tez orada ko'rib chiqadi:")
    await state.set_state(AdminStates.user_request)
    await call.answer()

@dp.message(AdminStates.user_request)
async def user_request_send(message: types.Message, state: FSMContext):
    await bot.send_message(chat_id=ADMIN_ID, text=f"⭐️ **Topilmagan anime so'rovi:**\nFoydalanuvchi: {message.from_user.full_name} (ID: {message.from_user.id})\nNomi: {message.text}")
    await message.answer("Xabaringiz adminga yetkazildi. Rahmat!")
    await state.clear()

# ---- ADMIN PANEL FUNKSIYALARI ----

@dp.callback_query(F.data == "panel_stats")
async def show_stats(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    
    # Obunachilar soni
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    # 1, 3, 7 kunlik statistika
    today = datetime.now()
    d1 = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    d3 = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    d7 = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (d1,))
    u1 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (d3,))
    u3 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (d7,))
    u7 = cursor.fetchone()[0]
    
    # Animelar soni
    cursor.execute("SELECT COUNT(*) FROM animes")
    total_anime = cursor.fetchone()[0]
    conn.close()
    
    txt = f"📊 **Statistika:**\n\n👤 Obunachilar soni: {total_users}\n 1 kun: {u1}\n 3 kun: {u3}\n 7 kun: {u7}\n🎞 Animelar soni: {total_anime}"
    await call.message.edit_text(txt, reply_markup=get_panel_markup())

# ANIME QO'SHISH (2-BAND)
@dp.callback_query(F.data == "panel_add_anime")
async def add_anime_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.answer("Yangi animening KODINI kiriting:")
    await state.set_state(AdminStates.add_anime_code)
    await call.answer()

@dp.message(AdminStates.add_anime_code)
async def add_anime_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Anime NOMINI kiriting:")
    await state.set_state(AdminStates.add_anime_name)

@dp.message(AdminStates.add_anime_name)
async def add_anime_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Anime uchun rasm (Photo) yuboring, rasm bo'lmasa 'Yo'q' deb yozing:")
    await state.set_state(AdminStates.add_anime_photo)

@dp.message(AdminStates.add_anime_photo)
async def add_anime_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(photo=message.photo[-1].file_id)
    else:
        await state.update_data(photo="Yo'q")
    await message.answer("Anime uchun TAVSIF (opisanie) kiriting:")
    await state.set_state(AdminStates.add_anime_desc)

@dp.message(AdminStates.add_anime_desc)
async def add_anime_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO animes VALUES (?, ?, ?, ?)", (data['code'], data['name'], data['photo'], message.text))
        conn.commit()
        await message.answer(f"✅ Anime yaratildi!\nKodi: {data['code']}\nNomi: {data['name']}\n\nEndi qismlarni qo'shishni boshlashingiz mumkin.", reply_markup=get_panel_markup())
    except sqlite3.IntegrityError:
        await message.answer("❌ Bu kodli anime allaqachon mavjud!", reply_markup=get_panel_markup())
    conn.close()
    await state.clear()

# ANIMELAR RO'YXATI VA BOSHQARUV (3-BAND)
@dp.callback_query(F.data == "panel_list_anime")
async def list_anime(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT code, name FROM animes")
    animes = cursor.fetchall()
    conn.close()
    
    if not animes:
        await call.message.edit_text("Hozircha animelar yo'q.", reply_markup=get_panel_markup())
        return
        
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"manage_{code}")] for code, name in animes]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_panel")])
    await call.message.edit_text("🗂 Kerakli animeni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_anime(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM animes WHERE code=?", (code,))
    anime = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_code=?", (code,))
    ep_count = cursor.fetchone()[0]
    conn.close()
    
    if not anime: return
    
    buttons = [
        [InlineKeyboardButton(text="🎬 Qism qo'shish", callback_data=f"addep_{code} ({ep_count+1}-qism)")],
        [InlineKeyboardButton(text="✒️ Nomni o'zgartirish", callback_data=f"edit_name_{code}"),
         InlineKeyboardButton(text="🏞 Rasmni o'zgartirish", callback_data=f"edit_photo_{code}")],
        [InlineKeyboardButton(text="✒️ Tavsifni o'zgartirish", callback_data=f"edit_desc_{code}"),
         InlineKeyboardButton(text="✒️ Kodni o'zgartirish", callback_data=f"edit_code_{code}")],
        [InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data=f"del_anime_{code}")],
        [InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data="panel_list_anime")]
    ]
    await call.message.edit_text(f"Anime: {anime[0]}\nKodi: {code}\nJoriy qismlar soni: {ep_count}", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# 11-BAND: QISM QO'SHISH (BITTAM-BITTA SAQLASH)
@dp.callback_query(F.data.startswith("addep_"))
async def add_episode_start(call: types.CallbackQuery, state: FSMContext):
    code = call.data.split("_")[1].split(" ")[0]
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_code=?", (code,))
    next_ep = cursor.fetchone()[0] + 1
    conn.close()
    
    await state.update_data(anime_code=code, next_ep=next_ep)
    await call.message.answer(f"📹 {next_ep}-qism videosini yuboring:")
    await state.set_state(AdminStates.add_episode_video)
    await call.answer()

@dp.message(AdminStates.add_episode_video, F.video)
async def add_episode_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data['anime_code']
    ep_num = data['next_ep']
    
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO episodes (anime_code, ep_number, file_id) VALUES (?, ?, ?)", (code, ep_num, message.video.file_id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ {ep_num}-qism saqlandi!")
    
    # Avtomatik keyingi qismga o'tkazish
    next_ep = ep_num + 1
    await state.update_data(next_ep=next_ep)
    await message.answer(f"📹 Keyingi: {next_ep}-qism videosini yuboring. To'xtatish uchun /start bosing.")

# O'CHIRISH VA O'ZGARTIRISHLAR
@dp.callback_query(F.data.startswith("del_anime_"))
async def delete_anime(call: types.CallbackQuery):
    code = call.data.split("_")[2]
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM animes WHERE code=?", (code,))
    cursor.execute("DELETE FROM episodes WHERE anime_code=?", (code,))
    conn.commit()
    conn.close()
    await call.answer("Anime va uning barcha qismlari o'chirildi!", show_alert=True)
    await list_anime(call)

# TAHRIRLASH STATE-LARIGA O'TISH
@dp.callback_query(F.data.startswith("edit_"))
async def edit_anime_fields(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    field = parts[1]
    code = parts[2]
    await state.update_data(edit_code=code)
    
    if field == "name":
        await call.message.answer("Yangi nomni yuboring:")
        await state.set_state(AdminStates.edit_name)
    elif field == "photo":
        await call.message.answer("Yangi rasm yuboring:")
        await state.set_state(AdminStates.edit_photo)
    elif field == "desc":
        await call.message.answer("Yangi tavsifni yuboring:")
        await state.set_state(AdminStates.edit_desc)
    elif field == "code":
        await call.message.answer("Yangi KOD kiriting:")
        await state.set_state(AdminStates.edit_code)
    await call.answer()

@dp.message(AdminStates.edit_name)
async def save_edit_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE animes SET name=? WHERE code=?", (message.text, data['edit_code']))
    conn.commit() ; conn.close()
    await message.answer("✅ Nomi o'zgartirildi!", reply_markup=get_panel_markup())
    await state.clear()

# MAJBURIY KANALLAR BOSHQARUVI (6-BAND)
@dp.callback_query(F.data == "panel_channels")
async def manage_channels(call: types.CallbackQuery):
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM channels")
    ch_list = cursor.fetchall()
    conn.close()
    
    txt = "🔒 **Majburiy kanallar ro'yxati:**\n\n"
    buttons = []
    for row in ch_list:
        txt += f"🔹 {row[0]}\n"
        buttons.append([InlineKeyboardButton(text=f"❌ {row[0]} o'chirish", callback_data=f"del_ch_{row[0]}")])
        
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_panel")])
    await call.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal havolasini yuboring (Masalan: https://t.me/kanal_link):")
    await state.set_state(AdminStates.add_channel_url)
    await call.answer()

@dp.message(AdminStates.add_channel_url)
async def add_ch_url(message: types.Message, state: FSMContext):
    await state.update_data(ch_url=message.text.strip())
    await message.answer("Kanal ID-sini yuboring (Masalan: -100123456789, bot kanalda admin bo'lishi shart):")
    await state.set_state(AdminStates.add_channel_id)

@dp.message(AdminStates.add_channel_id)
async def add_ch_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO channels VALUES (?, ?)", (data['ch_url'], message.text.strip()))
        conn.commit()
        await message.answer("✅ Kanal qo'shildi!", reply_markup=get_panel_markup())
    except sqlite3.IntegrityError:
        await message.answer("Bu kanal allaqachon bor.", reply_markup=get_panel_markup())
    conn.close()
    await state.clear()

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_channel(call: types.CallbackQuery):
    url = call.data.replace("del_ch_", "")
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE url=?", (url,))
    conn.commit() ; conn.close()
    await call.answer("Kanal o'chirildi!", show_alert=True)
    await manage_channels(call)

# KANALGA POST YUBORISH (8-BAND - "TOMOSHA QILISH" TUGMASI BILAN)
@dp.callback_query(F.data == "panel_send_post")
async def post_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Kanalga yuboriladigan post matni yoki rasmini yuboring:")
    await state.set_state(AdminStates.post_text)
    await call.answer()

@dp.message(AdminStates.post_text)
async def post_text_get(message: types.Message, state: FSMContext):
    await state.update_data(text=message.html_text)
    await message.answer("Ushbu post ostidagi 'Tomosha qilish' tugmasi bosilganda ochiladigan bot havolasini yuboring\n(Masalan: `https://t.me/bot_nomi?start=anime_kodi`):")
    await state.set_state(AdminStates.post_inline)

@dp.message(AdminStates.post_inline)
async def post_send_chan(message: types.Message, state: FSMContext):
    data = await state.get_data()
    url = message.text.strip()
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Tomosha qilish", url=url)]
    ])
    
    conn = sqlite3.connect('anime_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    count = 0
    for ch in channels:
        try:
            await bot.send_message(chat_id=ch[0], text=data['text'], reply_markup=markup, parse_mode="HTML")
            count += 1
        except Exception:
            pass
            
    await message.answer(f"✅ Post {count} ta kanalga muvaffaqiyatli yuborildi!", reply_markup=get_panel_markup())
    await state.clear()

# PANELGA QAYTISH
@dp.callback_query(F.data == "back_to_panel")
async def back_to_panel(call: types.CallbackQuery):
    await call.message.edit_text("Boshqaruv paneli:", reply_markup=get_panel_markup())

# ASOSIY ISHGA TUSHIRISH (MAIN)
async def main():
    # Flask serverni alohida oqimda ishga tushirish
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Telegram botni polling qilish
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
