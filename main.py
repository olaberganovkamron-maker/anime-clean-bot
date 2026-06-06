import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiohttp import web

# @BotFather dan olgan haqiqiy tokeningizni yozing
BOT_TOKEN = "8869934360:AAF0GLfrwS5oiTJDzunDW-Mb23idr5c-hng" 

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(f"Salom, {message.from_user.full_name}! 👋\nBot Render platformasida muvaffaqiyatli ishlamoqda! 🚀")

@dp.message()
async def echo_handler(message: types.Message):
    await message.answer(f"Siz yozdingiz: {message.text}")

# Render oʻchib qolmasligi uchun kichik veb-server funksiyasi
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    # Veb-serverni sozlash (Render talab qiladigan port)
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 7860))
    site = web.TCPSite(runner, '0.0.0.0', port)
    asyncio.create_task(site.start())
    
    print(f"Web server started on port {port}")
    
    # Bot pollingni boshlash
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
