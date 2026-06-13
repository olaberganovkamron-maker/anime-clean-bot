import os
import sys
from dotenv import load_dotenv

load_dotenv()

# TOKEN topilmasa xato bersin
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("ERROR: BOT_TOKEN topilmadi!")
    sys.exit(1) # Bu kod bot nima uchun o'chganini logda aniq yozadi
async def main():
    # Eski so‘rovlarni o‘chirib, botni toza holatda ishga tushiradi
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
