import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from flask import Flask
import threading

# Flask (Render o'chib qolmasligi uchun port ochadi)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Logging (Xatoliklarni ko'rish uchun)
logging.basicConfig(level=logging.INFO)

# Tokenni Render tizimidan xavfsiz o'qiydi
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7488056428:AAF8A6g_pZ8I-jKOfy0VjFq7Nsc_U32-K9E")
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Admin ID (Sening Telegram ID'ying)
ADMIN_ID = 5371587441  

# Vaqtinchalik ma'lumotlar bazasi
anime_database = {}

# Suxbat bosqichlari (FSM)
class AnimeState(StatesGroup):
    waiting_for_code = State()
    waiting_for_name = State()
    waiting_for_desc = State()

# /start komandasi
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton("➕ Anime qo'shish"))
        await message.answer("👋 Xush kelibsiz, Admin!\nBoshqaruv paneli tayyor:", reply_markup=keyboard)
    else:
        await message.answer("🎬 Salom! Anime kodini yuboring:")

# Admin: "Anime qo'shish" tugmasini bosganda
@dp.message_handler(text="➕ Anime qo'shish")
async def add_anime_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await AnimeState.waiting_for_code.set()
        await message.answer("🎬 Yangi anime uchun KOD kiriting (Masalan: 23):")

# Admin: Kodni kiritganda
@dp.message_handler(state=AnimeState.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    await state.update_data(anime_code=message.text.strip())
    await AnimeState.next()
    await message.answer("🍿 Anime nomini yuboring:")

# Admin: Nomini kiritganda
@dp.message_handler(state=AnimeState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(anime_name=message.text.strip())
    await AnimeState.next()
    await message.answer("📜 Anime tavsifini yuboring:")

# Admin: Tavsifni kiritganda va saqlash
@dp.message_handler(state=AnimeState.waiting_for_desc)
async def process_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data['anime_code']
    name = data['anime_name']
    desc = message.text.strip()

    # Bazaga saqlash
    anime_database[code] = {"name": name, "desc": desc}
    
    await state.finish()
    await message.answer(f"✅ Anime muvaffaqiyatli saqlandi!\n\n🔑 Kod: {code}\n🎬 Nomi: {name}")

# Kod yuborilganda qidirish
@dp.message_handler()
async def search_anime(message: types.Message):
    code = message.text.strip()
    if code in anime_database:
        anime = anime_database[code]
        await message.answer(f"🎬 Nomi: {anime['name']}\n\n📜 Tavsif: {anime['desc']}")
    else:
        await message.answer("❌ Bunday kodli anime topilmadi!")

if __name__ == '__main__':
    # Flaskni alohida potokda yoqish
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Botni ishga tushirish
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
