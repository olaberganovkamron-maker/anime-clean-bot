import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- SOZLAMALAR ---
TOKEN = "8591657020:AAHcxp39UPzlT0E7SX-W1aySjLppfo_r7n0"
ADMIN_ID = 7164685036 # O'z IDingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# State (Bosqichlar)
class AnimeForm(StatesGroup):
    code = State()
    name = State()
    desc = State()
    photo = State()

def init_db():
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS animes (code TEXT PRIMARY KEY, name TEXT, desc TEXT, photo TEXT)")
    conn.commit(); conn.close()

init_db()

# --- BUYRUQLAR (Admin va Start) ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Xush kelibsiz! Anime kodini yuboring.")

@dp.message(Command("admin"))
async def admin_menu(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Admin panel:\n/add_anime - Anime qo'shish")
    else:
        await message.answer("❌ Siz admin emassiz!")

@dp.message(Command("add_anime"))
async def add_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Anime kodini kiriting:")
        await state.set_state(AnimeForm.code)
    else:
        await message.answer("❌ Siz admin emassiz!")

# --- ANIME QO'SHISH BOSQICHLARI ---
@dp.message(AnimeForm.code)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await message.answer("Anime nomini yozing:")
    await state.set_state(AnimeForm.name)

@dp.message(AnimeForm.name)
async def add_desc(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Anime tavsifini yozing:")
    await state.set_state(AnimeForm.desc)

@dp.message(AnimeForm.desc)
async def add_photo(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Anime rasmini yuboring:")
    await state.set_state(AnimeForm.photo)

@dp.message(AnimeForm.photo)
async def finish_add(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo = message.photo[-1].file_id if message.photo else "https://via.placeholder.com/150"
    
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO animes VALUES (?, ?, ?, ?)", (data['code'], data['name'], data['desc'], photo))
    conn.commit(); conn.close()
    
    await message.answer("✅ Anime bazaga saqlandi!"); await state.clear()

# --- QIDIRUV (Matnli xabarlar uchun) ---
@dp.message(F.text)
async def get_anime(message: types.Message):
    # Buyruqlar qidiruvga kirmasligi uchun tekshiruv
    if message.text.startswith("/"): return
    
    code = message.text.strip()
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, desc, photo FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    
    if anime:
        name, desc, photo = anime
        await message.answer_photo(photo=photo, caption=f"🎬 {name}\n\n📝 {desc}\n\n📂 Kod: {code}")
    else:
        await message.answer("❌ Uzr, bu kod bilan anime topilmadi.")
    conn.close()

if __name__ == "__main__":
    dp.run_polling(bot)
