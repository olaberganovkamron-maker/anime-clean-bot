import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta

# 1. BOT TOKENI VA ASOSIY ADMIN ID
TOKEN = "8939879560:AAFL21GDf3-KcLLGyHElTsTTploMSXLEPaI"
SUPER_ADMIN_ID = 7164685036  # Bot egasi
CHANNEL_USERNAME = "@anime_movieuz" # Asosiy anime kanali

bot = telebot.TeleBot(TOKEN)

# 2. BAZANI ISHGA TUSHIRISH
def init_db():
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS animes (
            code TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            poster_id TEXT,
            views_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anime_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_code TEXT,
            part_number INTEGER,
            file_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            join_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sub_admins (
            admin_id INTEGER PRIMARY KEY,
            username TEXT,
            added_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            channel_name TEXT,
            channel_url TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sub_admins WHERE admin_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def check_sub(user_id):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    for ch in channels:
        ch_id = ch[0]
        try:
            member = bot.get_chat_member(ch_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            continue
    return True

admin_states = {}

def get_stats_text():
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    now = datetime.now()
    one_day_ago = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    seven_days_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    thirty_days_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (one_day_ago,))
    day_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (seven_days_ago,))
    week_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE join_date >= ?", (thirty_days_ago,))
    month_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM animes")
    total_animes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM anime_parts")
    total_parts = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(views_count) FROM animes")
    total_views = cursor.fetchone()[0] or 0
    conn.close()
    
    return (
        f"📊 **BOT STATISTIKASI**\n"
        f"-------------------------\n"
        f"👥 **Foydalanuvchilar:** {total_users} ta\n"
        f"-------------------------\n"
        f"📈 **O'sish dinamikasi:**\n"
        f" 📅 1 kun: +{day_users} | 7 kun: +{week_users} | 31 kun: +{month_users}\n"
        f"-------------------------\n"
        f"🎬 **Kontent:**\n"
        f" 📁 Animelar: {total_animes} ta | 🎞 Qismlar: {total_parts} ta\n"
        f"📥 **Jami yuklanishlar (Counter):** {total_views} marta\n"
        f"-------------------------\n"
        f"⏳ **Holat:** {now.strftime('%d.%m.%Y  %H:%M:%S')}"
    )

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👥 Foydalanuvchilar"))
    markup.add(types.KeyboardButton("👑 VIP Boshqaruvi"), types.KeyboardButton("🎛 Menu"))
    markup.add(types.KeyboardButton("🗃 Animelarni boshqarish"))
    markup.add(types.KeyboardButton("📊 Statistika"), types.KeyboardButton("✉️ Xabar yuborish"))
    markup.add(types.KeyboardButton("🔐 Majburiy obunalar"))
    markup.add(types.KeyboardButton("👮 Adminlar"), types.KeyboardButton("👑 PRO"))
    markup.add(types.KeyboardButton("⚙️ Sozlamalar"), types.KeyboardButton("◀️ Orqaga"))
    return markup

def get_user_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🔍 Animeni qidirish"),
        types.KeyboardButton("🏆 Reytingli anime"),
        types.KeyboardButton("👨‍💻 Admin bilan bog'lanish")
    )
    return markup

# 3. /START BUYRUG'I
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, join_date) VALUES (?, ?)", 
                   (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

    start_args = message.text.split()
    search_query = start_args[1].strip() if len(start_args) > 1 else None

    if not is_admin(user_id):
        if not check_sub(user_id):
            send_sub_keyboard(message.chat.id, search_query)
            return

    if search_query:
        search_anime_process(message.chat.id, search_query)
        return
    
    if is_admin(user_id):
        bot.send_message(message.chat.id, "🤖 **Admin panelga xush kelibsiz!**", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, f"✨ **{first_name}**, botga xush kelibsiz! Anime nomi yoki kodini kiriting:", reply_markup=get_user_keyboard())

def send_sub_keyboard(chat_id, query=None):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_name, channel_url FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        markup.add(types.InlineKeyboardButton(f"📢 {ch[0]}", url=ch[1]))
        
    callback_data = f"check_sub_now_{query}" if query else "check_sub_now_none"
    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data=callback_data))
    
    bot.send_message(
        chat_id, 
        "❌ **Obuna bo'ling!**\n\nBotdan foydalanish uchun homiy kanallarimizga a'zo bo'lishingiz shart. Kanallarga o'tib a'zo bo'ling va pastdagi tekshirish tugmasini bosing: ⏬", 
        parse_mode="Markdown", reply_markup=markup
    )

