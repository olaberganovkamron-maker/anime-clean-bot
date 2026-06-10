import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

# --- BU YERLARNI O'ZGARTIRING ---
TOKEN = "8591657020:AAHcxp39UPzlT0E7SX-W1aySjLppfo_r7n0"
ADMIN_ID = 7164685036  # O'z Telegram ID raqamingizni yozing
# -------------------------------

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Baza inicializatsiyasi
def init_db():
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS animes (code TEXT PRIMARY KEY, name TEXT, desc TEXT, photo TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS parts (code TEXT, part_num INTEGER, file_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS views (code TEXT, count INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

# Qidiruv va 13-band (Ko'rilganlar statistikasi)
@dp.message(F.text)
async def get_anime(message: types.Message):
    code = message.text.strip()
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, desc, photo FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    
    cursor.execute("SELECT count FROM views WHERE code = ?", (code,))
    view = cursor.fetchone()
    
    if anime:
        name, desc, photo = anime
        views = view[0] if view else 0
        
        # Tugmalar
        builder = types.InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📥 Yuklab olish", callback_data="download"))
        builder.row(types.InlineKeyboardButton(text="▶️ Tomosha qilish", callback_data="watch"))
        
        await message.answer_photo(
            photo=photo, 
            caption=f"🎬 Nomi: {name}\n\n📝 Tavsif: {desc}\n\n👤 Ko'rilganlar: {views + 1}\n\n📂 KODI: « {code} »", 
            reply_markup=builder.as_markup()
        )
        
        cursor.execute("UPDATE views SET count = count + 1 WHERE code = ?", (code,))
        conn.commit()
    else:
        await message.answer("❌ Uzr, anime topilmadi. Boshqa kod kiriting.")
    conn.close()

if __name__ == "__main__":
    init_db()
    dp.run_polling(bot)
