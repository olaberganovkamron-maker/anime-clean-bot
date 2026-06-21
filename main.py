import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMINS = [7164685036] # IDingni yoz
CHANNEL_ID = "@kanalingiz_username"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Baza sozlamalari
db = sqlite3.connect("anime_bot.db")
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS animes 
            (id INTEGER PRIMARY KEY, name TEXT, code TEXT, video_id TEXT, desc TEXT)""")
db.commit()

class AnimeState(StatesGroup):
    name = State(); code = State(); video = State(); desc = State()

# Tugmalar
def admin_menu():
    return types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="➕ Anime qo'shish"), types.KeyboardButton(text="🗂 Animelar ro'yxati")],
        [types.KeyboardButton(text="📊 Statistika"), types.KeyboardButton(text="🔊 Bot sozlamalari")],
        [types.KeyboardButton(text="🔍 Qidirish")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Xush kelibsiz!", reply_markup=admin_menu())

# 3-4-BAND: Anime qo'shish
@dp.message(F.text == "➕ Anime qo'shish")
async def add_anime(msg: types.Message, state: FSMContext):
    await msg.answer("Anime nomini yuboring:"); await state.set_state(AnimeState.name)

@dp.message(AnimeState.name)
async def get_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text); await msg.answer("Kodini yuboring:"); await state.set_state(AnimeState.code)

@dp.message(AnimeState.code)
async def get_code(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text); await msg.answer("Videosini yuboring:"); await state.set_state(AnimeState.video)

@dp.message(AnimeState.video, F.video)
async def get_video(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute("INSERT INTO animes (name, code, video_id) VALUES (?,?,?)", (data['name'], data['code'], msg.video.file_id))
    db.commit()
    # 5-BAND: Kanalga post yuborish
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎞 Tomosha qilish", callback_data=f"watch_{data['code']}")]])
    await bot.send_video(CHANNEL_ID, video=msg.video.file_id, caption=f"🎞 {data['name']}\n🗂 Kod: {data['code']}", reply_markup=kb)
    await msg.answer("✅ Muvaffaqiyatli kanalga yuborildi!"); await state.clear()

# 6-BAND: Ro'yxat va tahrirlash (Qisqartirilgan logika)
@dp.message(F.text == "🗂 Animelar ro'yxati")
async def list_anime(msg: types.Message):
    cur.execute("SELECT name, code FROM animes")
    animes = cur.fetchall()
    text = "\n".join([f"{a[0]} (Kod: {a[1]})" for a in animes])
    await msg.answer(text if text else "Animelar yo'q.")

# 8-BAND: Statistika
@dp.message(F.text == "📊 Statistika")
async def stats(msg: types.Message):
    cur.execute("SELECT COUNT(*) FROM animes")
    count = cur.fetchone()[0]
    await msg.answer(f"📊 Statistika:\nAnimelar soni: {count}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