def send_top_animes(chat_id):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, name, views_count FROM animes ORDER BY views_count DESC LIMIT 10")
    top_animes = cursor.fetchall()
    conn.close()
    
    if not top_animes:
        bot.send_message(chat_id, "⚠️ Hozircha bazada yetarlicha ma'lumot yo'q.")
        return
    
    text = "🏆 **Eng ko'p ko'rilgan animelar (Reyting):**\n\n"
    for i, anime in enumerate(top_animes, 1):
        text += f"{i}. {anime[1]} (Kod: `{anime[0]}`) — 📥 {anime[2]} marta\n"
    
    text += "\n✍️ _Kodni yoki nomini yuborib tomosha qilishingiz mumkin!_"
    bot.send_message(chat_id, text, parse_mode="Markdown")

# 4. MATNLI XABARLAR FILTRI
@bot.message_handler(func=lambda msg: True, content_types=['text', 'video', 'photo'])
def handle_admin_text_buttons(message):
    user_id = message.from_user.id
    
    if is_admin(user_id) and user_id in admin_states:
        handle_admin_inputs(message)
        return

    if not is_admin(user_id):
        if message.content_type == 'text':
            if message.text == "🔍 Animeni qidirish":
                bot.send_message(message.chat.id, "✍️ **Anime ko'rish uchun uning KODINI yoki NOMINI yuboring:**\n\n_Masalan: 105 yoki Naruto_")
                return
            elif message.text == "🏆 Reytingli anime":
                send_top_animes(message.chat.id)
                return
            elif message.text == "👨‍💻 Admin bilan bog'lanish":
                bot.send_message(message.chat.id, "⚠️ **Birorta vaziyat bo'lgan bo'lsa (yoki xatolik yuz bersa) admin bilan bog'laning.**\n\n⚙️ Admin: @anime_movieuz_admin")
                return
            
            if not check_sub(user_id):
                send_sub_keyboard(message.chat.id, message.text.strip())
            else:
                search_anime_process(message.chat.id, message.text.strip())
        return

    # ADMIN TUGMALARI
    if message.text == "🗃 Animelarni boshqarish":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Yangi qo'shish", callback_data="add_anime"),
            types.InlineKeyboardButton("📁 Animelar ro'yxati", callback_data="list_animes_0")
        )
        bot.send_message(message.chat.id, "🗃 **Animelarni boshqarish:**", reply_markup=markup)
        
    elif message.text == "📊 Statistika":
        bot.send_message(message.chat.id, get_stats_text(), parse_mode="Markdown")
        
    elif message.text == "👮 Adminlar":
        show_admins_management_menu(message.chat.id)

    elif message.text == "🔐 Majburiy obunalar":
        show_channels_management_menu(message.chat.id)

    elif message.text == "◀️ Orqaga":
        bot.send_message(message.chat.id, "Asosiy menyu:", reply_markup=get_admin_keyboard())
    else:
        if message.content_type == 'text':
            search_anime_process(message.chat.id, message.text.strip())

