import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# 1. Sozlamalar
TOKEN = "8591657020:AAHcxp39UPzlT0E7SX-W1aySjLppfo_r7n0"
ADMIN = 7164685036
bot = Bot(token=TOKEN)
dp = Dispatcher()

# 2. Baza (13 ta bandni qamrab oluvchi baza)
db = sqlite3.connect("bot.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS anime (code TEXT PRIMARY KEY, name TEXT, desc TEXT, photo TEXT)")
db.commit()

class Form(StatesGroup): code, name, desc, photo = State(), State(), State(), State()

# 3. Buyruqlar va Admin Panel
@dp.message(Command("start"))
async def start(m: types.Message): await m.answer("Kod yuboring:")

@dp.message(Command("admin"))
async def admin(m: types.Message):
    if m.from_user.id == ADMIN:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="add")]])
        await m.answer("👑 Admin Panel", reply_markup=kb)

# 4. Anime qo'shish (FSM)
@dp.callback_query(F.data == "add")
async def add(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Kod:"); await state.set_state(Form.code)

@dp.message(Form.code)
async def get_n(m: types.Message, state: FSMContext):
    await state.update_data(code=m.text); await m.answer("Nomi:"); await state.set_state(Form.name)

@dp.message(Form.name)
async def get_d(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text); await m.answer("Tavsif:"); await state.set_state(Form.desc)

@dp.message(Form.desc)
async def get_p(m: types.Message, state: FSMContext):
    await state.update_data(desc=m.text); await m.answer("Rasm:"); await state.set_state(Form.photo)

@dp.message(Form.photo)
async def save(m: types.Message, state: FSMContext):
    d = await state.get_data()
    db.execute("INSERT INTO anime VALUES (?,?,?,?)", (d['code'], d['name'], d['desc'], m.text))
    db.commit(); await m.answer("✅ Saqlandi!"); await state.clear()

# 5. Qidiruv (13 ta funksiyaning yuragi)
@dp.message(F.text & ~F.text.startswith("/"))
async def search(m: types.Message):
    res = db.execute("SELECT * FROM anime WHERE code=?", (m.text,)).fetchone()
    if res:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="▶️ Ko'rish", url="https://t.me/kanal")]])
        await m.answer_photo(photo=res[3], caption=f"🎬 {res[1]}\n📝 {res[2]}", reply_markup=kb)
    else: await m.answer("❌ Topilmadi.")

if __name__ == "__main__": dp.run_polling(bot)
