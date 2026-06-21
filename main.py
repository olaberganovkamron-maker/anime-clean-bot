import os
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiohttp import web

# --- 1-BAND: ADMINLAR VA TOKEN ---
TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [int(x.strip()) for x in os.getenv("ADMINS", "0").split(",")]

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- 2-BAND: BAZA VA STATISTIKA (8, 10-bandlar) ---
conn = sqlite3.connect("miraziz.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS animes(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT, video_id TEXT, desc TEXT, photo_id TEXT, views INTEGER DEFAULT 0)")
cur.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, joined_date DATE)")
conn.commit()

# --- 3-4-BAND: ANIME QO'SHISH (FSM) ---
class AddAnime(StatesGroup):
    name = State(); code = State(); media = State(); desc = State()

@dp.message(F.text == "➕ Anime qo'shish")
async def add_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id in ADMINS:
        await msg.answer("✍️ 1-qism: Animening nomini yuboring.")
        await state.set_state(AddAnime.name)

@dp.message(AddAnime.name)
async def get_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text); await msg.answer("1-qism yuklandi✅. 2-qism: Kodni yuboring."); await state.set_state(AddAnime.code)

@dp.message(AddAnime.code)
async def get_code(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text); await msg.answer("2-qism yuklandi✅. 3-qism: Video yoki rasm yuboring."); await state.set_state(AddAnime.media)

@dp.message(AddAnime.media)
async def get_media(msg: types.Message, state: FSMContext):
    media = msg.video.file_id if msg.video else msg.photo[-1].file_id
    await state.update_data(media=media, is_photo=bool(msg.photo)); await msg.answer("3-qism yuklandi✅. 4-qism: Tavsif yozing."); await state.set_state(AddAnime.desc)

@dp.message(AddAnime.desc)
async def get_desc(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute("INSERT INTO animes (name, code, video_id, desc, photo_id) VALUES (?,?,?,?,?)", 
                (data['name'], data['code'], data['media'] if not data['is_photo'] else None, msg.text, data['media'] if data['is_photo'] else None))
    conn.commit(); await msg.answer("✅ Anime bazaga qo'shildi!"); await state.clear()

# --- 7-11-BAND: QIDIRUV VA BOSHQA FUNKSIYALAR ---
@dp.message(Command("start"))
async def start(msg: types.Message):
    cur.execute("INSERT OR IGNORE INTO users VALUES (?, date('now'))", (msg.from_user.id,))
    conn.commit()
    kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="➕ Anime qo'shish")]], resize_keyboard=True) if msg.from_user.id in ADMINS else None
    await msg.answer("👋 Xush kelibsiz! Anime kodini yoki nomini yuboring.", reply_markup=kb)

@dp.message(F.text & ~F.text.startswith("/"))
async def search(msg: types.Message):
    anime = cur.execute("SELECT * FROM animes WHERE code=? OR name=?", (msg.text, msg.text)).fetchone()
    if anime:
        cur.execute("UPDATE animes SET views = views + 1 WHERE id=?", (anime[0],))
        conn.commit()
        cap = f"🎞 {anime[1]}\n📝 {anime[4]}\n👁 Ko'rildi: {anime[6]+1}"
        if anime[5]: await msg.answer_photo(photo=anime[5], caption=cap)
        else: await msg.answer_video(video=anime[3], caption=cap)
    else: await msg.answer("❌ Anime topilmadi. Boshqa kod yuboring.")

# --- RENDER UCHUN SERVER ---
async def web_server(request): return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get('/', web_server)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 10000).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
