import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# ---- BOT SOZLAMALARI ----
BOT_TOKEN = "8869934360:AAF0GLfrwS5oiTJDzunDW-Mb23idr5c-hng" # Tokenni shu yerga qo'ying
ADMIN_ID = 7164685036                # O'zingizning Telegram ID raqamingizni yozing

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---- BAZA (SQLITE) ----
def init_db():
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, date TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS animes (code TEXT PRIMARY KEY, name TEXT, photo TEXT, desc TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS episodes (anime_code TEXT, ep_num INTEGER, file_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS channels (url TEXT, chat_id TEXT)")
    conn.commit()
    conn.close()

init_db()

# ---- HOLATLAR (STATES) ----
class BotStates(StatesGroup):
    add_code = State()
    add_name = State()
    add_photo = State()
    add_desc = State()
    add_video = State()
    user_req = State()
    post_text = State()
    post_url = State()
    # Tahrirlash holatlari
    edit_name = State()
    edit_photo = State()
    edit_desc = State()
    edit_code = State()

# ---- TUGMALAR (KEYBOARDS) ----
admin_btn = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🎛 Boshqarish paneli")]], resize_keyboard=True)

panel_markup = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Anime qo'shish", callback_data="add_anime"),
     InlineKeyboardButton(text="🗂 Animelar ro'yxati", callback_data="list_anime")],
    [InlineKeyboardButton(text="🔒 Kanallar", callback_data="channels"),
     InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
    [InlineKeyboardButton(text="📤 Post yuborish", callback_data="send_post")]
])

