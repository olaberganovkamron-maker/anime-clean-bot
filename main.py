import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, html, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# 🤖 BOT SOZLAMALARI
# ⚠️ Token oxiridagi qo'shtirnoq yopildi (Render'dagi xatolik tuzatildi)
TOKEN= "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_IDS = [7164685036, 7164685036, 7164685036]  # Shu yerga o'zingiz va 2 ta admin ID'sini yozing

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 📊 BAZANI SOZLASH
conn = sqlite3.connect("anime_bot.db")
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, join_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS animes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, title TEXT, desc TEXT, image TEXT, downloads INTEGER DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, anime_id INTEGER, ep_num INTEGER, file_id TEXT)''')
conn.commit()

# FSM (Holatlar)
class AnimeStates(StatesGroup):
    add_code = State()
    add_title = State()
    add_desc = State()
    add_image = State()
    add_episodes = State()
    search = State()
    edit_title = State()
    edit_desc = State()
    edit_image = State()
    edit_code = State()
    post_channel = State()

# ⌨ BOSHQARUV BANERLARI
def get_main_keyboard(user_id):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔍 Anime Qidirish")]], resize_keyboard=True)
    if user_id in ADMIN_IDS:
        kb.keyboard.append([KeyboardButton(text="➕ Anime Qo'shish"), KeyboardButton(text="🗂 Animelar Ro'yxati")])
        kb.keyboard.append([KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📤 Kanalga Post")])
    return kb

# 🎬 XUSH KELIBSIZ MATNLARI VA START
@dp.message(F.text == "/start")
async def start_cmd(message: Message):
    user_id = message.from_user.id
    
    # Foydalanuvchini bazaga qo'shish
    cursor.execute("INSERT OR IGNORE INTO users (id, join_date) VALUES (?, ?)", (user_id, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    
    # Deep linking orqali kod bilan kirganda avtomatik qidirish (Kanal uchun)
    args = message.text.split()
    if len(args) > 1:
        anime_code = args[1]
        message.text = anime_code
        await search_anime(message)
        return

    welcome_text = (
        f"👋 Xush kelibsiz, **{message.from_user.first_name}**!\n\n"
        "✨ `Miraziz Anime` olamiga xush kelibsiz! 🎉\n"
        "Bu yerda siz eng sara va eng so'nggi anime qismlarini topishingiz mumkin.\n\n"
        "👇 Botdan foydalanish uchun quyidagi tugmalardan foydalaning yoki "
        "to'g'ridan-to'g'ri **Anime kodini yoki nomini** yozib yuboring!"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

# 📊 STATISTIKA (Bugun, 3 kun, 7 kun)
@dp.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    
    now = datetime.now()
    day1 = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    day3 = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    day7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (day1,))
    u1 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (day3,))
    u3 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (day7,))
    u7 = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM animes")
    total_animes = cursor.fetchone()[0]
    
    text = (
        "📊 **Bot Statistikasi:**\n\n"
        f"👤 **Umumiy obunachilar:** {total_users}\n"
        f"📅 1 Kunlik: {u1}\n"
        f"📅 3 Kunlik: {u3}\n"
        f"📅 7 Kunlik: {u7}\n\n"
        f"🎬 **Umumiy Animelar soni:** {total_animes} ta"
    )
    await message.answer(text, parse_mode="Markdown")

# ➕ ANIME QO'SHISH KETMA-KETLIGI (Infinity qismlar)
@dp.message(F.text == "➕ Anime Qo'shish")
async def add_anime_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await message.answer("✏ Anime uchun **unikal kod** kiriting (masalan: 102):")
    await state.set_state(AnimeStates.add_code)

@dp.message(AnimeStates.add_code)
async def process_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text)
    await message.answer("📝 Anime **nomini** kiriting:")
    await state.set_state(AnimeStates.add_title)

@dp.message(AnimeStates.add_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("🎞 Anime uchun **tavsif (opisaniya)** kiriting:")
    await state.set_state(AnimeStates.add_desc)

@dp.message(AnimeStates.add_desc)
async def process_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("🌄 Anime muqovasi uchun **Rasm** yoki **Video** yuboring:")
    await state.set_state(AnimeStates.add_image)

@dp.message(AnimeStates.add_image)
async def process_image(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else None)
    if not file_id:
        await message.answer("⚠️ Iltimos, faqat rasm yoki video yuboring!")
        return
    
    data = await state.get_data()
    try:
        cursor.execute("INSERT INTO animes (code, title, desc, image) VALUES (?, ?, ?, ?)", 
                       (data['code'], data['title'], data['desc'], file_id))
        conn.commit()
        anime_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        await message.answer("❌ Bu kod oldin ishlatilgan! Boshqa kod kiriting.")
        await state.set_state(AnimeStates.add_code)
        return
    
    await state.update_data(anime_id=anime_id, ep_num=1)
    await message.answer("✅ Anime asosiy ma'lumotlari saqlandi!\n\n♾ Endi qismlarni yuboring.\n➡️ **1-qismni yuboring:**")
    await state.set_state(AnimeStates.add_episodes)

@dp.message(AnimeStates.add_episodes, F.video)
async def process_episodes(message: Message, state: FSMContext):
    data = await state.get_data()
    anime_id = data['anime_id']
    ep_num = data['ep_num']
    
    cursor.execute("INSERT INTO episodes (anime_id, ep_num, file_id) VALUES (?, ?, ?)", (anime_id, ep_num, message.video.file_id))
    conn.commit()
    
    next_ep = ep_num + 1
    await state.update_data(ep_num=next_ep)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 Tugatish", callback_data="finish_add")]])
    await message.answer(f"✅ {ep_num}-qism yuklandi!\n\n➡️ Endi esa **{next_ep}-qismni yuboring** (Yoki tugatish uchun pastdagi tugmani bosing):", reply_markup=kb)

@dp.callback_query(F.data == "finish_add")
async def finish_adding(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("🎉 Hamma qismlar muvaffaqiyatli yuklandi va yakunlandi!", reply_markup=get_main_keyboard(call.from_user.id))
    await call.answer()

# 🗂 ANIMELAR RO'YXATI VA BOSHQARISH
@dp.message(F.text == "🗂 Animelar Ro'yxati")
async def list_animes(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    cursor.execute("SELECT id, title, code gloom FROM animes")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("🗂 Hozircha animelar yo'q.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{row[1]} [{row[2]}]", callback_data=f"manage_{row[0]}")])
    await message.answer("🔧 Boshqarish uchun animeni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("manage_"))
async def manage_anime(call: CallbackQuery):
    anime_id = int(call.data.split("_")[1])
    cursor.execute("SELECT id, code, title, desc, downloads FROM animes WHERE id=?", (anime_id,))
    anime = cursor.fetchone()
    
    text = f"🎬 **Nomi:** {anime[2]}\n🔑 **Kodi:** {anime[1]}\n📝 **Tavsif:** {anime[3]}\n📥 **Yuklab olishlar soni:** {anime[4]}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✒ Nomni o'zgartirish", callback_data=f"edit_title_{anime_id}"), InlineKeyboardButton(text="✏ Kodni o'zgartirish", callback_data=f"edit_code_{anime_id}")],
        [InlineKeyboardButton(text="🌄 Rasmini o'zgartirish", callback_data=f"edit_img_{anime_id}"), InlineKeyboardButton(text="🎞 Tavsifni o'zgartirish", callback_data=f"edit_desc_{anime_id}")],
        [InlineKeyboardButton(text="🗑 Animeni o'chirish", callback_data=f"delete_{anime_id}")]
    ])
    await call.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("delete_"))
async def delete_anime(call: CallbackQuery):
    anime_id = int(call.data.split("_")[1])
    cursor.execute("DELETE FROM animes WHERE id=?", (anime_id,))
    cursor.execute("DELETE FROM episodes WHERE anime_id=?", (anime_id,))
    conn.commit()
    await call.message.answer("🗑 Anime va uning hamma qismlari o'chirib tashlandi!")
    await call.answer()

@dp.callback_query(F.data.startswith("edit_"))
async def edit_fields(call: CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    anime_id = int(call.data.split("_")[2])
    await state.update_data(edit_anime_id=anime_id)
    
    if action == "title":
        await call.message.answer("✏ Yangi nomni yuboring:")
        await state.set_state(AnimeStates.edit_title)
    elif action == "code":
        await call.message.answer("🔑 Yangi kodni yuboring:")
        await state.set_state(AnimeStates.edit_code)
    elif action == "desc":
        await call.message.answer("🎞 Yangi tavsifni yuboring:")
        await state.set_state(AnimeStates.edit_desc)
    elif action == "img":
        await call.message.answer("🌄 Yangi rasm/video yuboring:")
        await state.set_state(AnimeStates.edit_image)
    await call.answer()

@dp.message(AnimeStates.edit_title)
async def save_title(message: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE animes SET title=? WHERE id=?", (message.text, data['edit_anime_id']))
    conn.commit()
    await message.answer("✅ Nomi o'zgartirildi!")
    await state.clear()

@dp.message(AnimeStates.edit_code)
async def save_code(message: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE animes SET code=? WHERE id=?", (message.text, data['edit_anime_id']))
    conn.commit()
    await message.answer("✅ Kodi o'zgartirildi!")
    await state.clear()

@dp.message(AnimeStates.edit_desc)
async def save_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE animes SET desc=? WHERE id=?", (message.text, data['edit_anime_id']))
    conn.commit()
    await message.answer("✅ Tavsifi o'zgartirildi!")
    await state.clear()

@dp.message(AnimeStates.edit_image)
async def save_img(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id if message.photo else (message.video.file_id if message.video else None)
    data = await state.get_data()
    cursor.execute("UPDATE animes SET image=? WHERE id=?", (file_id, data['edit_anime_id']))
    conn.commit()
    await message.answer("✅ Rasmi/Videosi o'zgartirildi!")
    await state.clear()

# 🔍 ANIME QIDIRISH
@dp.message(F.text == "🔍 Anime Qidirish")
async def search_start(message: Message, state: FSMContext):
    await message.answer("🔍 Qidirmoqchi bo'lgan anime **nomini** yoki **kodini** kiriting:")
    await state.set_state(AnimeStates.search)

@dp.message(AnimeStates.search)
@dp.message(F.text) 
async def search_anime(message: Message, state: FSMContext = None):
    query = message.text
    if state: await state.clear()
        
    cursor.execute("SELECT id, code, title, desc, image FROM animes WHERE code=? OR title LIKE ?", (query, f"%{query}%"))
    anime = cursor.fetchone()
    
    if not anime:
        await message.answer("❌ Anime kodi yoki nomi topilmadi. Iltimos boshqa kod yoki nom kiriting yoki muammo bo'lsa admin bilan bog'laning! ✨")
        return
    
    anime_id, code, title, desc, image = anime
    
    cursor.execute("SELECT ep_num FROM episodes WHERE anime_id=?", (anime_id,))
    episodes = cursor.fetchall()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for ep in episodes:
        row.append(InlineKeyboardButton(text=f"{ep[0]}-Qism", callback_data=f"getep_{anime_id}_{ep[0]}"))
        if len(row) == 4:
            kb.inline_keyboard.append(row)
            row = []
    if row: kb.inline_keyboard.append(row)
    
    caption = f"🎬 **{title}**\n🔑 Kod: `{code}`\n\n🎞 **Tavsif:** {desc}"
    
    try:
        await message.answer_photo(photo=image, caption=caption, reply_markup=kb, parse_mode="Markdown")
    except:
        try:
            await message.answer_video(video=image, caption=caption, reply_markup=kb, parse_mode="Markdown")
        except:
            await message.answer(caption, reply_markup=kb, parse_mode="Markdown")

# 📥 QISMLARNI YUKLASH (COUNTER +1)
@dp.callback_query(F.data.startswith("getep_"))
async def get_episode(call: CallbackQuery):
    _, anime_id, ep_num = call.data.split("_")
    
    cursor.execute("SELECT file_id FROM episodes WHERE anime_id=? AND ep_num=?", (anime_id, ep_num))
    ep = cursor.fetchone()
    
    if ep:
        cursor.execute("UPDATE animes SET downloads = downloads + 1 WHERE id=?", (anime_id,))
        conn.commit()
        await call.message.answer_video(video=ep[0], caption=f"🎬 {ep_num}-qism. Tomoshingiz xayrli bo'lsin!")
    else:
        await call.message.answer("⚠️ Bu qism topilmadi.")
    await call.answer()

# 📤 KANALGA POST YUBORISH
@dp.message(F.text == "📤 Kanalga Post")
async def post_channel_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await message.answer("Kanalga yuboriladigan post uchun anime **kodini** kiriting:")
    await state.set_state(AnimeStates.post_channel)

@dp.message(AnimeStates.post_channel)
async def send_to_channel(message: Message, state: FSMContext):
    code = message.text
    cursor.execute("SELECT id, title, desc, image FROM animes WHERE code=?", (code,))
    anime = cursor.fetchone()
    
    if not anime:
        await message.answer("❌ Bu kodli anime topilmadi!")
        await state.clear()
        return
        
    anime_id, title, desc, image = anime
    bot_user = await bot.get_me()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍿 Botda Tomosha Qilish", url=f"https://t.me/{bot_user.username}?start={code}")]
    ])
    
    channel_text = f"🔥 **Yangi Anime Joylandi!**\n\n🎬 **Nomi:** {title}\n⚡️ **Kodi:** {code}\n\n📝 **Tavsif:** {desc}\n\n👇 Pastdagi tugmani bosing va botimizda tomosha qiling!"
    
    CHANNEL_ID = "@Sizning_Kanal_Username"  # O'z kanalingiz usernamesini yozing
    
    try:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=image, caption=channel_text, reply_markup=kb, parse_mode="Markdown")
        await message.answer("🚀 Kanalga post muvaffaqiyatli yuborildi!")
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}\n(Bot kanalizda admin ekanligini tekshiring)")
        
    await state.clear()

# 🚀 BOTNI ISHGA TUSHIRISH
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
