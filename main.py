import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiohttp import web

# --- ID VA TOKEN ---
TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
ADMIN_ID = 7164685036  # @userinfobot dan olgan IDing

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA ---
conn = sqlite3.connect("miraziz.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS animes(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT, video_id TEXT, desc TEXT, photo_id TEXT)")
conn.commit()

class AddAnime(StatesGroup):
    name = State(); code = State(); media = State(); desc = State()

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_panel(msg: types.Message):
    if msg.from_user.id == ADMIN_ID:
        kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="➕ Anime qo'shish")]], resize_keyboard=True)
        await msg.answer("🛠 Admin panelga kirdingiz!", reply_markup=kb)
    else:
        await msg.answer("❌ Siz admin emassiz!")

@dp.message(F.text == "➕ Anime qo'shish")
async def add_anime(msg: types.Message, state: FSMContext):
    if msg.from_user.id == ADMIN_ID:
        await msg.answer("✍️ 1-qism: Anime nomini yozing:")
        await state.set_state(AddAnime.name)

@dp.message(AddAnime.name)
async def get_name(msg: types.Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await msg.answer("✅ Nom olindi. 2-qism: Kodni yozing:"); await state.set_state(AddAnime.code)

@dp.message(AddAnime.code)
async def get_code(msg: types.Message, state: FSMContext):
    await state.update_data(code=msg.text)
    await msg.answer("✅ Kod olindi. 3-qism: Rasm yoki Video yuboring:"); await state.set_state(AddAnime.media)

@dp.message(AddAnime.media)
async def get_media(msg: types.Message, state: FSMContext):
    media = msg.video.file_id if msg.video else msg.photo[-1].file_id
    await state.update_data(media=media, is_photo=bool(msg.photo))
    await msg.answer("✅ Media olindi. 4-qism: Tavsif yozing:"); await state.set_state(AddAnime.desc)

@dp.message(AddAnime.desc)
async def get_desc(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute("INSERT INTO animes (name, code, video_id, desc, photo_id) VALUES (?,?,?,?,?)", 
                (data['name'], data['code'], data['media'] if not data['is_photo'] else None, msg.text, data['media'] if data['is_photo'] else None))
    conn.commit()
    await msg.answer("🎉 Anime muvaffaqiyatli qo'shildi!"); await state.clear()

# --- SEARCH ---
@dp.message(F.text)
async def search(msg: types.Message):
    anime = cur.execute("SELECT * FROM animes WHERE code=? OR name=?", (msg.text, msg.text)).fetchone()
    if anime:
        cap = f"🎞 {anime[1]}\n📝 {anime[4]}"
        if anime[5]: await msg.answer_photo(photo=anime[5], caption=cap)
        else: await msg.answer_video(video=anime[3], caption=cap)
    else: await msg.answer("❌ Bunday anime topilmadi.")

# --- SERVER ---
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
