import asyncio, sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Baza
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS anime (code TEXT PRIMARY KEY, name TEXT, genre TEXT)")
conn.commit()

class AddAnime(StatesGroup):
    code = State()
    name = State()

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Bot tayyor. Kodni yuboring:")

# --- ANIME QO'SHISH (2-BAND) ---
@dp.message(Command("admin"))
async def admin_panel(msg: types.Message, state: FSMContext):
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("Kod yuboring:")
        await state.set_state(AddAnime.code)

@dp.message(AddAnime.code)
async def get_code(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text)
    await msg.answer("Nomi nima?")
    await state.set_state(AddAnime.name)

@dp.message(AddAnime.name)
async def get_name(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT OR REPLACE INTO anime (code, name) VALUES (?, ?)", (data['code'], msg.text))
    conn.commit()
    await msg.answer(f"✅ Saqlandi! Kod: {data['code']}, Nomi: {msg.text}")
    await state.clear()

# --- QIDIRISH (5-BAND) ---
@dp.message(F.text)
async def search_anime(msg: types.Message):
    # Bu qism kodni tekshiradi
    cursor.execute("SELECT name FROM anime WHERE code = ?", (msg.text,))
    res = cursor.fetchone()
    if res:
        await msg.answer(f"🎬 Topildi: {res[0]}")
    else:
        await msg.answer("❌ Anime topilmadi.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
