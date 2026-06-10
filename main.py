import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- SOZLAMALAR ---
TOKEN = "8591657020:AAHcxp39UPzlT0E7SX-W1aySjLppfo_r7n0"
ADMIN_ID = 7164685036 # O'z ID raqamingiz
CHANNEL_ID = "@A_ToolsX" # Majburiy obuna kanali

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class AnimeForm(StatesGroup):
    code = State(); name = State(); desc = State(); photo = State()

# --- BAZA ---
def init_db():
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS animes (code TEXT PRIMARY KEY, name TEXT, desc TEXT, photo TEXT)")
    conn.commit(); conn.close()
init_db()

# --- 13 TALI ROYHAT FUNKSIYALARI ---
def check_sub(user_id):
    # Bu yerda kanalga a'zolik tekshiriladi
    return True 

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Xush kelibsiz! Anime kodini yuboring.")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="add_anime")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")]
        ])
        await message.answer("👑 **Admin Panel**", reply_markup=kb)

@dp.callback_query(F.data == "add_anime")
async def add_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Anime kodini kiriting:"); await state.set_state(AnimeForm.code)

# (Bu yerda AnimeForm bosqichlari...)

@dp.message(F.text)
async def get_anime(message: types.Message):
    if message.text.startswith("/"): return
    if not check_sub(message.from_user.id):
        await message.answer(f"🚀 Kanalga obuna bo'ling: {CHANNEL_ID}"); return
    
    code = message.text.strip()
    conn = sqlite3.connect("anime_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, desc, photo FROM animes WHERE code = ?", (code,))
    anime = cursor.fetchone()
    
    if anime:
        name, desc, photo = anime
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="▶️ Tomosha qilish", url="https://t.me/kanal")]])
        await message.answer_photo(photo=photo, caption=f"🎬 {name}\n\n📝 {desc}", reply_markup=kb)
    else:
        await message.answer("❌ Topilmadi.")
    conn.close()

if __name__ == "__main__":
    dp.run_polling(bot)
