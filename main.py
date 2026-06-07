import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- SOZLAMALAR ---
BOT_TOKEN = "8536249870:AAFLnOA9kQAetkcnQqASuyK52yB78ovNqgo" # @animovie_uzz_bot tokeni
ADMIN_ID = 7164685036  # Sizning shaxsiy Telegram ID raqamingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- MA'LUMOTLAR BAZASI ---
conn = sqlite3.connect("anime_bot.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, joined_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY, link TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS animelar (kod TEXT PRIMARY KEY, nomi TEXT, tavsif TEXT, rasm TEXT, video TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS qismlar (id INTEGER PRIMARY KEY AUTOINCREMENT, anime_kod TEXT, qism_raqam INTEGER, video_id TEXT)''')
conn.commit()

class AdminStates(StatesGroup):
    add_channel_id = State()
    add_channel_link = State()
    anime_kod = State()
    anime_nomi = State()
    anime_tavsif = State()
    anime_media = State() 
    edit_nomi = State()
    edit_rasm = State()
    edit_tavsif = State()
    edit_kod = State()
    add_qism_video = State()
    post_media = State()
    post_anime_kod = State()

def get_admin_inline_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎛 Boshqarish baneri", callback_data="adm_banner")
    kb.button(text="➕ Anime qo'shish", callback_data="adm_add_anime")
    kb.button(text="🗂 Animelar ro'yxati", callback_data="adm_list_anime")
    kb.button(text="🔒 Majburiy kanallar", callback_data="adm_channels")
    kb.button(text="📊 Statistika", callback_data="adm_stats")
    kb.button(text="📤 Kanalga post yuborish", callback_data="adm_post")
    kb.adjust(2)
    return kb.as_markup()

async def check_sub(user_id):
    cursor.execute("SELECT id FROM channels")
    channels = cursor.fetchall()
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except Exception: continue
    return True

def get_sub_keyboard():
    builder = InlineKeyboardBuilder()
    cursor.execute("SELECT id, link FROM channels")
    for row in cursor.fetchall():
        builder.button(text="Obuna bo'lish 📢", url=row[1])
    builder.button(text="✅ Tekshirish", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(CommandStart())
async def start_cmd(message: types.Message, command: Command = None):
    user_id = message.from_user.id
    now = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT OR IGNORE INTO users (id, joined_date) VALUES (?, ?)", (user_id, now))
    conn.commit()

    if user_id != ADMIN_ID and not await check_sub(user_id):
        await message.answer("🔊 Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return

    if command and command.args:
        await send_anime_by_kod(message, command.args.strip())
        return

    if user_id == ADMIN_ID:
        await message.answer("Xush kelibsiz, Admin! 🎛\nBoshqarish uchun quyidagi tugmalardan foydalaning:", reply_markup=get_admin_inline_menu())
        return

    await message.answer("🔊 Xush kelibsiz, anime kodini yuboring:")

@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: types.CallbackQuery):
    if await check_sub(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("🎉 Rahmat! Animening kodini yuboring:")
    else:
        await callback.answer("❌ Hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

# --- INLINE CALLBACK HANDLERS ---
@dp.callback_query(F.data == "adm_banner")
async def admin_banner(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("🎛 **Boshqarish baneri**\nPanel orqali botni to'liq boshqarishingiz mumkin.")
    await callback.answer()

@dp.callback_query(F.data == "adm_stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    now = datetime.now()
    day1 = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= ?", (day1,))
    k1 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM animelar")
    total_anime = cursor.fetchone()[0]
    
    text = f"📊 **Statistika**\n\n👤 Obunachilar: {total_users}\n✨ Oxirgi sutkada: {k1}\n🎬 Animelar: {total_anime}"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "adm_channels")
async def manage_channels(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT id, link FROM channels")
    rows = cursor.fetchall()
    text = "🔒 **Majburiy kanallar ro'yxati:**\n\n"
    builder = InlineKeyboardBuilder()
    for row in rows:
        text += f"🔹 ID: `{row[0]}` | Link: {row[1]}\n"
        builder.button(text=f"🗑 {row[0]} o'chirish", callback_data=f"del_ch_{row[0]}")
    builder.button(text="➕ Yangi kanal qo'shish", callback_data="add_new_channel")
    builder.adjust(1)
    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "add_new_channel")
async def add_ch_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal ID raqamini yuboring (Masalan: -100123456789):")
    await state.set_state(AdminStates.add_channel_id)
    await callback.answer()

@dp.message(AdminStates.add_channel_id)
async def add_ch_id(message: types.Message, state: FSMContext):
    await state.update_data(ch_id=message.text.strip())
    await message.answer("Kanal havolasini (linkini) yuboring:")
    await state.set_state(AdminStates.add_channel_link)

@dp.message(AdminStates.add_channel_link)
async def add_ch_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT OR REPLACE INTO channels (id, link) VALUES (?, ?)", (data['ch_id'], message.text.strip()))
    conn.commit()
    await message.answer("✅ Kanal majburiy obunaga qo'shildi!", reply_markup=get_admin_inline_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_channel(callback: types.CallbackQuery):
    ch_id = callback.data.split("_")[2]
    cursor.execute("DELETE FROM channels WHERE id=?", (ch_id,))
    conn.commit()
    await callback.answer("Kanal o'chirildi!", show_alert=True)
    await callback.message.delete()

@dp.callback_query(F.data == "adm_add_anime")
async def add_anime_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("🔑 Yangi anime uchun unikal KOD kiriting:")
    await state.set_state(AdminStates.anime_kod)
    await callback.answer()

@dp.message(AdminStates.anime_kod)
async def add_anime_kod(message: types.Message, state: FSMContext):
    await state.update_data(kod=message.text.strip())
    await message.answer("🎬 Animening nomini kiriting:")
    await state.set_state(AdminStates.anime_nomi)

@dp.message(AdminStates.anime_nomi)
async def add_anime_nomi(message: types.Message, state: FSMContext):
    await state.update_data(nomi=message.text)
    await message.answer("📝 Anime uchun tavsif yuboring:")
    await state.set_state(AdminStates.anime_tavsif)

@dp.message(AdminStates.anime_tavsif)
async def add_anime_tavsif(message: types.Message, state: FSMContext):
    await state.update_data(tavsif=message.text)
    await message.answer("🏞 Animening RASMI yoki VIDEOSINI yuboring:")
    await state.set_state(AdminStates.anime_media)

@dp.message(AdminStates.anime_media)
async def add_anime_media(message: types.Message, state: FSMContext):
    rasm, video = "", ""
    if message.photo: rasm = message.photo[-1].file_id
    elif message.video: video = message.video.file_id
    else:
        await message.answer("Iltimos, rasm yoki video yuboring!")
        return
    data = await state.get_data()
    cursor.execute("INSERT OR REPLACE INTO animelar (kod, nomi, tavsif, rasm, video) VALUES (?, ?, ?, ?, ?)",
                   (data['kod'], data['nomi'], data['tavsif'], rasm, video))
    conn.commit()
    await message.answer("✅ Anime muvaffaqiyatli saqlandi!", reply_markup=get_admin_inline_menu())
    await state.clear()

@dp.callback_query(F.data == "adm_list_anime")
async def list_anime(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT kod, nomi FROM animelar")
    rows = cursor.fetchall()
    if not rows:
        await callback.message.answer("Bazada animelar mavjud emas.")
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=f"🎬 {row[1]}", callback_data=f"manage_{row[0]}")
    builder.adjust(1)
    await callback.message.answer("🗂 Tahrirlash uchun animeni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("manage_"))
async def manage_single_anime(callback: types.CallbackQuery):
    kod = callback.data.split("_")[1]
    cursor.execute("SELECT nomi FROM animelar WHERE kod=?", (kod,))
    row = cursor.fetchone()
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Qism qo'shish", callback_data=f"add_part_{kod}")
    builder.button(text="🗑 O'chirish", callback_data=f"delete_anime_{kod}")
    builder.adjust(2)
    await callback.message.answer(f"🎬 **{row[0]}** boshqaruv paneli:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("add_part_"))
async def add_part_start(callback: types.CallbackQuery, state: FSMContext):
    kod = callback.data.split("_")[2]
    cursor.execute("SELECT COUNT(*) FROM qismlar WHERE anime_kod=?", (kod,))
    next_part = cursor.fetchone()[0] + 1
    await state.update_data(kod=kod, next_part=next_part)
    await callback.message.answer(f"🎞 {next_part}-qism videosini yuboring:")
    await state.set_state(AdminStates.add_qism_video)
    await callback.answer()

@dp.message(AdminStates.add_qism_video)
async def add_part_end(message: types.Message, state: FSMContext):
    if not message.video:
        await message.answer("Faqat video yuboring!")
        return
    data = await state.get_data()
    cursor.execute("INSERT INTO qismlar (anime_kod, qism_raqam, video_id) VALUES (?, ?, ?)",
                   (data['kod'], data['next_part'], message.video.file_id))
    conn.commit()
    next_part = data['next_part'] + 1
    await state.update_data(next_part=next_part)
    await message.answer(f"✅ Qism saqlandi! {next_part}-qismni yuboring (yoki to'xtatish uchun /cancel):")

@dp.callback_query(F.data == "adm_post")
async def post_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Kanalga yuboriladigan postni kiriting:")
    await state.set_state(AdminStates.post_media)
    await callback.answer()

@dp.message(AdminStates.post_media)
async def post_media_rec(message: types.Message, state: FSMContext):
    if message.photo: await state.update_data(type="photo", file_id=message.photo[-1].file_id, caption=message.caption or "")
    elif message.video: await state.update_data(type="video", file_id=message.video.file_id, caption=message.caption or "")
    else: await state.update_data(type="text", text=message.text)
    await message.answer("Ushbu post qaysi anime kodiga tegishli?:")
    await state.set_state(AdminStates.post_anime_kod)

@dp.message(AdminStates.post_anime_kod)
async def post_channels_end(message: types.Message, state: FSMContext):
    kod = message.text.strip()
    cursor.execute("SELECT nomi FROM animelar WHERE kod=?", (kod,))
    if not cursor.fetchone():
        await message.answer("Bunday kodli anime topilmadi, qaytadan kiriting:")
        return
    data = await state.get_data()
    bot_user = await bot.get_me()
    builder = InlineKeyboardBuilder()
    builder.button(text="🍿 Tomosha qiling", url=f"https://t.me/{bot_user.username}?start={kod}")
    
    cursor.execute("SELECT id FROM channels")
    channels = cursor.fetchall()
    success = 0
    for ch in channels:
        try:
            if data['type'] == "photo": await bot.send_photo(chat_id=ch[0], photo=data['file_id'], caption=data['caption'], reply_markup=builder.as_markup())
            elif data['type'] == "video": await bot.send_video(chat_id=ch[0], video=data['file_id'], caption=data['caption'], reply_markup=builder.as_markup())
            else: await bot.send_message(chat_id=ch[0], text=data['text'], reply_markup=builder.as_markup())
            success += 1
        except Exception: continue
    await message.answer(f"✅ Post {success} ta kanalga yuborildi!", reply_markup=get_admin_inline_menu())
    await state.clear()

async def send_anime_by_kod(message: types.Message, kod: str):
    cursor.execute("SELECT nomi, tavsif, rasm, video FROM animelar WHERE kod=?", (kod,))
    anime = cursor.fetchone()
    if anime:
        nomi, tavsif, rasm, video = anime
        text = f"🎬 **{nomi}**\n\n📝 {tavsif}\n\n🔑 Kod: {kod}"
        builder = InlineKeyboardBuilder()
        builder.button(text="🎬 Tomosha qilish", callback_data=f"view_parts_{kod}")
        if rasm: await message.answer_photo(photo=rasm, caption=text, reply_markup=builder.as_markup())
        elif video: await message.answer_video(video=video, caption=text, reply_markup=builder.as_markup())
        else: await message.answer(text, reply_markup=builder.as_markup())
    else:
        await message.answer("🔊 Uzr, bunday kodli anime topilmadi.")

@dp.message(lambda msg: msg.text and not msg.text.startswith("/"))
async def search_anime(message: types.Message):
    if not await check_sub(message.from_user.id):
        await message.answer("🔊 Kanallarga obuna bo'ling:", reply_markup=get_sub_keyboard())
        return
    await send_anime_by_kod(message, message.text.strip())

@dp.message(Command("cancel"))
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=get_admin_inline_menu())

async def handle(request): return web.Response(text="Bot is Live!")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    asyncio.create_task(site.start())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
