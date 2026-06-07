import logging
import asyncio
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# LOGGING SOZLAMALARI
logging.basicConfig(level=logging.INFO)

# BOT TOKEN VA ADMIN ID (O'zingiznikini qo'ying)
BOT_TOKEN = "8340884342:AAHzz_2cEvNbzyQfdCHRHFYuNoBy6Hiumus"
ADMIN_ID = 7164685036  # <--- Bu yerga o'zingizning Telegram ID'ingizni yozing!

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# DB BAZA BILAN ISHLASH
conn = sqlite3.connect("anime_bot.db", check_same_thread=False)
cursor = conn.cursor()

# Jadvallarni yaratish
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, join_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS animes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    code TEXT UNIQUE, 
    name TEXT, 
    desc TEXT, 
    photo TEXT, 
    video TEXT
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    anime_code TEXT, 
    part_num INTEGER, 
    file_id TEXT
)''')
conn.commit()

# FSM STATE'LAR (Bosqichlar)
class AdminStates(StatesGroup):
    add_channel = State()
    # Anime qo'shish bosqichlari
    anime_code = State()
    anime_name = State()
    anime_desc = State()
    anime_photo = State()
    anime_video = State()
    # Qism qo'shish
    episode_code = State()
    episode_file = State()
    # Tahrirlash
    edit_name = State()
    edit_desc = State()
    edit_photo = State()
    edit_code = State()
    # Post tarqatish
    post_text = State()
    # Admin bilan aloqa
    user_report = State()

# MAJBURIY OBUNA TEKSHIRISH FUNKSIYASI
async def check_sub(user_id):
    cursor.execute("SELECT username FROM channels")
    channels = cursor.fetchall()
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

# --- 1) BOSH QARISH BANERI (ADMIN PANEL) ---
def admin_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🎛 Boshqarish baneri")
    builder.button(text="➕ Anime qo'shish")
    builder.button(text="🎬 Qism qo'shish")
    builder.button(text="🗂 Animelarni ro'yxati")
    builder.button(text="🔒 Majburiy kanallar")
    builder.button(text="📊 Statistika")
    builder.button(text="📤 Kanalga post yuborish")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# --- USER INTERFEYSI (XUSH KELIBSIZ) ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    # Statistika uchun foydalanuvchini bazaga qo'shish
    now = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT OR IGNORE INTO users (id, join_date) VALUES (?, ?)", (user_id, now))
    conn.commit()

    if user_id == ADMIN_ID:
        await message.answer("👋 Xush kelibsiz, Admin! Boshqaruv paneli tayyor:", reply_markup=admin_menu())
        return

    # Majburiy obuna tekshirish
    if not await check_sub(user_id):
        cursor.execute("SELECT username FROM channels")
        channels = cursor.fetchall()
        inline_ch = InlineKeyboardBuilder()
        for ch in channels:
            inline_ch.button(text="Obuna bo'lish", url=f"https://t.me/{ch[0].replace('@', '')}")
        inline_ch.button(text="✅ Tekshirish", callback_data="check_sub_status")
        inline_ch.adjust(1)
        await message.answer("🔊 Kanallarga obuna bo'ling, keyin tekshirish tugmasini bosing:", reply_markup=inline_ch.as_markup())
        return

    await message.answer("🔊 Xush kelibsiz! Animeni kodini yuboring:")

@dp.callback_query(F.data == "check_sub_status")
async def check_callback(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Rahmat! Endi anime kodini yuborishingiz mumkin:")
    else:
        await call.answer("❌ Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

# --- 9) ANIME QIDIRISH (KOD ORQALI) ---
@dp.message(F.text & ~F.text.startswith('/'))
async def search_anime(message: types.Message):
    if message.from_user.id == ADMIN_ID and message.text in ["🎛 Boshqarish baneri", "➕ Anime qo'shish", "🎬 Qism qoshish", "🗂 Animelarni ro'yxati", "🔒 Majburiy kanallar", "📊 Statistika", "📤 Kanalga post yuborish"]:
        return # Admin tugmalari bo'lsa qidiruv ishlamasin
        
    if not await check_sub(message.from_user.id):
        await message.answer("❌ Avval kanallarga obuna bo'ling!")
        return

    code = message.text.strip()
    cursor.execute("SELECT * FROM animes WHERE code=?", (code,))
    anime = cursor.fetchone()

    if anime:
        anime_id, a_code, name, desc, photo, video = anime
        text = f"🎬 **{name}**\n\n📝 {desc}\n\n🔢 Kod: `{a_code}`"
        
        # Qismlarni ko'rish tugmasi (8-band: tomosha qilish)
        builder = InlineKeyboardBuilder()
        builder.button(text="🍿 Tomosha qilish (Qismlar)", callback_data=f"view_parts_{a_code}")
        
        if photo:
            await message.answer_photo(photo, caption=text, parse_mode="Markdown", reply_markup=builder.as_markup())
        elif video:
            await message.answer_video(video, caption=text, parse_mode="Markdown", reply_markup=builder.as_markup())
        else:
            await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    else:
        # 10) Admin bilan aloqa taklifi
        builder = InlineKeyboardBuilder()
        builder.button(text="✍️ Admin'ga topilmagan animeni yozish", callback_data="report_anime")
        await message.answer("🔊 Uzr, bunday kodli anime topilmadi, boshqa kodni kiritib ko'ring yoki adminga murojaat qiling:", reply_markup=builder.as_markup())

# --- 8) & 11) QISMLARNI KO'RSATISH ---
@dp.callback_query(F.data.startswith("view_parts_"))
async def view_parts(call: types.CallbackQuery):
    anime_code = call.data.split("_")[2]
    cursor.execute("SELECT part_num, file_id FROM episodes WHERE anime_code=? ORDER BY part_num ASC", (anime_code,))
    episodes = cursor.fetchall()

    if not episodes:
        await call.answer("⚠️ Bu animening qismlari hali yuklanmagan!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for ep in episodes:
        builder.button(text=f"📹 {ep[0]}-qism", callback_data=f"get_ep_{anime_code}_{ep[0]}")
    builder.adjust(2)
    await call.message.reply(f"🎞 Qismlar ro'yxati:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("get_ep_"))
async def get_episode(call: types.CallbackQuery):
    _, _, code, part = call.data.split("_")
    cursor.execute("SELECT file_id FROM episodes WHERE anime_code=? AND part_num=?", (code, part))
    ep = cursor.fetchone()
    if ep:
        await bot.send_video(chat_id=call.from_user.id, video=ep[0], caption=f"🎬 {code} — {part}-qism")
    else:
        await call.answer("Xatolik!")

# --- 10) TOPILMAGAN ANIME HAQIDA ADMINGA YOZISH ---
@dp.callback_query(F.data == "report_anime")
async def report_anime(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.user_report)
    await call.message.answer("✍️ Topa olmagan anime nomini yozing, men adminga yetkazaman:")

@dp.message(AdminStates.user_report)
async def send_report_to_admin(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"⚠️ **Foydalanuvchi anime topa olmadi:**\n👤 Kimdan: {message.from_user.mention()}\n📝 Anime nomi: {message.text}")
    await message.answer("✅ Adminga yuborildi! Tez orada qo'shishga harakat qilamiz.")
    await state.clear()

# --- 2) ANIME QO'SHISH (ADMIN) ---
@dp.message(F.text == "➕ Anime qo'shish", F.from_user.id == ADMIN_ID)
async def add_anime_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.anime_code)
    await message.answer("🔢 Yangi anime uchun unikal KOD kiriting:")

@dp.message(AdminStates.anime_code)
async def add_anime_code(message: types.Message, state: FSMContext):
    await state.update_data(anime_code=message.text.strip())
    await state.set_state(AdminStates.anime_name)
    await message.answer("✒️ Anime NOMINI kiriting:")

@dp.message(AdminStates.anime_name)
async def add_anime_name(message: types.Message, state: FSMContext):
    await state.update_data(anime_name=message.text)
    await state.set_state(AdminStates.anime_desc)
    await message.answer("✒️ Anime uchun TAVSIF (opisanie) kiriting:")

@dp.message(AdminStates.anime_desc)
async def add_anime_desc(message: types.Message, state: FSMContext):
    await state.update_data(anime_desc=message.text)
    await state.set_state(AdminStates.anime_photo)
    await message.answer("🏞 Anime uchun RASM yuboring (Agar rasm bo'lmasa /skip bosing):")

@dp.message(AdminStates.anime_photo)
async def add_anime_photo(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(anime_photo=message.photo[-1].file_id)
        await state.update_data(anime_video=None)
    else:
        await state.update_data(anime_photo=None)
    
    await state.set_state(AdminStates.anime_video)
    await message.answer("🎬 Anime uchun PREVIEW VIDEO yuboring (Agar video bo'lmasa /skip bosing):")

@dp.message(AdminStates.anime_video)
async def add_anime_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_id = message.video.file_id if message.video else None
    
    cursor.execute("INSERT OR REPLACE INTO animes (code, name, desc, photo, video) VALUES (?, ?, ?, ?, ?)",
                   (data['anime_code'], data['anime_name'], data['anime_desc'], data['anime_photo'], video_id))
    conn.commit()
    
    await message.answer(f"✅ Anime muvaffaqiyatli saqlandi!\nKod: {data['anime_code']}", reply_markup=admin_menu())
    await state.clear()

# --- 11) QISM QO'SHISH FUNKSIYASI ---
@dp.message(F.text == "🎬 Qism qo'shish", F.from_user.id == ADMIN_ID)
async def add_episode_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.episode_code)
    await message.answer("🔢 Qaysi anime kodiga qism qo'shmoqchisiz? Kodni kiriting:")

@dp.message(AdminStates.episode_code)
async def add_episode_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    cursor.execute("SELECT id FROM animes WHERE code=?", (code,))
    if not cursor.fetchone():
        await message.answer("❌ Bunday anime kodi topilmadi! Qaytadan kiriting:")
        return
    
    cursor.execute("SELECT COUNT(id) FROM episodes WHERE anime_code=?", (code,))
    next_part = cursor.fetchone()[0] + 1
    
    await state.update_data(ep_code=code, next_part=next_part)
    await state.set_state(AdminStates.episode_file)
    await message.answer(f"🎞 **{next_part}-qism**ni (Video formatida) yuboring:")

@dp.message(AdminStates.episode_file, F.video)
async def add_episode_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data['ep_code']
    part = data['next_part']
    
    cursor.execute("INSERT INTO episodes (anime_code, part_num, file_id) VALUES (?, ?, ?)", (code, part, message.video.file_id))
    conn.commit()
    
    next_part = part + 1
    await state.update_data(next_part=next_part)
    await message.answer(f"✅ {part}-qism saqlandi!\n\n🎞 Endi **{next_part}-qism**ni yuboring (To'xtatish uchun /cancel bosing):")

# --- 3) ANIMELAR RO'YXATI VA TAHRIRLASH ---
@dp.message(F.text == "🗂 Animelarni ro'yxati", F.from_user.id == ADMIN_ID)
async def list_animes(message: types.Message):
    cursor.execute("SELECT code, name FROM animes")
    animes = cursor.fetchall()
    if not animes:
        await message.answer("Bazada animelar yo'q.")
        return
    
    builder = InlineKeyboardBuilder()
    for anime in animes:
        builder.button(text=f"🎬 {anime[1]}", callback_data=f"manage_{anime[0]}")
    builder.adjust(1)
    await message.answer("🗂 Boshqarish va tahrirlash uchun animeni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("manage_"))
async def manage_anime(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    builder = InlineKeyboardBuilder()
    builder.button(text="✒️ Nomini o'zgartirish", callback_data=f"edit_name_{code}")
    builder.button(text="🏞 Rasmini o'zgartirish", callback_data=f"edit_photo_{code}")
    builder.button(text="✒️ Tavsifni o'zgartirish", callback_data=f"edit_desc_{code}")
    builder.button(text="✒️ Kodni o'zgartirish", callback_data=f"edit_code_{code}")
    builder.button(text="🗑 O'chirish", callback_data=f"delete_{code}")
    builder.adjust(2)
    await call.message.answer(f"⚙️ Kod: `{code}` uchun harakatni tanlang:", reply_markup=builder.as_markup())

# (O'chirish amali)
@dp.callback_query(F.data.startswith("delete_"))
async def delete_anime(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    cursor.execute("DELETE FROM animes WHERE code=?", (code,))
    cursor.execute("DELETE FROM episodes WHERE anime_code=?", (code,))
    conn.commit()
    await call.message.edit_text("🗑 Anime va uning hamma qismlari bazadan o'chirildi!")

# Tahrirlash boshlanishi (Nom)
@dp.callback_query(F.data.startswith("edit_name_"))
async def edit_name_start(call: types.CallbackQuery, state: FSMContext):
    code = call.data.split("_")[2]
    await state.update_data(edit_code=code)
    await state.set_state(AdminStates.edit_name)
    await call.message.answer("✏️ Yangi nomni yuboring:")

@dp.message(AdminStates.edit_name)
async def edit_name_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE animes SET name=? WHERE code=?", (message.text, data['edit_code']))
    conn.commit()
    await message.answer("✅ Nomi yangilandi!", reply_markup=admin_menu())
    await state.clear()

# --- 6) MAJBURIY KANALLAR (KO'P KANAL QO'SHISH) ---
@dp.message(F.text == "🔒 Majburiy kanallar", F.from_user.id == ADMIN_ID)
async def manage_channels(message: types.Message):
    cursor.execute("SELECT username FROM channels")
    channels = cursor.fetchall()
    text = "🔒 **Majburiy obuna kanallari:**\n\n"
    builder = InlineKeyboardBuilder()
    
    for ch in channels:
        text += f"🔹 {ch[0]}\n"
        builder.button(text=f"❌ O'chirish {ch[0]}", callback_data=f"del_ch_{ch[0]}")
    
    builder.button(text="➕ Kanal qo'shish", callback_data="add_ch_start")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "add_ch_start")
async def add_ch_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_channel)
    await call.message.answer("📢 Kanal usernamesini yuboring (Masalan: @kanal_ nomi):")

@dp.message(AdminStates.add_channel)
async def add_channel_save(message: types.Message, state: FSMContext):
    username = message.text.strip()
    if not username.startswith("@"):
        username = "@" + username
    cursor.execute("INSERT OR IGNORE INTO channels (username) VALUES (?)", (username,))
    conn.commit()
    await message.answer(f"✅ {username} majburiy kanallarga qo'shildi!", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_channel(call: types.CallbackQuery):
    username = call.data.replace("del_ch_", "")
    cursor.execute("DELETE FROM channels WHERE username=?", (username,))
    conn.commit()
    await call.message.edit_text(f"❌ {username} ro'yxatdan o'chirildi!")

# --- 7) STATISTIKA KUNLIK VA UMUMIY ---
@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def show_stats(message: types.Message):
    cursor.execute("SELECT COUNT(id) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(id) FROM animes")
    total_animes = cursor.fetchone()[0]
    
    # Kunlarni hisoblash
    now = datetime.now()
    d1 = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    d3 = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    d7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    cursor.execute("SELECT COUNT(id) FROM users WHERE join_date >= ?", (d1,))
    k1 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM users WHERE join_date >= ?", (d3,))
    k3 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(id) FROM users WHERE join_date >= ?", (d7,))
    k7 = cursor.fetchone()[0]

    stats_text = (
        f"📊 **Bot Statistikasi:**\n\n"
        f"👤 Obunachilar soni — {total_users}\n"
        f"  └ 1 kun — {k1}\n"
        f"  └ 3 kun — {k3}\n"
        f"  └ 7 kun — {k7}\n\n"
        f"🎞 Animelar soni — {total_animes}"
    )
    await message.answer(stats_text, parse_mode="Markdown")

# --- 13) KANALGA POST YUBORISH (KOD ORQALI POST) ---
@dp.message(F.text == "📤 Kanalga post yuborish", F.from_user.id == ADMIN_ID)
async def send_post_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.post_text)
    await message.answer("📝 Kanalga yuboriladigan post matnini yoki anime kodini kiriting:")

@dp.message(AdminStates.post_text)
async def send_post_finish(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    # Agar adminga shunchaki kod yuborilsa, o'sha animeni topib chiroyli post qiladi
    cursor.execute("SELECT name, code FROM animes WHERE code=?", (text,))
    anime = cursor.fetchone()
    
    builder = InlineKeyboardBuilder()
    if anime:
        post_content = f"🎬 **{anime[0]}** animesining yangi qismlari joylandi!\n\n🤖 Botga kirib ` {anime[1]} ` kodini yuboring va tomosha qiling."
        builder.button(text="🍿 Tomosha qilish", url=f"https://t.me/{(await bot.get_me()).username}?start=true")
    else:
        post_content = text
        builder.button(text="🍿 Tomosha qilish", url=f"https://t.me/{(await bot.get_me()).username}?start=true")

    # Barcha foydalanuvchilarga tarqatish
    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()
    
    success = 0
    for u in users:
        try:
            await bot.send_message(chat_id=u[0], text=post_content, parse_mode="Markdown", reply_markup=builder.as_markup())
            success += 1
        except Exception:
            pass
            
    await message.answer(f"🚀 Post {success} ta foydalanuvchiga muvaffaqiyatli yuborildi!", reply_markup=admin_menu())
    await state.clear()

# Global cancel komandasi
@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Harakat bekor qilindi.", reply_markup=admin_menu() if message.from_user.id == ADMIN_ID else None)

# BOTNI ISHGA TUSHIRISH
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
