import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# TOKENingizni shu yerga yozing
TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"

# 1-BAND: Adminlar ro'yxati (o'zingiz va do'stlaringiz IDsi)
ADMINS = [7164685036] 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 2-BAND: Boshqaruv baneri (Admin uchun maxsus tugmalar)
def main_admin_kb():
    buttons = [
        [KeyboardButton(text="➕ Anime qo'shish"), KeyboardButton(text="🗂 Animelar ro'yxati")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🔊 Bot sozlamalari")],
        [KeyboardButton(text="🔍 Qidirish")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id in ADMINS:
        await message.answer("Admin xush kelibsiz! Panel:", reply_markup=main_admin_kb())
    else:
        await message.answer("Assalomu alaykum! Anime kodini kiriting.")

async def main():
    print("Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