def show_channels_management_menu(chat_id):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_name, channel_url FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    text = "🔐 **Majburiy obuna kanallari boshqaruvi**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if not channels:
        text += "⚠️ _Hozircha hech qanday majburiy kanal o'rnatilmagan._"
    else:
        text += f"📋 **Faol kanallar ({len(channels)} ta):**\n"
        for ch in channels:
            text += f"• {ch[1]} (ID: `{ch[0]}`)\n"
            markup.add(types.InlineKeyboardButton(f"🗑 {ch[1]} ni o'chirish", callback_data=f"del_chan_{ch[0]}"))
            
    markup.add(types.InlineKeyboardButton("➕ Yangi Kanal Qo'shish", callback_data="add_new_channel"))
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# 5. INLINE CALLBACK AMALLARI (YANGI TAHRIRLASH TUGMALARI BILAN)
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data.startswith("check_sub_now_"):
        query = data.split("_")[3]
        if check_sub(user_id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ **Rahmat! Obuna tasdiqlandi.**", reply_markup=get_user_keyboard())
            if query != "none":
                search_anime_process(call.message.chat.id, query)
        else:
            bot.answer_callback_query(call.id, "❌ Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
        return

    if data.startswith("get_part_"):
        part_id = data.split("_")[2]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("SELECT anime_code, part_number, file_id FROM anime_parts WHERE id = ?", (part_id,))
        res = cursor.fetchone()
        if res:
            anime_code, part_number, file_id = res
            cursor.execute("SELECT name FROM animes WHERE code = ?", (anime_code,))
            anime_name = cursor.fetchone()[0]
            cursor.execute("UPDATE animes SET views_count = views_count + 1 WHERE code = ?", (anime_code,))
            conn.commit()
            bot.send_video(call.message.chat.id, file_id, caption=f"🎬 **{anime_name}**\n📌 **{part_number}-qism**")
        conn.close()
        bot.answer_callback_query(call.id)
        return

    if not is_admin(user_id): return

    # ADMIN CALLBACKS
    if data == "add_new_channel":
        admin_states[user_id] = {"step": "waiting_for_channel_id"}
        bot.send_message(call.message.chat.id, "🆔 **Kanalning Telegram ID raqamini yoki Username'ini kiriting:**")
        bot.answer_callback_query(call.id)

    elif data.startswith("del_chan_"):
        ch_id = data.split("_")[2]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM channels WHERE channel_id = ?", (ch_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Kanal o'chirildi!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_channels_management_menu(call.message.chat.id)

    elif data == "add_new_admin":
        if user_id != SUPER_ADMIN_ID: return
        admin_states[user_id] = {"step": "waiting_for_admin_id"}
        bot.send_message(call.message.chat.id, "🆔 **Yangi adminning Telegram ID raqamini kiriting:**")
        bot.answer_callback_query(call.id)

    elif data.startswith("del_admin_"):
        if user_id != SUPER_ADMIN_ID: return
        target_id = int(data.split("_")[2])
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sub_admins WHERE admin_id = ?", (target_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Admin o'chirildi!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_admins_management_menu(call.message.chat.id)

    elif data.startswith("list_animes_"):
        page = int(data.split("_")[2])
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("SELECT code, views_count, name FROM animes")
        all_animes = cursor.fetchall()
        conn.close()
        
        if not all_animes:
            bot.answer_callback_query(call.id, "Bazada anime yo'q!", show_alert=True)
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        per_page = 5
        start_idx = page * per_page
        end_idx = start_idx + per_page
        page_items = all_animes[start_idx:end_idx]
        
        for anime in page_items:
            code, views, name = anime
            markup.add(types.InlineKeyboardButton(f"🎬 {name[:15]}.. (Kod: {code}) | 📥 {views} ta", callback_data=f"manage_anime_{code}"))
            
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"list_animes_{page-1}"))
        else:
            nav_buttons.append(types.InlineKeyboardButton("•", callback_data="none"))
            
        total_pages = (len(all_animes) + per_page - 1) // per_page
        nav_buttons.append(types.InlineKeyboardButton(f"({page+1}/{total_pages})", callback_data="none"))
        
        if end_idx < len(all_animes):
            nav_buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"list_animes_{page+1}"))
        else:
            nav_buttons.append(types.InlineKeyboardButton("•", callback_data="none"))
            
        markup.row(*nav_buttons)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="📁 **Animelar ro'yxati va ko'rilganlar soni:**", reply_markup=markup)

    elif data.startswith("manage_anime_"):
        code = data.split("_")[2]
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_anime_management_menu(call.message.chat.id, code)

    elif data.startswith("manage_parts_"):
        code = data.split("_")[2]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM anime_parts WHERE anime_code = ?", (code,))
        count = cursor.fetchone()[0]
        conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Qism qo'shish", callback_data=f"add_part_{code}"),
                   types.InlineKeyboardButton("◀️ Orqaga", callback_data=f"manage_anime_{code}"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"📦 Jami qismlar: {count} ta", reply_markup=markup)

    elif data.startswith("add_part_"):
        code = data.split("_")[2]
        admin_states[user_id] = {"step": "infinite_adding_parts", "code": code}
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("◀️ Orqaga"))
        bot.send_message(call.message.chat.id, "🎬 Videosini ketma-ket yuboring:", reply_markup=markup)

    # 🛠 1-5 SIZ SO'RAGAN YANGI TAHRIRLASH CALLBACK'LARI
    elif data.startswith("edit_name_"): # 1. Nomi
        code = data.split("_")[2]
        admin_states[user_id] = {"step": "editing_name", "code": code}
        bot.send_message(call.message.chat.id, "✍️ **Yangi ANIME NOMINI kiriting:**")
        bot.answer_callback_query(call.id)

    elif data.startswith("edit_poster_"): # 2. Rasmi
        code = data.split("_")[2]
        admin_states[user_id] = {"step": "editing_poster", "code": code}
        bot.send_message(call.message.chat.id, "🖼 **Yangi POSTER (Rasm) yuboring:**")
        bot.answer_callback_query(call.id)

    elif data.startswith("edit_desc_"): # 3. Tavsifi
        code = data.split("_")[2]
        admin_states[user_id] = {"step": "editing_desc", "code": code}
        bot.send_message(call.message.chat.id, "📝 **Yangi ANIME TAVSIFINI (Description) kiriting:**")
        bot.answer_callback_query(call.id)

    elif data.startswith("edit_code_"): # 4. Kodi
        code = data.split("_")[2]
        admin_states[user_id] = {"step": "editing_code", "old_code": code}
        bot.send_message(call.message.chat.id, "🔢 **Yangi unikal ANIME KODINI kiriting:**")
        bot.answer_callback_query(call.id)

    elif data.startswith("delete_anime_"): # 5. O'chirish
        code = data.split("_")[2]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM animes WHERE code = ?", (code,))
        cursor.execute("DELETE FROM anime_parts WHERE anime_code = ?", (code,)) # Qismlarni ham o'chirish
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "❌ Anime butunlay o'chirildi!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ Anime va uning barcha qismlari bazadan o'chirib tashlandi.", reply_markup=get_admin_keyboard())

    elif data.startswith("post_channel_"):
        code = data.split("_")[2]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, poster_id FROM animes WHERE code = ?", (code,))
        res = cursor.fetchone()
        conn.close()
        if not res: return
        name, description, poster_id = res
        share_link = f"https://t.me/{bot.get_me().username}?start={code}"
        post_caption = f"🔢 **{code}**\n\n🎬 **{name}**\n-----------------------------------------\n{description}"
        channel_markup = types.InlineKeyboardMarkup()
        channel_markup.add(types.InlineKeyboardButton("▶️ Tomosha qilish", url=share_link))
        try:
            if poster_id:
                bot.send_photo(CHANNEL_USERNAME, poster_id, caption=post_caption, parse_mode="Markdown", reply_markup=channel_markup)
            else:
                bot.send_message(CHANNEL_USERNAME, post_caption, parse_mode="Markdown", reply_markup=channel_markup)
            bot.send_message(call.message.chat.id, "✅ **Post kanalga muvaffaqiyatli yuborildi!**")
        except Exception:
            bot.send_message(call.message.chat.id, "❌ Xatolik: Bot kanalda admin ekanligini tekshiring.")

    elif data == "add_anime":
        admin_states[user_id] = {"step": "waiting_for_code"}
        bot.send_message(call.message.chat.id, "🔢 **Yangi anime kodini kiriting:**")

