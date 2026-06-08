import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# BOT TOKENINGIZNI SHU YERGA QO'YING
TOKEN = "8591657020:AAHcxp39UPzlT0E7SX-W1aySjLppfo_r7n0"  # BotFather'dan olgan tokeningizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("Bot muvaffaqiyatli ishga tushdi! 🚀")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
