import os
import sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher # Bularni import qilganingizga ishonch hosil qiling

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN topilmadi!")
    sys.exit(1)

# BOT va DP shu yerda bo'lishi shart!
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Keyin esa qolgan funksiyalar:
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Salom!")

# Va hokazo...
