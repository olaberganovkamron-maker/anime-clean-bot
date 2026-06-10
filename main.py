import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- SOZLAMALAR ---
TOKEN = "8591657020:AAHcxp39UPzlT0E7SX-W1aySjLppfo_r7n0"
ADMIN_ID = 7164685036  # O'z IDingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- BUYRUQLAR (Ularni qidiruvdan ajratish shart) ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Xush kelibsiz! Anime kodini yuboring.")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Admin panel:\n/add_anime - Anime qo'shish")
    else:
        await message.answer("❌ Siz admin emassiz!")

# --- QIDIRUV (Faqat "/" bilan boshlanmagan matnlar uchun) ---
@dp.message(F.text & ~F.text.startswith("/"))
async def get_anime(message: types.Message):
    code = message.text.strip()
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, desc, photo FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    
    if anime:
        name, desc, photo = anime
        await message.answer_photo(photo=photo, caption=f"🎬 {name}\n\n📝 {desc}")
    else:
        await message.answer("❌ Uzr, bu kod topilmadi.")
    conn.close()

if __name__ == "__main__":
    dp.run_polling(bot)
