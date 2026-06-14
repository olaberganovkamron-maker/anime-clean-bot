import asyncio, sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Baza
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS anime (code TEXT PRIMARY KEY, name TEXT)")
conn.commit()

# --- ASOSIY MENYU ---
@dp.message(Command("start"))
async def start(msg: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🍿 Anime qidirish", callback_data="search")
    builder.button(text="📊 Statistika", callback_data="stats")
    if msg.from_user.id == ADMIN_ID:
        builder.button(text="🎛 Admin panel", callback_data="admin")
    builder.adjust(1)
    await msg.answer("Assalomu alaykum! Kerakli bo'limni tanlang:", reply_markup=builder.as_markup())

# --- TUGMALAR JAVOBI ---
@dp.callback_query(F.data == "stats")
async def stats(call: types.CallbackQuery):
    await call.answer("Baza hozircha bo'sh", show_alert=True)

@dp.callback_query(F.data == "search")
async def search(call: types.CallbackQuery):
    await call.message.answer("Anime kodini yozing (faqat raqam):")
    await call.answer()

@dp.callback_query(F.data == "admin")
async def admin_panel(call: types.CallbackQuery):
    await call.message.answer("Admin paneli ochildi!")
    await call.answer()

async def main():
    app = web.Application()
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