# ---- OBUNANI TEKSHIRISH ----
async def is_subscribed(user_id):
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("SELECT url, chat_id FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    for url, chat_id in channels:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except:
            pass
    return True

# ---- FOYDALANUVCHILAR QISMI (4-BAND SO'ZLARI BILAN) ----

@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect('anime.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (message.from_user.id, datetime.now().strftime("%Y-%m-%d")))
    conn.commit() ; conn.close()

    if not await is_subscribed(message.from_user.id):
        conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
        cursor.execute("SELECT url FROM channels")
        channels = cursor.fetchall() ; conn.close()
        
        btns = [[InlineKeyboardButton(text="Obuna bo'lish", url=ch[0])] for ch in channels]
        btns.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check")])
        await message.answer("🔊 Kanallarga obuna boling tekashirish", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
        return

    msg = "🔊 xush kelibsiz,animeni kodini yuboring"
    if message.from_user.id == ADMIN_ID:
        await message.answer(msg, reply_markup=admin_btn)
    else:
        await message.answer(msg)

@dp.callback_query(F.data == "check")
async def check(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🔊 xush kelibsiz,animeni kodini yuboring")
    else:
        await call.answer("Uzur, hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

# 9) ANIME QIDIRISH
@dp.message(F.text & ~F.text.startswith('/'))
async def search(message: types.Message, state: FSMContext):
    if message.text == "🎛 Boshqarish paneli" and message.from_user.id == ADMIN_ID:
        await message.answer("🎛 Boshqarish paneli:", reply_markup=panel_markup)
        return

    if not await is_subscribed(message.from_user.id):
        await start(message)
        return

    code = message.text.strip()
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("SELECT name, photo, desc FROM animes WHERE code=?", (code,))
    anime = cursor.fetchone()
    
    if anime:
        name, photo, desc = anime
        cursor.execute("SELECT ep_num FROM episodes WHERE anime_code=? ORDER BY ep_num ASC", (code,))
        eps = cursor.fetchall() ; conn.close()
        
        caption = f"🎬 Nomi: {name}\n📝 Tavsif: {desc}\n🔢 Kodi: {code}"
        btns = [] ; row = []
        for ep in eps:
            row.append(InlineKeyboardButton(text=f"{ep[0]}-qism", callback_data=f"get_{code}_{ep[0]}"))
            if len(row) == 3: btns.append(row) ; row = []
        if row: btns.append(row)
            
        if photo != "Yo'q":
            await message.answer_photo(photo=photo, caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
        else:
            await message.answer(text=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        conn.close()
        btn = [[InlineKeyboardButton(text="⭐️ Adminga murojaat", callback_data="req")]]
        await message.answer("🔊 uzur anime topilmadi boshqa kodin kirtib koring", reply_markup=InlineKeyboardMarkup(inline_keyboard=btn))

@dp.callback_query(F.data.startswith("get_"))
async def get_ep(call: types.CallbackQuery):
    _, code, ep_num = call.data.split("_")
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM episodes WHERE anime_code=? AND ep_num=?", (code, int(ep_num)))
    file_id = cursor.fetchone() ; conn.close()
    if file_id:
        await bot.send_video(chat_id=call.from_user.id, video=file_id[0], caption=f"🎬 {ep_num}-qism")
    await call.answer()

# 10) ADMIN BILAN BOG'LANISH
@dp.callback_query(F.data == "req")
async def req(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Qidirayotgan anime nomingizni yozing:")
    await state.set_state(BotStates.user_req)

@dp.message(BotStates.user_req)
async def user_req(message: types.Message, state: FSMContext):
    await bot.send_message(chat_id=ADMIN_ID, text=f"⭐️ **Anime topilmadi so'rovi:**\nKimdan: {message.from_user.full_name}\nNomi: {message.text}")
    await message.answer("Xabaringiz adminga yetkazildi!") ; await state.clear()

# ---- 7) STATISTIKA QISMI ----
@dp.callback_query(F.data == "stats")
async def stats(call: types.CallbackQuery):
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users") ; total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM animes") ; animes = cursor.fetchone()[0]
    
    t = datetime.now()
    cursor.execute("SELECT COUNT(*) FROM users WHERE date >= ?", ((t-timedelta(days=1)).strftime("%Y-%m-%d"),)) ; d1 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE date >= ?", ((t-timedelta(days=3)).strftime("%Y-%m-%d"),)) ; d3 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE date >= ?", ((t-timedelta(days=7)).strftime("%Y-%m-%d"),)) ; d7 = cursor.fetchone()[0]
    conn.close()
    
    txt = f"📊 **Statistika:**\n\n👤 obunachilarni soni-{total}\n1kun-{d1}\n3kun-{d3}\n7kun-{d7}\n🎞 animelarni soni-{animes}"
    await call.message.edit_text(txt, reply_markup=panel_markup)

# ---- 2) VA 5) ANIME QO'SHISH ----
@dp.callback_query(F.data == "add_anime")
async def add_a(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Anime KODINI kiriting:")
    await state.set_state(BotStates.add_code)

@dp.message(BotStates.add_code)
async def add_c(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Anime NOMINI kiriting:")
    await state.set_state(BotStates.add_name)

@dp.message(BotStates.add_name)
async def add_n(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("RASMINI yuboring (bo'lmasa 'Yo'q' deb yozing):")
    await state.set_state(BotStates.add_photo)

@dp.message(BotStates.add_photo)
async def add_p(message: types.Message, state: FSMContext):
    photo = message.photo[-1].file_id if message.photo else "Yo'q"
    await state.update_data(photo=photo)
    await message.answer("TAVSIFINI kiriting:")
    await state.set_state(BotStates.add_desc)

@dp.message(BotStates.add_desc)
async def add_d(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO animes VALUES (?, ?, ?, ?)", (data['code'], data['name'], data['photo'], message.text))
    conn.commit() ; conn.close()
    await message.answer("✅ Anime qo'shildi!", reply_markup=panel_markup)
    await state.clear()

# ---- 3) ANIMELAR RO'YXATI VA TAHRIRLASH ----
@dp.callback_query(F.data == "list_anime")
async def list_a(call: types.CallbackQuery):
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("SELECT code, name FROM animes")
    animes = cursor.fetchall() ; conn.close()
    
    if not animes:
        await call.message.edit_text("🗂 Ro'yxat bo'sh.", reply_markup=panel_markup) ; return
        
    btns = [[InlineKeyboardButton(text=name, callback_data=f"op_{code}")] for code, name in animes]
    btns.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")])
    await call.message.edit_text("🗂 Animelarni ro'yxati:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("op_"))
async def op_a(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    btns = [
        [InlineKeyboardButton(text="🎬 Qism qo'shish", callback_data=f"addep_{code}")],
        [InlineKeyboardButton(text="✒️ Nomi", callback_data=f"en_{code}"), InlineKeyboardButton(text="🏞 Rasmi", callback_data=f"ep_{code}")],
        [InlineKeyboardButton(text="✒️ Tavsifi", callback_data=f"ed_{code}"), InlineKeyboardButton(text="✒️ Kodi", callback_data=f"ec_{code}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{code}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="list_anime")]
    ]
    await call.message.edit_text(f"Anime kodi: {code}\nQuyidagilardan birini tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# 3-BANDNIG TAHRIRLASH QISMLARI
@dp.callback_query(F.data.startswith("en_"))
async def edit_n_start(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(code=call.data.split("_")[1])
    await call.message.answer("✒️ Yangi NOMINI yuboring:")
    await state.set_state(BotStates.edit_name)

@dp.message(BotStates.edit_name)
async def edit_n_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("UPDATE animes SET name=? WHERE code=?", (message.text, data['code']))
    conn.commit() ; conn.close() ; await state.clear()
    await message.answer("✅ Nomi o'zgartirildi!", reply_markup=panel_markup)

@dp.callback_query(F.data.startswith("ep_"))
async def edit_p_start(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(code=call.data.split("_")[1])
    await call.message.answer("🏞 Yangi RASMINI yuboring:")
    await state.set_state(BotStates.edit_photo)

@dp.message(BotStates.edit_photo)
async def edit_p_save(message: types.Message, state: FSMContext):
    if not message.photo: await message.answer("Rasm yuboring!") ; return
    data = await state.get_data()
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("UPDATE animes SET photo=? WHERE code=?", (message.photo[-1].file_id, data['code']))
    conn.commit() ; conn.close() ; await state.clear()
    await message.answer("✅ Rasmi o'zgartirildi!", reply_markup=panel_markup)

@dp.callback_query(F.data.startswith("ed_"))
async def edit_d_start(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(code=call.data.split("_")[1])
    await call.message.answer("✒️ Yangi TAVSIFINI yuboring:")
    await state.set_state(BotStates.edit_desc)

@dp.message(BotStates.edit_desc)
async def edit_d_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("UPDATE animes SET desc=? WHERE code=?", (message.text, data['code']))
    conn.commit() ; conn.close() ; await state.clear()
    await message.answer("✅ Tavsifi o'zgartirildi!", reply_markup=panel_markup)

@dp.callback_query(F.data.startswith("ec_"))
async def edit_c_start(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(code=call.data.split("_")[1])
    await call.message.answer("✒️ Yangi KODINI kiriting:")
    await state.set_state(BotStates.edit_code)

@dp.message(BotStates.edit_code)
async def edit_c_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_code = message.text.strip()
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    try:
        cursor.execute("UPDATE animes SET code=? WHERE code=?", (new_code, data['code']))
        cursor.execute("UPDATE episodes SET anime_code=? WHERE anime_code=?", (new_code, data['code']))
        conn.commit() ; conn.close() ; await state.clear()
        await message.answer("✅ Kodi muvaffaqiyatli o'zgartirildi!", reply_markup=panel_markup)
    except:
        conn.close() ; await message.answer("❌ Bu kod allaqachon band!")

@dp.callback_query(F.data.startswith("del_"))
async def del_a(call: types.CallbackQuery):
    code = call.data.split("_")[1]
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("DELETE FROM animes WHERE code=?", (code,))
    cursor.execute("DELETE FROM episodes WHERE anime_code=?", (code,))
    conn.commit() ; conn.close()
    await call.answer("🗑 O'chirildi!") ; await list_a(call)

# ---- 11) KETMA-KET QISM QO'SHISH ----
@dp.callback_query(F.data.startswith("addep_"))
async def add_ep(call: types.CallbackQuery, state: FSMContext):
    code = call.data.split("_")[1]
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM episodes WHERE anime_code=?", (code,))
    next_ep = cursor.fetchone()[0] + 1 ; conn.close()
    
    await state.update_data(code=code, next_ep=next_ep)
    await call.message.answer(f"📹 {next_ep}qismni yuboring")
    await state.set_state(BotStates.add_video)

@dp.message(BotStates.add_video, F.video)
async def save_ep(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("INSERT INTO episodes VALUES (?, ?, ?)", (data['code'], data['next_ep'], message.video.file_id))
    conn.commit() ; conn.close()
    
    await message.answer(f"✅ {data['next_ep']}qism saqland")
    next_ep = data['next_ep'] + 1
    await state.update_data(next_ep=next_ep)
    await message.answer(f"📹 {next_ep}qismni yuboring")

# ---- 6) MAJBURIY KANALLAR ----
@dp.callback_query(F.data == "channels")
async def chan(call: types.CallbackQuery):
    btns = [[InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_chan")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back")]]
    await call.message.edit_text("🔒 Majburiy kanallar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data == "add_chan")
async def add_chan(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Format: link,ID (Masalan: `https://t.me/link,-1001234`)")
    await state.set_state(BotStates.post_url)

@dp.message(BotStates.post_url)
async def save_chan(message: types.Message, state: FSMContext):
    try:
        url, cid = message.text.split(",")
        conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
        cursor.execute("INSERT INTO channels VALUES (?, ?)", (url.strip(), cid.strip()))
        conn.commit() ; conn.close()
        await message.answer("✅ Kanal qo'shildi!", reply_markup=panel_markup)
    except:
        await message.answer("❌ Xato kiritish!")
    await state.clear()

# ---- 8) REKLAMA POST YUBORISH ----
@dp.callback_query(F.data == "send_post")
async def s_post(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Reklama matnini yuboring:")
    await state.set_state(BotStates.post_text)

@dp.message(BotStates.post_text)
async def p_txt(message: types.Message, state: FSMContext):
    await state.update_data(txt=message.text)
    await message.answer("Tugma havolasini (link) yuboring:")
    await state.set_state(BotStates.add_video)

@dp.message(BotStates.add_video)
async def p_lnk(message: types.Message, state: FSMContext):
    data = await state.get_data()
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎬 tomosha qilig", url=message.text.strip())]])
    
    conn = sqlite3.connect('anime.db') ; cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM channels")
    chans = cursor.fetchall() ; conn.close()
    
    for ch in chans:
        try: await bot.send_message(chat_id=ch[0], text=data['txt'], reply_markup=markup)
        except: pass
    await message.answer("✅ Tarqatildi!", reply_markup=panel_markup)
    await state.clear()

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    await call.message.edit_text("🎛 Boshqarish paneli:", reply_markup=panel_markup)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
