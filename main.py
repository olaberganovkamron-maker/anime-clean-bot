import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- SOZLAMALAR ---
TOKEN = "8591657020:AAHcxp39UPzlT0E7SX-W1aySjLppfo_r7n0"
ADMIN_ID = 7164685036  # O'z IDingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# State (Qismlar uchun)
class AnimeForm(StatesGroup):
    code = State()
    name = State()
    desc = State()
    photo = State()

# Baza inicializatsiyasi
def init_db():
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS animes (code TEXT PRIMARY KEY, name TEXT, desc TEXT, photo TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS views (code TEXT PRIMARY KEY, count INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

init_db()

# --- 4, 9-band: Qidiruv va Xush kelibsiz ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Xush kelibsiz! Anime ko'rish uchun kodni yuboring.")

@dp.message(F.text)
async def get_anime(message: types.Message):
    code = message.text.strip()
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, desc, photo FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    
    if anime:
        name, desc, photo = anime
        cursor.execute("INSERT OR IGNORE INTO views VALUES (?, 0)", (code,))
        cursor.execute("UPDATE views SET count = count + 1 WHERE code = ?", (code,))
        conn.commit()
        
        cursor.execute("SELECT count FROM views WHERE code = ?", (code,))
        views = cursor.fetchone()[0]
        
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Tomosha qilish", callback_data=f"watch_{code}")],
            [InlineKeyboardButton(text="📥 Yuklab olish", callback_data=f"dl_{code}")]
        ])
        await message.answer_photo(photo=photo, caption=f"🎬 {name}\n\n📝 {desc}\n\n👤 Ko'rilganlar: {views}", reply_markup=btn)
    else:
        await message.answer("❌ Uzr, anime topilmadi. Boshqa kod kiriting.")
    conn.close()

# --- 2, 5, 11, 12-band: Admin Panel ---
@dp.message(Command("add_anime"))
async def add_anime(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Anime kodini kiriting:")
        await state.set_state(AnimeForm.code)
    else:
        await message.answer("Siz admin emassiz!")

@dp.message(AnimeForm.code)
async def save_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await message.answer("Anime nomini yozing:")
    await state.set_state(AnimeForm.name)

# (Qolgan step'lar ham shu tartibda davom etadi)

if __name__ == "__main__":
    dp.run_polling(bot)
