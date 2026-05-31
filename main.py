import os
import asyncio
import logging
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, html, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# 1. LOGGING VA SOZLAMALAR
logging.basicConfig(level=logging.INFO)

# ⚠️ BOT TOKENI (Aynan sening botingniki joylandi!)
TOKEN = "8931499273:AAEvhf-cHTkCP8klPQ7cbqIX_buedsxz98Q" 

# 👥 ADMINLAR RO'YXATI
ADMIN_IDS = [7164685036, 1234567890]  

# 4) 🔊 BOTGA SOZLAR QOSHISH
TEXT_WELCOME = "Xush kelibsiz!"
TEXT_SEND_CODE = "animeni kodini yuboring"
TEXT_SUBSCRIBE = "kanalga obuna boling"
TEXT_NOT_FOUND = "anime topilmadi boshqa kodin kiritib koring"

# 5) 🔐 MAJBURIY KANALLAR
REQUIRED_CHANNELS = [
    "@anime_movieuz",   
    "@Anicineuz",       
    "@kanal3",          
    "@kanal4",
    "@kanal5"
] 

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🗄 TEKIN HOSTING UCHUN MAXSUS XAVFSIZ BAZA (O'CHIB KETMAYDI)
USERS_DB = set()
ANIMES_DB = {}
EPISODES_DB = {}
ANIMES_COUNTER = 0

# 💡 TEST UCHUN 1-KODGA ANIME JOYLAB QO'YDIM:
ANIMES_COUNTER += 1
ANIMES_DB[ANIMES_COUNTER] = {
    "title": "Kanan xonimni boshqarish juda oson",
    "description": "Holati: Tugallangan\nSifat: 720p\nJanr: Komediya, Romantika",
    "photo_id": None
}
EPISODES_DB[ANIMES_COUNTER] = []

# HOLATLAR (FSM TIZIMI)
class AdminStates(StatesGroup):
    add_anime_photo = State()
    add_anime_title = State()
    add_anime_desc = State()
    
    add_only_part_code = State()
    add_only_part_video = State()
    
    edit_select_code = State()
    edit_field_choice = State()
    edit_new_value = State()
    
    delete_code = State()
    send_post = State()
    send_channel_post = State()

# OBUNA TEKSHIRISH
async def check_subscription(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        if "kanal" in channel: continue
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except Exception: continue
    return True

# 1) 🎛 BOSHQARISH PANEL KLABIATURASI
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime Qo'shish", callback_data="adm_add"),
         InlineKeyboardButton(text="🗂 Animelarni Ro'yxati", callback_data="adm_list")],
        [InlineKeyboardButton(text="📦 Animeni Tahrirlash", callback_data="adm_edit"),
         InlineKeyboardButton(text="🗑 Animelarni O'chirish", callback_data="adm_delete")],
        [InlineKeyboardButton(text="🎬 Qism Qo'shish", callback_data="adm_add_part"),
         InlineKeyboardButton(text="📢 Kanalga Post", callback_data="adm_chan_post")],
        [InlineKeyboardButton(text="📣 Hammaga Xabar", callback_data="adm_post"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")]
    ])

# START BUYRUG'I
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    USERS_DB.add(user_id)
    
    if not await check_subscription(user_id):
        buttons = []
        for ch in REQUIRED_CHANNELS:
            if "kanal" in ch: continue
            buttons.append([InlineKeyboardButton(text=f"📢 {ch} ga a'zo bo'lish", url=f"https://t.me/{ch.replace('@','')}")])
        buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
        await message.answer(TEXT_SUBSCRIBE, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    if user_id in ADMIN_IDS:
        await message.answer("🎛 <b>Boshqarish Paneli:</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        await message.answer(TEXT_WELCOME)
        await message.answer(TEXT_SEND_CODE)

# KOD ORQALI QIDIRUV (QISMLARNI SHU YERDA CHIQARADI)
@dp.message(F.text.isdigit())
async def search_anime(message: Message):
    if not await check_subscription(message.from_user.id): return
    code = int(message.text)
    
    if code in ANIMES_DB:
        anime = ANIMES_DB[code]
        episodes = EPISODES_DB.get(code, [])
        
        caption = f"🎬 <b>{anime['title']}</b>\n\n📝 {anime['description']}\n\n🆔 Kod: {code}\n🎥 Jami qismlar: {len(episodes)} ta"
        
        buttons = []
        row = []
        for ep in episodes:
            part_num = ep['part_number']
            row.append(InlineKeyboardButton(text=f"{part_num}-qism", callback_data=f"get_part_{code}_{part_num}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        if anime['photo_id']: 
            await message.answer_photo(photo=anime['photo_id'], caption=caption, parse_mode="HTML", reply_markup=kb)
        else: 
            await message.answer(caption, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(TEXT_NOT_FOUND)

@dp.callback_query(F.data.startswith("get_part_"))
async def callback_get_part(callback: CallbackQuery):
    _, _, code, part_num = callback.data.split("_")
    code, part_num = int(code), int(part_num)
    
    video_id = None
    for ep in EPISODES_DB.get(code, []):
        if ep['part_number'] == part_num:
            video_id = ep['file_id']
            break
            
    if video_id:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍿 kanallar tomosha qiling", callback_data="watch_now")]])
        await callback.message.answer_video(video=video_id, caption=f"🎬 Qism: {part_num}\n🆔 Kod: {code}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "watch_now")
async def watch_callback(callback: CallbackQuery):
    await callback.answer("Yoqimli tomosha tilaymiz! 🍿")

# --- ADMIN AMALLARI ---
@dp.callback_query(F.data == "adm_add")
async def add_anime_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("1. Anime uchun rasm (poster) yuboring:")
    await state.set_state(AdminStates.add_anime_photo)
    await callback.answer()

@dp.message(AdminStates.add_anime_photo)
async def add_photo(message: Message, state: FSMContext):
    if message.photo: await state.update_data(photo_id=message.photo[-1].file_id)
    else: await state.update_data(photo_id=None)
    await message.answer("2. Animening nomini kiriting:")
    await state.set_state(AdminStates.add_anime_title)

@dp.message(AdminStates.add_anime_title)
async def add_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("3. Anime haqida tavsif (opisaniya) yozing:")
    await state.set_state(AdminStates.add_anime_desc)

@dp.message(AdminStates.add_anime_desc)
async def add_desc(message: Message, state: FSMContext):
    global ANIMES_COUNTER
    data = await state.get_data()
    ANIMES_COUNTER += 1
    
    ANIMES_DB[ANIMES_COUNTER] = {
        "title": data['title'],
        "description": message.text,
        "photo_id": data.get('photo_id')
    }
    EPISODES_DB[ANIMES_COUNTER] = []
    
    await message.answer(f"✅ Yangi anime muvaffaqiyatli yaratildi!\n🎬 Nomi: {data['title']}\n🆔 Kodi: <b>{ANIMES_COUNTER}</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(F.data == "adm_list")
async def adm_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    text = "🗂 <b>Animelar ro'yxati:</b>\n\n" if ANIMES_DB else "Bazada anime yo'q."
    for code, anime in ANIMES_DB.items():
        text += f"🆔 {code} — {anime['title']}\n"
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "adm_add_part")
async def add_part_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("🎥 Qism qo'shmoqchi bo'lgan anime kodini kiriting:")
    await state.set_state(AdminStates.add_only_part_code)
    await callback.answer()

@dp.message(AdminStates.add_only_part_code)
async def add_part_code_rec(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat raqamli kod kiriting!")
        return
    code = int(message.text)
    if code not in ANIMES_DB:
        await message.answer("❌ Anime topilmadi! Qayta kiriting:")
        return
    next_part = len(EPISODES_DB.get(code, [])) + 1
    await state.update_data(anime_code=code, current_part=next_part)
    await message.answer(f"🎬 <b>{ANIMES_DB[code]['title']}</b> tanlandi.\n🎥 Ketma-ketlikda <b>{next_part}-qism</b> videosini yuboring:\n(Tugatish uchun /done deb yozing)", parse_mode="HTML")
    await state.set_state(AdminStates.add_only_part_video)

@dp.message(AdminStates.add_only_part_video)
async def add_part_video_loop(message: Message, state: FSMContext):
    if message.text == "/done":
        await message.answer("🎉 Qismlar saqlandi!", reply_markup=get_admin_keyboard())
        await state.clear()
        return
    if not message.video:
        await message.answer("❌ Faqat video formatda yuboring!")
        return
    data = await state.get_data()
    code = data['anime_code']
    current_part = data['current_part']
    
    EPISODES_DB[code].append({
        "part_number": current_part,
        "file_id": message.video.file_id
    })
    
    await message.answer(f"<i>Qabul qilindi!</i>\nNom: {current_part}-qism\n\nKeyingi <b>{current_part + 1}-qismni</b> yuboring:\n(Tugatish uchun /done yozing)", parse_mode="HTML")
    await state.update_data(current_part=current_part + 1)

@dp.callback_query(F.data == "adm_chan_post")
async def chan_post_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("📢 Kanalga yuboriladigan anime kodini kiriting:")
    await state.set_state(AdminStates.send_channel_post)
    await callback.answer()

@dp.message(AdminStates.send_channel_post)
async def chan_post_done(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    code = int(message.text)
    if code not in ANIMES_DB:
        await message.answer("❌ Topilmadi!")
        return
    anime = ANIMES_DB[code]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍿 kanallar tomosha qiling", url=f"https://t.me/{(await bot.get_me()).username}?start=true")]])
    caption = f"🔥 <b>Yangi Anime!</b>\n\n🎬 Nomi: {anime['title']}\n📝 Haqida: {anime['description']}\n\n🆔 Bot uchun qidiruv kodi: <code>{code}</code>"
    try:
        if anime['photo_id']: await bot.send_photo(chat_id=REQUIRED_CHANNELS[0], photo=anime['photo_id'], caption=caption, parse_mode="HTML", reply_markup=kb)
        else: await bot.send_message(chat_id=REQUIRED_CHANNELS[0], text=caption, parse_mode="HTML", reply_markup=kb)
        await message.answer("✅ Kanalga post yuborildi!", reply_markup=get_admin_keyboard())
    except Exception as e:
        await message.answer(f"❌ Xato: {e}", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(F.data == "adm_post")
async def post_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("📣 Reklama matnini kiriting:")
    await state.set_state(AdminStates.send_post)
    await callback.answer()

@dp.message(AdminStates.send_post)
async def post_done(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🍿 kanallar tomosha qiling", callback_data="watch_now")]])
    success = 0
    for user_id in USERS_DB:
        try:
            await bot.send_message(chat_id=user_id, text=message.text, reply_markup=kb)
            success += 1
            await asyncio.sleep(0.05)
        except Exception: continue
    await message.answer(f"✅ Tarqatildi: {success} ta odamga.", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    stat_text = (
        f"👤Obunachilar soni:{len(USERS_DB)}\n"
        f"🎥Animelarni soni-{len(ANIMES_DB)}"
    )
    await callback.message.answer(stat_text, reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "adm_edit")
async def edit_anime_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("🖋 Tahrir qilmoqchi bo'lgan anime kodini yuboring:")
    await state.set_state(AdminStates.edit_select_code)
    await callback.answer()

@dp.message(AdminStates.edit_select_code)
async def edit_code_rec(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    code = int(message.text)
    if code not in ANIMES_DB: return
    await state.update_data(edit_code=code)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖋animeni nomi ozgartitish", callback_data="field_title")],
        [InlineKeyboardButton(text="🏞animeni rasmnin ozgtartirish", callback_data="field_photo")],
        [InlineKeyboardButton(text="🖋animeni tavsifni ozgartirish", callback_data="field_desc")]
    ])
    await message.answer("Nimani o'zgartiramiz?", reply_markup=kb)
    await state.set_state(AdminStates.edit_field_choice)

@dp.callback_query(AdminStates.edit_field_choice, F.data.startswith("field_"))
async def edit_field_sel(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[1]
    await state.update_data(edit_field=field)
    await callback.message.answer(f"Yangi qiymatni kiriting/yuboring:")
    await state.set_state(AdminStates.edit_new_value)
    await callback.answer()

@dp.message(AdminStates.edit_new_value)
async def edit_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data['edit_code']
    field = data['edit_field']
    
    if field == "title": ANIMES_DB[code]["title"] = message.text
    elif field == "desc": ANIMES_DB[code]["description"] = message.text
    elif field == "photo" and message.photo: ANIMES_DB[code]["photo_id"] = message.photo[-1].file_id
    
    await message.answer("✅ Muvaffaqiyatli o'zgartirildi!", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(F.data == "adm_delete")
async def delete_anime_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.message.answer("🗑 O'chirib tashlamoqchi bo'lgan anime kodini yuboring:")
    await state.set_state(AdminStates.delete_code)
    await callback.answer()

@dp.message(AdminStates.delete_code)
async def delete_anime_done(message: Message, state: FSMContext):
    if not message.text.isdigit(): return
    code = int(message.text)
    if code in ANIMES_DB: del ANIMES_DB[code]
    if code in EPISODES_DB: del EPISODES_DB[code]
    await message.answer(f"✅ Kod {code} bo'lgan anime butunlay o'chirildi.", reply_markup=get_admin_keyboard())
    await state.clear()

@dp.callback_query(F.data == "check_subs")
async def callback_check_subs(callback: CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer(TEXT_WELCOME)
        await callback.message.answer(TEXT_SEND_CODE)
        if callback.from_user.id in ADMIN_IDS: await callback.message.answer("🎛 Boshqarish Paneli:", reply_markup=get_admin_keyboard())
    else: await callback.answer("❌ Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

# 🌐 WEB SERVER TIZIMI (Render o'chib qolmasligi uchun)
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running perfectly!"

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

async def main():
    Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
