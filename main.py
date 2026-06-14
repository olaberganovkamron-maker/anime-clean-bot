import asyncio, sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036

bot = Bot(token=TOKEN)
dp = Dispatcher()
conn = sqlite3.connect("anime_data.db", check_same_thread=False)
cursor = conn.cursor()
# 16 ta funksiyani qo'llab-quvvatlaydigan baza
cursor.execute("CREATE TABLE IF NOT EXISTS anime (code TEXT PRIMARY KEY, name TEXT, desc TEXT, file_id TEXT, genre TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER)")
conn.commit()

# --- ASOSIY MENYU ---
def main_menu(user_id):
    kb = [[KeyboardButton(text="🍿 Anime qidirish"), KeyboardButton(text="📊 Statistika")]]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="🎛 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Xush kelibsiz! Anime botiga kirdingiz.", reply_markup=main_menu(message.from_user.id))

# 2, 3, 10, 13, 16 - ADMIN PANEL (Yig'ilgan)
@dp.message(F.text == "🎛 Admin panel")
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin boshqaruv paneli:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="add_anime")],
            [InlineKeyboardButton(text="🗂 Animelar ro'yxati", callback_data="list_anime")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")]
        ]))

# 5, 6 - QIDIRISH
@dp.message(F.text == "🍿 Anime qidirish")
async def search_mode(message: types.Message):
    await message.answer("Anime kodi yoki nomini yuboring:")

@dp.message(F.text.isdigit())
async def get_anime(message: types.Message):
    cursor.execute("SELECT * FROM anime WHERE code = ?", (message.text,))
    res = cursor.fetchone()
    if res:
        await message.answer_video(video=res[3], caption=f"🎬 {res[1]}\n📝 {res[2]}\n📂 Janri: {res[4]}")
    else:
        await message.answer("❌ Anime topilmadi.")

# Stats (10, 16)
@dp.callback_query(F.data == "stats")
async def show_stats(call: types.CallbackQuery):
    cursor.execute("SELECT count(*) FROM anime")
    count = cursor.fetchone()[0]
    await call.message.answer(f"📊 Yuklangan animelar soni: {count}")

async def main():
    app = web.Application()
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
