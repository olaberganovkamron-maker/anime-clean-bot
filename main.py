import os
import asyncio
import logging
from threading import Thread
from flask import Flask
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# 1. LOGGING
logging.basicConfig(level=logging.INFO)

# ⚠️ SOZLAMALAR (Sening tokening va admin ID raqaming!)
TOKEN = "8931499273:AAEvhf-cHTkCP8klPQ7cbqIX_buedsxz98Q"
ADMIN_IDS = [7164685036]

# 4) 🔊 BOTGA SOZLAR
TEXT_WELCOME = "Xush kelibsiz!"
TEXT_SEND_CODE = "animeni kodini yuboring"
TEXT_SUBSCRIBE = "kanallarga obuna boling"
TEXT_NOT_FOUND = "uzur anime topilmadi boshqa kodin kirtib koring"

# 6) 🔒 MAJBURIY KANALLAR (Xohlagancha kanal qo'shishing mumkin)
REQUIRED_CHANNELS = [
    "@anime_movieuz",
    "@Anicineuz"
]

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# 🗄 MULTI-FUNCTIONAL DATABASE (On-Memory)
USERS_DB = {}       # {user_id: join_date_string}
ANIMES_DB = {}      # {code: {"title": "", "description": "", "photo_id": ""}}
EPISODES_DB = {}    # {code: [{"part_number": 1, "file_id": ""}]}
SUPPORT_DB = []     # Kelgan savollar ro'yxati
ANIMES_COUNTER = 0

# Test uchun 1-kodga tayyor anime qo'shib qo'yilgan
ANIMES_COUNTER += 1
ANIMES_DB[ANIMES_COUNTER] = {
    "title": "Kanan xonimni boshqarish juda oson",
    "description": "Holati: Davom etmoqda\nJanr: Komediya, Romantika",
    "photo_id": None
}
EPISODES_DB[ANIMES_COUNTER] = []

class AdminStates(StatesGroup):
    add_anime_photo = State()
    add_anime_title = State()
    add_anime_desc = State()
    edit_new_value = State()
    add_only_part_code = State()
    add_only_part_video = State()
    send_post = State()
    send_channel_post = State()

class UserStates(StatesGroup):
    waiting_for_support = State()

async def check_subscription(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except Exception: continue
    return True

# 1) 🎛 BOSHQARISH BANERI
def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime Qo'shish", callback_data="adm_add"),
         InlineKeyboardButton(text="🗂 Animelarni Ro'yxati", callback_data="adm_list")],
        [InlineKeyboardButton(text="🎬 Qism Qo'shish", callback_data="adm_add_part"),
         InlineKeyboardButton(text="📢 Kanalga Post", callback_data="adm_chan_post")],
        [InlineKeyboardButton(text="📣 Hammaga Xabar", callback_data="adm_post"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📥 Kelgan Savollar", callback_data="adm_support_view")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id not in USERS_DB:
        USERS_DB[user_id] = datetime.now().strftime("%Y-%m-%d")
        
    if not await check_subscription(user_id):
        buttons = []
        for ch in REQUIRED_CHANNELS:
            buttons.append([InlineKeyboardButton(text=f"📢 {ch} ga a'zo bo'lish", url=f"https://t.me/{ch.replace('@','')}")])
        buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
        await message.answer(TEXT_SUBSCRIBE, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        return

    if user_id in ADMIN_IDS:
        await message.answer("🎛 <b>Boshqarish Paneli:</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🙋‍♂️ Admin bilan bog'lanish", callback_data="user_support")]])
        await message.answer(TEXT_WELCOME, reply_markup=kb)
        await message.answer(TEXT_SEND_CODE)

# 9) 🎬 ANIME QIDIRISH TIZIMI (KOD VA NOMI BO'YICHA)
@dp.message(F.text)
async def global_search_anime(message: Message, state: FSMContext):
    if not await check_subscription(message.from_user.id): return
    if message.text.startswith("/"): return
    
    search_query = message.text.strip().lower()
    found_code = None
    
    if search_query.isdigit():
        code = int(search_query)
        if code in ANIMES_DB: found_code = code
    else:
        for code, anime in ANIMES_DB.items():
            if search_query in anime['title'].lower():
                found_code = code
                break
                
    if found_code:
        anime = ANIMES_DB[found_code]
        episodes = EPISODES_DB.get(found_code, [])
        caption = f"🎬 <b>{anime['title']}</b>\n\n📝 {anime['description']}\n\n🆔 Kod: {found_code}\n🎥 Jami qismlar: {len(episodes)} ta"
        
        buttons = []
        row = []
        for ep in episodes:
            part_num = ep['part_number']
            row.append(InlineKeyboardButton(text=f"{part_num}-qism", callback_data=f"get_part_{found_code}_{part_num}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        if anime['photo_id']: await message.answer_photo(photo=anime['photo_id'], caption=caption, parse_mode="HTML", reply_markup=kb)
        else: await message.answer(caption, parse_mode="HTML", reply_markup=kb)
    else:
        # 10) ⭐️ ADMIN (TOPILMASA ADMINGA YOZISH)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✍️ Animeni Admindan so'rash", callback_data="ask_admin_anime")]])
        await message.answer(TEXT_NOT_FOUND, reply_markup=kb)

@dp.callback_query(F.data == "user_support")
@dp.callback_query(F.data == "ask_admin_anime")
async def user_support_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Topa olmagan anime nomingizni yoki muammoingizni yozib yuboring:")
    await state.set_state(UserStates.waiting_for_support)
    await callback.answer()

@dp.message(UserStates.waiting_for_support)
async def user_support_received(message: Message, state: FSMContext):
    SUPPORT_DB.append({"user_id": message.from_user.id, "username": message.from_user.username, "text": message.text})
    await message.answer("✅ Rahmat! Xabaringiz adminga yuborildi. Tezi orada javob beramiz.")
    await state.clear()

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

# --- ADMIN PANEL FUNKSIYALARI ---

# 2) ➕ ANIME QOSHISH (5-band: Nomi va Kodli qilib boshqarish)
@dp.callback_query(F.data == "adm_add")
async def add_anime_start(callback: CallbackQuery, state: F
