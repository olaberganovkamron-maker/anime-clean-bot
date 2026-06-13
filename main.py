import os
import sys
import asyncio
from dotenv import load_dotenv

# Mana shu importlar juda muhim!
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN topilmadi!")
    sys.exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Endi @dp.message(Command("start")) xato bermaydi, 
# chunki Command import qilindi.
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Salom!")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