# 6. ADMIN MA'LUMOTLARINI EMBED QILISH (INPUTS)
def handle_admin_inputs(message):
    user_id = message.from_user.id
    state = admin_states[user_id]
    
    # ⚙️ SIZ SO'RAGAN MA'LUMOTLARNI BAZADA TAHRIRLASH BOSQICHLARI
    if state["step"] == "editing_name":
        new_name = message.text.strip()
        code = state["code"]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE animes SET name = ? WHERE code = ?", (new_name, code))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ **Anime nomi muvaffaqiyatli o'zgartirildi!**")
        admin_states.pop(user_id, None)
        show_anime_management_menu(message.chat.id, code)

    elif state["step"] == "editing_poster":
        if message.content_type != 'photo':
            bot.send_message(message.chat.id, "❌ Iltimos, faqat rasm (poster) yuboring!")
            return
        new_poster = message.photo[-1].file_id
        code = state["code"]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE animes SET poster_id = ? WHERE code = ?", (new_poster, code))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ **Anime posteri muvaffaqiyatli o'zgartirildi!**")
        admin_states.pop(user_id, None)
        show_anime_management_menu(message.chat.id, code)

    elif state["step"] == "editing_desc":
        new_desc = message.text.strip()
        code = state["code"]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE animes SET description = ? WHERE code = ?", (new_desc, code))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ **Anime tavsifi muvaffaqiyatli o'zgartirildi!**")
        admin_states.pop(user_id, None)
        show_anime_management_menu(message.chat.id, code)

    elif state["step"] == "editing_code":
        new_code = message.text.strip()
        old_code = state["old_code"]
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE animes SET code = ? WHERE code = ?", (new_code, old_code))
            cursor.execute("UPDATE anime_parts SET anime_code = ? WHERE anime_code = ?", (new_code, old_code))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ **Anime kodi `{old_code}` dan `{new_code}` ga muvaffaqiyatli o'zgardi!**")
            admin_states.pop(user_id, None)
            show_anime_management_menu(message.chat.id, new_code)
        except sqlite3.IntegrityError:
            bot.send_message(message.chat.id, "❌ Bu kod band! Boshqa kod kiriting:")
        conn.close()

    # (Eski kodlar - Kanal va Admin qo'shish jarayonlari)
    elif state["step"] == "waiting_for_channel_id":
        ch_id = message.text.strip()
        admin_states[user_id] = {"step": "waiting_for_channel_name", "ch_id": ch_id}
        bot.send_message(message.chat.id, "Kanal ID qabul qilindi. Tugma uchun **Nom** kiriting:")
        
    elif state["step"] == "waiting_for_channel_name":
        ch_name = message.text.strip()
        ch_id = state["ch_id"]
        admin_states[user_id] = {"step": "waiting_for_channel_url", "ch_id": ch_id, "ch_name": ch_name}
        bot.send_message(message.chat.id, "Endi **Kanal havolasini (Linkini)** yuboring:")

    elif state["step"] == "waiting_for_channel_url":
        ch_url = message.text.strip()
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO channels (channel_id, channel_name, channel_url) VALUES (?, ?, ?)", (state["ch_id"], state["ch_name"], ch_url))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ **Majburiy kanal ulandi!**")
        admin_states.pop(user_id, None)
        show_channels_management_menu(message.chat.id)

    elif state["step"] == "waiting_for_admin_id":
        try:
            new_admin_id = int(message.text.strip())
            admin_states[user_id] = {"step": "waiting_for_admin_user", "new_id": new_admin_id}
            bot.send_message(message.chat.id, "Admin Telegram Usernamening kiriting (@ belgisiz):")
        except ValueError:
            bot.send_message(message.chat.id, "❌ ID raqam bo'lishi shart!")
            
    elif state["step"] == "waiting_for_admin_user":
        username = message.text.strip().replace("@", "")
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO sub_admins (admin_id, username, added_date) VALUES (?, ?, ?)", (state["new_id"], username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ @{username} admin qilindi.")
        admin_states.pop(user_id, None)
        show_admins_management_menu(message.chat.id)

    elif state["step"] == "infinite_adding_parts":
        if message.content_type == 'text' and message.text == "◀️ Orqaga":
            code = state["code"]
            admin_states.pop(user_id, None)
            bot.send_message(message.chat.id, "To'xtatildi.", reply_markup=get_admin_keyboard())
            show_anime_management_menu(message.chat.id, code)
            return
        if message.content_type == 'video':
            code = state["code"]
            conn = sqlite3.connect("anime.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM anime_parts WHERE anime_code = ?", (code,))
            next_part = cursor.fetchone()[0] + 1
            cursor.execute("INSERT INTO anime_parts (anime_code, part_number, file_id) VALUES (?, ?, ?)", (code, next_part, message.video.file_id))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, f"✅ {next_part}-qism qo'shildi. Keyingisini yuboring...")

    elif state["step"] == "waiting_for_code":
        anime_code = message.text.strip()
        admin_states[user_id] = {"step": "waiting_for_name", "code": anime_code}
        bot.send_message(message.chat.id, f"Kod {anime_code}. Nomini kiriting:")
        
    elif state["step"] == "waiting_for_name":
        anime_name = message.text.strip()
        conn = sqlite3.connect("anime.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO animes (code, name, description, poster_id, views_count) VALUES (?, ?, ?, ?, 0)", (state["code"], anime_name, "Tavsif yo'q.", None))
        conn.commit()
        conn.close()
        show_anime_management_menu(message.chat.id, state["code"])
        admin_states.pop(user_id, None)

