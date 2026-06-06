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
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web

# --- SOZLAMALAR ---
BOT_TOKEN = "8536249870:AAFLnOA9kQAetkcnQqASuyK52yB78ovNqgo" # <--- O'zingizning tokeningizni yozing!
ADMIN_ID = 7164685036  # <--- O'zingizning Telegram ID raqamingizni yozing!

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- MA'LUMOTLAR BAZASI (SQLite) ---
conn = sqlite3.connect("anime_bot.db")
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, joined_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY, link TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS animelar (
    kod TEXT PRIMARY KEY, nomi TEXT, tavsif TEXT, rasm TEXT, video TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS qismlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT, anime_kod TEXT, qism_raqam INTEGER, video_id TEXT)''')
conn.commit()

# --- FSM STATES ---
class AdminStates(StatesGroup):
    add_channel_id = State()
    add_channel_link = State()
    anime_kod = State()
    anime_nomi = State()
    anime_tavsif = State()
    anime_media = State() # Rasm va video uchun umumiy
    # Tahrirlash bo'limi
    edit_nomi = State()
    edit_rasm = State()
    edit_tavsif = State()
    edit_kod = State()
    # Qism qo'shish
    add_qism_video = State()
    # Post yuborish
    post_text = State()
    post_anime_kod = State()
    # Admin murojaat
    user_murojaat = State()

# --- REPLIES ---
def get_admin_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎛 Boshqarish baneri")
    kb.button(text="➕ Anime qo'shish")
    kb.button(text="🗂 Animelar ro'yxati")
    kb.button(text="🔒 Majburiy kanallar")
    kb.button(text="📊 Statistika")
    kb.button(text="📤 Kanalga post yuborish")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# --- OBUNA TEKSHIRISH ---
async def check_sub(user_id):
    cursor.execute("SELECT id FROM channels")
    channels = cursor.fetchall()
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            continue
    return True

def get_sub_keyboard():
    builder = InlineKeyboardBuilder()
    cursor.execute("SELECT id, link FROM channels")
    for row in cursor.fetchall():
        builder.button(text="Obuna bo'lish 📢", url=row[1])
    builder.button(text="✅ Tekshirish", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()

# --- FOYDALANUVCHILAR REJIMI ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT OR IGNORE INTO users (id, joined_date) VALUES (?, ?)", (user_id, now))
    conn.commit()

    if user_id == ADMIN_ID:
        await message.answer("Xush kelibsiz, Admin! 🎛", reply_markup=get_admin_menu())
        return

    if not await check_sub(user_id):
        await message.answer("🔊 Kanallarga obuna boling tekashirish:", reply_markup=get_sub_keyboard())
        return

    # Foydalanuvchiga start bosilgandagi matn
    await message.answer("🔊 xush kelibsiz,animeni kodini yuboring:")

@dp.callback_query(F.data == "check_subscription")
async def check_sub_callback(callback: types.CallbackQuery):
    if await check_sub(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer("🎉 Rahmat! Animening kodini yuboring:")
    else:
        await callback.answer("❌ Hamma kanallarga obuna bo'lmadingiz!", show_alert=True)

# 10) Admin (Agar odam qidirganini topolmasa)
@dp.message(F.text == "✍️ Adminga yozish")
async def murojaat_start(message: types.Message, state: FSMContext):
    await message.answer("Topolmagan animengiz nomini yozing, admin tez orada qo'shadi:")
    await state.set_state(AdminStates.user_murojaat)

@dp.message(AdminStates.user_murojaat)
async def murojaat_end(message: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"⭐️ **Topilmagan Anime So'rovi!**\nFoydalanuvchi: [{message.from_user.full_name}](tg://user?id={message.from_user.id})\nAnime nomi: {message.text}", parse_mode="Markdown")
    await message.answer("Xabaringiz adminga yetkazildi! Rahmat. ⭐")
    await state.clear()

# 9) Anime qidirish (Kod orqali chiqarish)
@dp.message(lambda msg: msg.text and not msg.text.startswith("/"))
async def search_anime(message: types.Message):
    # Admin tugmalari bo'lsa chetlab o'tish
    if message.from_user.id == ADMIN_ID and message.text in ["🎛 Boshqarish baneri", "➕ Anime qo'shish", "🗂 Animelar ro'yxati", "🔒 Majburiy kanallar", "📊 Statistika", "📤 Kanalga post yuborish"]:
        return

    if not await check_sub(message.from_user.id):
        await message.answer("🔊 Kanallarga obuna boling tekashirish:", reply_markup=get_sub_keyboard())
        return

    kod = message.text.strip()
    cursor.execute("SELECT nomi, tavsif, rasm, video FROM animelar WHERE kod=?", (kod,))
    anime = cursor.fetchone()

    if anime:
        nomi, tavsif, rasm, video = anime
        text = f"🎬 **{nomi}**\n\n📝 {tavsif}\n\n🔑 Kod: {kod}"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🎬 Tomosha qilish", callback_data=f"view_parts_{kod}")
        
        if rasm:
            await message.answer_photo(photo=rasm, caption=text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        elif video:
            await message.answer_video(video=video, caption=text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        else:
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        kb = ReplyKeyboardBuilder()
        kb.button(text="✍️ Adminga yozish")
        await message.answer("🔊 uzur anime topilmadi boshqa kodin kirtib koring", reply_markup=kb.as_markup(resize_keyboard=True))

# 8) Tomosha qilish bosilganda qismlarni ko'rsatish
@dp.callback_query(F.data.startswith("view_parts_"))
async def view_parts(callback: types.CallbackQuery):
    kod = callback.data.split("_")[2]
    cursor.execute("SELECT qism_raqam FROM qismlar WHERE anime_kod=? ORDER BY qism_raqam ASC", (kod,))
    rows = cursor.fetchall()
    
    if not rows:
        await callback.answer("Bu animening qismlari hali yuklanmagan!", show_alert=True)
        return
        
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=f"{row[0]}-qism 🎥", callback_data=f"show_part_{kod}_{row[0]}")
    builder.adjust(3)
    await callback.message.answer(f"🎞 Qismlar ro'yxati:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("show_part_"))
async def show_single_part(callback: types.CallbackQuery):
    _, _, kod, qism = callback.data.split("_")
    cursor.execute("SELECT video_id FROM qismlar WHERE anime_kod=? AND qism_raqam=?", (kod, qism))
    row = cursor.fetchone()
    if row:
        await callback.message.answer_video(video=row[0], caption=f"🎬 Kod: {kod}\n🎞 {qism}-qism")
    await callback.answer()


# --- ADMIN FUNKSIYALARI ---
# 1) Boshqarish baneri
@dp.message(F.text == "🎛 Boshqarish baneri")
async def admin_banner(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🎛 **Boshqarish baneri**\n\nUshbu panel orqali siz animelarni boshqarishingiz, majburiy kanallarni sozlashingiz va statistikani ko'rishingiz mumkin.")

# 7) Statistika
@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    now = datetime.now()
    day1 = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    day3 = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    day7 = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= ?", (day1,))
    k1 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= ?", (day3,))
    k3 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date >= ?", (day7,))
    k7 = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM animelar")
    total_anime = cursor.fetchone()[0]
    
    text = (f"📊 **Statistika**\n\n"
            f"👤 obunachilarni soni-{total_users}\n"
            f"1kun-{k1}\n"
            f"3kun-{k3}\n"
            f"7kun-{k7}\n"
            f"🎞 animelarni soni-{total_anime}")
    await message.answer(text)

# 6) Majburiy kanal qo'shish (Xohlagancha qo'shish imkoniyati)
@dp.message(F.text == "🔒 Majburiy kanallar")
async def manage_channels(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT id, link FROM channels")
    rows = cursor.fetchall()
    text = "🔒 **Majburiy kanallar ro'yxati:**\n\n"
    builder = InlineKeyboardBuilder()
    for row in rows:
        text += f"🔹 ID: `{row[0]}` | Link: {row[1]}\n"
        builder.button(text=f"🗑 {row[0]} o'chirish", callback_data=f"del_ch_{row[0]}")
    
    builder.button(text="➕ Yangi kanal qo'shish", callback_data="add_new_channel")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup())

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
    await message.answer("✅ Kanal muvaffaqiyatli qo'shildi!", reply_markup=get_admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_channel(callback: types.CallbackQuery):
    ch_id = callback.data.split("_")[2]
    cursor.execute("DELETE FROM channels WHERE id=?", (ch_id,))
    conn.commit()
    await callback.answer("Kanal o'chirildi!", show_alert=True)
    await callback.message.delete()

# 2, 5 va 12) Anime yaratish (Rasm ham, video ham qo'shish imkoniyati)
@dp.message(F.text == "➕ Anime qo'shish")
async def add_anime_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔑 Yangi anime uchun unikal KOD kiriting:")
    await state.set_state(AdminStates.anime_kod)

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
    await message.answer("🏞 Animening RASMI yoki VIDEOSINI yuboring (Poster uchun):")
    await state.set_state(AdminStates.anime_media)

@dp.message(AdminStates.anime_media)
async def add_anime_media(message: types.Message, state: FSMContext):
    rasm = ""
    video = ""
    if message.photo:
        rasm = message.photo[-1].file_id
    elif message.video:
        video = message.video.file_id
    else:
        await message.answer("Iltimos, rasm yoki video yuboring!")
        return

    data = await state.get_data()
    cursor.execute("INSERT OR REPLACE INTO animelar (kod, nomi, tavsif, rasm, video) VALUES (?, ?, ?, ?, ?)",
                   (data['kod'], data['nomi'], data['tavsif'], rasm, video))
    conn.commit()
    
    await message.answer("✅ Anime muvaffaqiyatli saqlandi!", reply_markup=get_admin_menu())
    await state.clear()

# 3) Animelar ro'yxati va TO'LIQ TAHRIRLASH
@dp.message(F.text == "🗂 Animelar ro'yxati")
async def list_anime(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT kod, nomi vomi FROM animelar")
    rows = cursor.fetchall()
    
    if not rows:
        await message.answer("Bazada animelar mavjud emas.")
        return
        
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=f"🎬 {row[1]} (Kod: {row[0]})", callback_data=f"manage_{row[0]}")
    builder.adjust(1)
    await message.answer("🗂 Tahrirlash yoki o'chirish uchun animeni tanlang:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("manage_"))
async def manage_single_anime(callback: types.CallbackQuery):
    kod = callback.data.split("_")[1]
    cursor.execute("SELECT nomi FROM animelar WHERE kod=?", (kod,))
    row = cursor.fetchone()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✒️ Nomini o'zgartirish", callback_data=f"edit_nomi_{kod}")
    builder.button(text="🏞 Rasmini/Videosini o'zgartirish", callback_data=f"edit_rasm_{kod}")
    builder.button(text="✒️ Tavsifni o'zgartirish", callback_data=f"edit_tavsif_{kod}")
    builder.button(text="🔑 Kodini o'zgartirish", callback_data=f"edit_kod_{kod}")
    builder.button(text="🎬 Qism qo'shish", callback_data=f"add_part_{kod}")
    builder.button(text="🗑 O'chirish", callback_data=f"delete_anime_{kod}")
    builder.adjust(2)
    
    await callback.message.answer(f"🎬 **{row[0]}** banyeri boshqaruvi:", reply_markup=builder.as_markup())
    await callback.answer()

# --- TAHRIRLASH LOXIKASI (3-band to'liq funksiyalari) ---
@dp.callback_query(F.data.startswith("edit_nomi_"))
async def edit_nomi_start(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(kod=callback.data.split("_")[2])
    await callback.message.answer("Yangi anime nomini yuboring:")
    await state.set_state(AdminStates.edit_nomi)
    await callback.answer()

@dp.message(AdminStates.edit_nomi)
async def edit_nomi_end(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE animelar SET nomi=? WHERE kod=?", (message.text, data['kod']))
    conn.commit()
    await message.answer("✅ Animening nomi o'zgartirildi!", reply_markup=get_admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("edit_tavsif_"))
async def edit_tavsif_start(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(kod=callback.data.split("_")[2])
    await callback.message.answer("Yangi tavsifni (opisaniya) yuboring:")
    await state.set_state(AdminStates.edit_tavsif)
    await callback.answer()

@dp.message(AdminStates.edit_tavsif)
async def edit_tavsif_end(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("UPDATE animelar SET tavsif=? WHERE kod=?", (message.text, data['kod']))
    conn.commit()
    await message.answer("✅ Anime tavsifi o'zgartirildi!", reply_markup=get_admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("edit_rasm_"))
async def edit_rasm_start(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(kod=callback.data.split("_")[2])
    await callback.message.answer("Yangi RASM yoki VIDEO yuboring:")
    await state.set_state(AdminStates.edit_rasm)
    await callback.answer()

@dp.message(AdminStates.edit_rasm)
async def edit_rasm_end(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.photo:
        cursor.execute("UPDATE animelar SET rasm=?, video='' WHERE kod=?", (message.photo[-1].file_id, data['kod']))
    elif message.video:
        cursor.execute("UPDATE animelar SET video=?, rasm='' WHERE kod=?", (message.video.file_id, data['kod']))
    else:
        await message.answer("Iltimos, rasm yoki video yuboring!")
        return
    conn.commit()
    await message.answer("✅ Anime media fayli o'zgartirildi!", reply_markup=get_admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("edit_kod_"))
async def edit_kod_start(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(old_kod=callback.data.split("_")[2])
    await callback.message.answer("Yangi unikal KOD yuboring:")
    await state.set_state(AdminStates.edit_kod)
    await callback.answer()

@dp.message(AdminStates.edit_kod)
async def edit_kod_end(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_kod = message.text.strip()
    try:
        cursor.execute("UPDATE animelar SET kod=? WHERE kod=?", (new_kod, data['old_kod']))
        cursor.execute("UPDATE qismlar SET anime_kod=? WHERE anime_kod=?", (new_kod, data['old_kod']))
        conn.commit()
        await message.answer("✅ Anime kodi muvaffaqiyatli o'zgartirildi!", reply_markup=get_admin_menu())
    except Exception:
        await message.answer("Bu kod allaqachon band, boshqa kod kiriting.")
    await state.clear()

@dp.callback_query(F.data.startswith("delete_anime_"))
async def delete_anime(callback: types.CallbackQuery):
    kod = callback.data.split("_")[2]
    cursor.execute("DELETE FROM animelar WHERE kod=?", (kod,))
    cursor.execute("DELETE FROM qismlar WHERE anime_kod=?", (kod,))
    conn.commit()
    await callback.answer("Anime va uning qismlari o'chirildi!", show_alert=True)
    await callback.message.delete()

# 11) Qism qo'shish (Ketma-ket rejim: 1-qismni yuboring -> 2-qismni yuboring)
@dp.callback_query(F.data.startswith("add_part_"))
async def add_part_start(callback: types.CallbackQuery, state: FSMContext):
    kod = callback.data.split("_")[2]
    cursor.execute("SELECT COUNT(*) FROM qismlar WHERE anime_kod=?", (kod,))
    next_part = cursor.fetchone()[0] + 1
    
    await state.update_data(kod=kod, next_part=next_part)
    await callback.message.answer(f"🎞 {next_part}-qismni yuboring:")
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
    
    await message.answer(f"✅ {data['next_part']}-qism saqland")
    
    next_part = data['next_part'] + 1
    await state.update_data(next_part=next_part)
    await message.answer(f"🎞 {next_part}-qismni yuboring (to'xtatish uchun /cancel kiriting):")

# 8) Kanalga post yuborish ("tomosha qilig" inline tugmasi bilan)
@dp.message(F.text == "📤 Kanalga post yuborish")
async def post_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Kanalga yuboriladigan post matnini kiriting:")
    await state.set_state(AdminStates.post_text)

@dp.message(AdminStates.post_text)
async def post_text_rec(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer("Ushbu post qaysi animega tegishli? O'sha animening KODINI yuboring:")
    await state.set_state(AdminStates.post_anime_kod)

@dp.message(AdminStates.post_anime_kod)
async def post_channels_end(message: types.Message, state: FSMContext):
    kod = message.text.strip()
    cursor.execute("SELECT nomi FROM animelar WHERE kod=?", (kod,))
    anime = cursor.fetchone()
    
    if not anime:
        await message.answer("Bunday kodli anime topilmadi, qaytadan kod yuboring:")
        return
        
    data = await state.get_data()
    bot_user = await bot.get_me()
    
    # "tomosha qilig" tugmasi botga start havola (deeplink) bilan ulanadi
    builder = InlineKeyboardBuilder()
    builder.button(text="🍿 Tomosha qiling", url=f"https://t.me/{bot_user.username}?start=true")
    
    cursor.execute("SELECT id FROM channels")
    channels = cursor.fetchall()
    
    success = 0
    for ch in channels:
        try:
            await bot.send_message(chat_id=ch[0], text=data['text'], reply_markup=builder.as_markup())
            success += 1
        except Exception:
            continue
            
    await message.answer(f"✅ Post {success} ta majburiy kanalga muvaffaqiyatli yuborildi!")
    await state.clear()

@dp.message(Command("cancel"))
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=get_admin_menu())

# --- RENDER SERVER INTEGRATION ---
async def handle(request):
    return web.Response(text="Bot is running completely!")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 7860))
    site = web.TCPSite(runner, '0.0.0.0', port)
    asyncio.create_task(site.start())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
