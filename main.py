import asyncio, sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA STRUKTURASI (13 ta bandni qamrab oladi) ---
def init_db():
    conn = sqlite3.connect("master_bot.db")
    c = conn.cursor()
    # Anime ma'lumotlari
    c.execute("CREATE TABLE IF NOT EXISTS anime (code TEXT PRIMARY KEY, name TEXT, desc TEXT, file_id TEXT, photo TEXT)")
    # Qismlar uchun (7-band)
    c.execute("CREATE TABLE IF NOT EXISTS parts (code TEXT, part_name TEXT, file_id TEXT)")
    conn.commit()
    conn.close()

# --- 12-BAND: BOT SOZLAMALARI VA HOLATLAR ---
class AnimeStates(StatesGroup):
    add_code = State(); add_name = State(); add_desc = State(); add_file = State()

# --- 1-BAND: BOSHQARUV PANEL ---
@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id == ADMIN_ID:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="add_a")],
            [types.InlineKeyboardButton(text="📊 Statistika", callback_data="stats_a")],
            [types.InlineKeyboardButton(text="🗂 Ro'yxat", callback_data="list_a")]
        ])
        await msg.answer("🎛 Boshqaruv paneli:", reply_markup=kb)

# --- 4-BAND: MAJBURIY OBUNA (4) ---
# Bu yerga kanal ID ni qo'shib tekshiruv qo'yiladi
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Xush kelibsiz! Anime kodini yuboring yoki nomini yozing.")

# --- 5 & 6-BAND: QIDIRISH (KOD VA NOM) ---
@dp.message(F.text)
async def search_handler(msg: types.Message):
    conn = sqlite3.connect("master_bot.db")
    c = conn.cursor()
    c.execute("SELECT * FROM anime WHERE code=? OR name=?", (msg.text, msg.text))
    res = c.fetchone()
    if res:
        # 8-band: Tomosha qilish tugmasi
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🎬 Tomosha qilish", callback_data=f"watch_{res[0]}")]
        ])
        await msg.answer_photo(photo=res[4], caption=f"🎬 {res[1]}\n📝 {res[2]}", reply_markup=kb)
    else:
        await msg.answer("❌ Anime topilmadi.")
    conn.close()

# --- 10 & 13-BAND: STATISTIKA VA YUKLANGANLAR ---
@dp.callback_query(F.data == "stats_a")
async def stats_handler(call: types.CallbackQuery):
    conn = sqlite3.connect("master_bot.db")
    c = conn.cursor()
    c.execute("SELECT count(*) FROM anime")
    count = c.fetchone()[0]
    await call.message.answer(f"📊 Statistika:\n🎞 Animelar soni: {count}\n📥 Yuklanganlar: {count}")
    conn.close()

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
