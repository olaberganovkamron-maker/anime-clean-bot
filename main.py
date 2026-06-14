import asyncio, sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- TUGMALARNI TO'G'RI YARATISH ---
def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🍿 Anime qidirish"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="🎛 Boshqaruv paneli")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Xush kelibsiz! Quyidagi tugmalardan birini tanlang:", reply_markup=get_main_kb())

# --- TUGMALAR ISHLASHI UCHUN HANTLERLAR ---
@dp.message(F.text == "🍿 Anime qidirish")
async def search_menu(msg: types.Message):
    await msg.answer("Iltimos, anime kodini kiriting:")

@dp.message(F.text == "📊 Statistika")
async def stats_menu(msg: types.Message):
    await msg.answer("📊 Botdagi animelar soni: 0 (Hozircha bo'sh)")

@dp.message(F.text == "🎛 Boshqaruv paneli")
async def admin_menu(msg: types.Message):
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("Admin panelga kirdingiz. Buyruqlarni kuting...")
    else:
        await msg.answer("Siz admin emassiz!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