# ANIME STRUKTURASI MENYUSI (YANGI TAHRIRLASH KNOPKALARI JOYLASHGAN JOY)
def show_anime_management_menu(chat_id, code):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, description, poster_id, views_count FROM animes WHERE code = ?", (code,))
    res = cursor.fetchone()
    conn.close()
    if not res: return
    name, description, poster_id, views_count = res
    share_link = f"https://t.me/{bot.get_me().username}?start={code}"
    
    menu_text = (
        f"📝 **Animeni boshqarish paneli**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 **Kodi:** `{code}`\n"
        f"🎬 **Nomi:** {name}\n"
        f"📥 **Ko'rilganlar:** {views_count} marta\n"
        f"ℹ️ **Tavsif:** {description}\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 Havola: `{share_link}`"
    )
    
    # 🌟 Mazkur menyuda barcha boshqaruv tugmalari mavjud
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📦 Qismlarni boshqarish", callback_data=f"manage_parts_{code}"))
    markup.add(
        types.InlineKeyboardButton("📝 Nomini o'zgartirish", callback_data=f"edit_name_{code}"),
        types.InlineKeyboardButton("🖼 Posterni o'zgartirish", callback_data=f"edit_poster_{code}")
    )
    markup.add(
        types.InlineKeyboardButton("✍️ Tavsifni o'zgartirish", callback_data=f"edit_desc_{code}"),
        types.InlineKeyboardButton("🔢 Kodni o'zgartirish", callback_data=f"edit_code_{code}")
    )
    markup.add(types.InlineKeyboardButton("📢 Kanalga post yuborish", callback_data=f"post_channel_{code}"))
    markup.add(types.InlineKeyboardButton("🗑 Animeni o'chirish", callback_data=f"delete_anime_{code}"))
    markup.add(types.InlineKeyboardButton("◀️ Ro'yxatga qaytish", callback_data="list_animes_0"))
    
    if poster_id:
        bot.send_photo(chat_id, poster_id, caption=menu_text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(chat_id, menu_text, parse_mode="Markdown", reply_markup=markup)

def show_admins_management_menu(chat_id):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id, username FROM sub_admins")
    admins = cursor.fetchall()
    conn.close()
    text = f"👮 **Yordamchi Adminlar ({len(admins)}/15)**\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    for adm in admins:
        text += f"• ID: `{adm[0]}` | @{adm[1]}\n"
        markup.add(types.InlineKeyboardButton(f"🗑 @{adm[1]} ni o'chirish", callback_data=f"del_admin_{adm[0]}"))
    markup.add(types.InlineKeyboardButton("➕ Yangi Admin Qo'shish", callback_data="add_new_admin"))
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

def search_anime_process(chat_id, query):
    conn = sqlite3.connect("anime.db")
    cursor = conn.cursor()
    cursor.execute("SELECT code, name, description, poster_id FROM animes WHERE code = ?", (query,))
    anime = cursor.fetchone()
    
    if not anime:
        cursor.execute("SELECT code, name, description, poster_id FROM animes WHERE name LIKE ?", (f"%{query}%",))
        anime = cursor.fetchone()
        
    if anime:
        code, name, description, poster_id = anime
        cursor.execute("SELECT id, part_number FROM anime_parts WHERE anime_code = ? ORDER BY part_number ASC", (code,))
        parts = cursor.fetchall()
        conn.close()
        
        caption_text = f"🎬 **{name}**\n🔢 Kod: `{code}`\n\n{description}\n\n🍿 Qismlar:"
        markup = types.InlineKeyboardMarkup(row_width=4)
        buttons = [types.InlineKeyboardButton(f"{p[1]}-qism", callback_data=f"get_part_{p[0]}") for p in parts]
        markup.add(*buttons)
        
        if poster_id:
            bot.send_photo(chat_id, poster_id, caption=caption_text, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, caption_text, parse_mode="Markdown", reply_markup=markup)
    else:
        conn.close()
        bot.send_message(chat_id, "❌ **Anime topilmadi!**\n\n💡 _Kodni yoki nomini xatosiz kiritganingizni tekshiring._")

if __name__ == "__main__":
    bot.infinity_polling()
