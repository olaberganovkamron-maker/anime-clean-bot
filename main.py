import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- SOZLAMALAR ---
TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036

# Loglarni ko'rish
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
conn = sqlite3.connect("anime_bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS anime (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        name TEXT,
        genre TEXT
    )
""")
conn.commit()

# Admin holatini saqlash uchun (oddiy lug'at)
admin_states = {}

# 16 ta janr ro'yxati
GENRES = [
    "Jangari", "Romantika", "Komediya", "Detektiv", "Sport", 
    "Sarguzasht", "Fantastika", "Qo'rqinchli", "Tarixiy", "Musiqiy",
    "Drama", "Psixologik", "Sehrli", "Mexa", "Slayz", "O'zbekcha"
]

# --- RENDER UCHUN VEB SERVER (Port 8080) ---
async def handle(request):
    return web.Response(text="Bot ishlamoqda...")

async def web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

# --- BOT FUNKSIYALARI ---

def is_admin(user_id):
    return user_id == ADMIN_ID

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if is_admin(message.from_user.id):
        # Admin menyusi (16 ta janr tugmasi bilan)
        builder = InlineKeyboardBuilder()
        for g in GENRES:
            builder.add(types.InlineKeyboardButton(text=g, callback_data=f"add_{g}"))
        builder.adjust(2)
        await message.answer("Xush kelibsiz Admin! Anime qo'shish uchun janrni tanlang:", reply_markup=builder.as_markup())
    else:
        await message.answer("Xush kelibsiz! Anime kodini yuboring:")

# Admin janrni tanlaganda
@dp.callback_query(F.data.startswith("add_"))
async def process_genre(callback: types.CallbackQuery):
    genre = callback.data.split("_")[1]
    admin_states[callback.from_user.id] = {"genre": genre, "step": "get_code"}
    await callback.message.answer(f"Siz '{genre}' janrini tanladingiz. Endi anime KODINI yuboring:")
    await callback.answer()

# Kod va Nomni qabul qilish
@dp.message(F.text)
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # Admin anime qo'shayotgan bo'lsa
    if is_admin(user_id) and user_id in admin_states:
        state = admin_states[user_id]
        
        if state["step"] == "get_code":
            state["code"] = text
            state["step"] = "get_name"
            await message.answer("Kod qabul qilindi. Endi anime NOMINI yuboring:")
            
        elif state["step"] == "get_name":
            name = text
            code = state["code"]
            genre = state["genre"]
            
            try:
                cursor.execute("INSERT INTO anime (code, name, genre) VALUES (?, ?, ?)", (code, name, genre))
                conn.commit()
                await message.answer(f"✅ Muvaffaqiyatli qo'shildi!\nKodi: {code}\nNomi: {name}\nJanr: {genre}")
            except:
                await message.answer("❌ Xato: Bu kod bazada bor bo'lishi mumkin.")
            
            del admin_states[user_id] # Holatni tozalash

    # Oddiy foydalanuvchi kod yuborganda
    else:
        cursor.execute("SELECT name, genre FROM anime WHERE code = ?", (text,))
        result = cursor.fetchone()
        if result:
            await message.answer(f"🎬 Anime nomi: {result[0]}\n📂 Janri: {result[1]}")
        else:
            await message.answer("😔 Kechirasiz, bu kod bilan anime topilmadi.")

async def main():
    asyncio.create_task(web_server()) # Veb serverni orqa fonda ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
