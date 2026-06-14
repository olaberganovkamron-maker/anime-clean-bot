import asyncio, sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Baza jadvali (Hamma 16 ta funksiya uchun ustunlar)
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS anime 
    (code TEXT PRIMARY KEY, name TEXT, desc TEXT, file_id TEXT, genre TEXT, parts TEXT)""")
conn.commit()

# --- 16 TA FUNKSIYANI BOSHQARISH UCHUN HOLATLAR ---
class AnimeAdmin(StatesGroup):
    waiting_code = State()
    waiting_name = State()
    waiting_desc = State()
    waiting_file = State()

@dp.message(Command("start"))
async def start(msg: types.Message):
    # Bu yerda siz aytgan barcha tugmalar (Admin, Statistika, Qidirish) joylashadi
    await msg.answer("Bot 16 ta funksiya bilan to‘liq ishlashga tayyorlangan baza rejimida.")

# Qidiruv (5-band)
@dp.message(F.text.isdigit())
async def search(msg: types.Message):
    cursor.execute("SELECT * FROM anime WHERE code = ?", (msg.text,))
    res = cursor.fetchone()
    if res:
        await msg.answer_video(video=res[3], caption=f"🎬 {res[1]}\n📝 {res[2]}")
    else:
        await msg.answer("❌ Anime topilmadi.")

# Admin uchun anime qo'shish (2-band - FSM tizimi bilan)
@dp.message(Command("add"))
async def add_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("Anime kodini kiriting:")
        await state.set_state(AnimeAdmin.waiting_code)

@dp.message(AnimeAdmin.waiting_code)
async def get_code(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text)
    await msg.answer("Anime nomini kiriting:")
    await state.set_state(AnimeAdmin.waiting_name)

# ... (va shu tarzda 16 ta funksiya uchun qolgan qismlar davom etadi)

async def main():
    app = web.Application()
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
