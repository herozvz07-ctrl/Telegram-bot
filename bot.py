import os
import datetime
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import telebot
from telebot import types
from flask import Flask
from threading import Thread
from pymongo import MongoClient

# ---------------- Конфигурация ----------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "herozvz"
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# --- Настройка подключения к БД ---
try:
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("⚠️ Переменная MONGO_URI не задана!")
        bank_db = None
    else:
        # Подключаемся с таймаутом 15 секунд
        mongo = MongoClient(mongo_uri, serverSelectionTimeoutMS=15000)
        
        # Проверяем доступ (ping)
        mongo.admin.command('ping')
        
        # Выбираем базу 'rucoy' и таблицу 'bank'
        db = mongo["rucoy"]
        bank_db = db["bank"]
        print("✅ ПОДКЛЮЧЕНО: База данных rucoy готова к работе!")
except Exception as e:
    print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
    bank_db = None
    

# Функции для работы с балансом (ИСПРАВЛЕНО)
def get_balance(uid):
    if bank_db is None: 
        return "db_error"  # База вообще не подключена (проблема в ссылке или IP)
    try:
        user_data = bank_db.find_one({"uid": str(uid)})
        return user_data.get("balance", 0) if user_data else 0
    except Exception as e:
        print(f"Ошибка БД: {e}")
        return "query_error" # Ошибка во время поиска (например, таймаут)

def add_balance(uid, amount):
    if bank_db is None: 
        return False
    try:
        # Убеждаемся, что uid - строка, а amount - целое число
        bank_db.update_one(
            {"uid": str(uid)}, 
            {"$inc": {"balance": int(amount)}}, 
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Ошибка в add_balance: {e}")
        return False

def set_balance(uid, amount):
    if bank_db is None: 
        return False
    try:
        # Убеждаемся, что uid - строка, а amount - целое число
        bank_db.update_one(
            {"uid": str(uid)},
            {"$set": {"balance": int(amount)}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Ошибка в set_balance: {e}")
        return False

# Ссылка на баннер для меню /start
START_BANNER = "https://i.ibb.co/5X2W2c8q/e9a3f45d2f734f9126820cdca7b55266.jpg"

# ---------------- SCAM STORAGE ----------------
def load_scammers():
    try:
        if os.path.exists(SCAM_FILE):
            with open(SCAM_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if data:
                    return json.loads(data)
    except:
        pass
    return {}

def save_scammers(data):
    with open(SCAM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ---------------- RENDER KEEP ALIVE ----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run_web_server, daemon=True).start()

# ---------------- PARSING ----------------
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MENU_WORDS = {
    "le navigation","rucoy online","welcome","news","highscores",
    "characters","guilds","sign in","sign in with google","sign in with apple"
}

def remove_adjacent_duplicates(lines):
    out = []
    for l in lines:
        if not out or l != out[-1]:
            out.append(l)
    return out

def remove_repeated_block(lines):
    n = len(lines)
    for k in range(1, n//2 + 1):
        if lines[:k] == lines[k:2*k]:
            return lines[k:]
    return lines

def extract_description(soup, name):
    text = soup.get_text("\n", strip=True)
    idx = text.lower().find(name.lower())
    chunk = ""
    if idx != -1:
        start = idx + len(name)
        m = re.search(r"(Founded on|Members)", text[start:], re.I)
        end = start + m.start() if m else len(text)
        chunk = text[start:end]
    if not chunk:
        return "Нет описания"

    lines = [l.strip() for l in chunk.split("\n") if l.strip()]
    lines = [l for l in lines if not any(m in l.lower() for m in MENU_WORDS)]
    lines = remove_adjacent_duplicates(lines)
    lines = remove_repeated_block(lines)
    return "\n".join(lines) if lines else "Нет описания"

# ---------------- COMMANDS ----------------

@bot.message_handler(commands=['start'])
def send_start(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("➕ Добавить в группу", url="https://t.me/rucoy_online_robot?startgroup=interface"))
    kb.add(
        types.InlineKeyboardButton("💬 Rucoy Chat", url="https://t.me/Bancus_Rucoy/13"),
        types.InlineKeyboardButton("🛒 Rucoy Market", url="https://t.me/Bancus_Rucoy/4")
    )
    kb.add(types.InlineKeyboardButton("🧮 Calculator", callback_data="calc"))
    kb.add(
        types.InlineKeyboardButton("💰 Купить Gold", callback_data="buy_gold"),
        types.InlineKeyboardButton("📤 Продать Gold", url="https://t.me/Bancus_Rucoy/159")
    )
    kb.add(types.InlineKeyboardButton("ℹ️ Информация", callback_data="info"))

    bot.send_photo(
        message.chat.id,
        START_BANNER,
        caption="⚔️ *Rucoy Hub*\n\nВыберите раздел:",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.message_handler(commands=['gold'])
def gold_command(message):
    try:
        text = (
            "💰 *Курс Gold на данный момент*\n\n"
            "🇷🇺 *Россия (RUB)*\n"
            "`20₽ = 1kk Gold`\n\n"
            "🇺🇦 *Украина (UAH)*\n"
            "`11₴ = 1kk Gold`\n\n"
            "🇰🇿 *Казахстан (KZT)*\n"
            "`130₸ = 1kk Gold`\n\n"
            "🇧🇾 *Беларусь (BYN)*\n"
            "`0.8 BYN = 1kk Gold`\n\n"
            "🇺🇸 *USD*\n"
            "`$0.3 = 1kk Gold`\n"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        print("Ошибка в команде /gold:", e)
        bot.reply_to(message, "❌ Не удалось отправить информацию о ценах на Gold")

@bot.callback_query_handler(func=lambda c: c.data == "calc")
def send_calculator(call):
    try:
        bot.forward_message(call.message.chat.id, "@rucoy_calculyator", 2)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Не удалось переслать файл: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "info")
def info_callback(call):
    bot.send_message(
        call.message.chat.id,
        "ℹ️ *Информация*\n\n📌 Команды:\n`/guild` — информация о гильдии\n`/user` — информация об игроке\n`/skam` — список скамеров\n`/bank` — ваш банковский счёт\n\n👨‍💻 Создатель: @herozvz",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda c: c.data == "buy_gold")
def buy_gold_menu(call):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📊 Курсы и топ-трейдеры", callback_data="gold_rates"))
    kb.add(types.InlineKeyboardButton("➕ Ещё", url="https://t.me/Bancus_Rucoy/159"))

    try:
        bot.send_message(
            call.message.chat.id,
            "💰 Курс Gold на данный момент\n\n🇷🇺 Россия (RUB)\n> 20₽ = 1kk Gold\n\n🇺🇦 Украина (UAH)\n> 11₴ = 1kk Gold\n\n🇰🇿 Казахстан (KZT)\n> 130₸ = 1kk Gold\n\n🇧🇾 Беларусь (BYN)\n> 0.8 BYN = 1kk Gold\n\n🇺🇸 Доллар (USD)\n> $0.3 = 1kk Gold",
            parse_mode="Markdown",
            reply_markup=kb
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error in buy_gold: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "gold_rates")
def gold_rates(call):
    bot.send_message(
        call.message.chat.id,
        "📊 *Курсы Gold*\n\nЛучшие трейдеры и цены скоро здесь.",
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id)

# -------- BANK SYSTEM (ИСПРАВЛЕНО) --------

# -------- BANK SYSTEM (ПОЛНОЕ ОБНОВЛЕНИЕ) --------

last_transfer_time = {}  # Для антиспама
transfer_process = {}    # Для пошагового ввода суммы

def get_player_name(uid):
    """Пытается достать имя игрока из базы"""
    if not bank_db: return "Unknown"
    user_data = bank_db.find_one({"uid": str(uid)})
    if user_data and "name" in user_data:
        return user_data["name"]
    return f"Player {uid}"

@bot.message_handler(commands=['bank'])
def bank_profile(msg):
    uid = str(msg.from_user.id)
    name = msg.from_user.first_name or "Player"
    
    # ИСПРАВЛЕНО: Проверка на None вместо прямого условия
    if bank_db is not None:
        try:
            bank_db.update_one({"uid": uid}, {"$set": {"name": name}}, upsert=True)
        except Exception as e:
            print(f"Ошибка сохранения имени: {e}")
    
    balance = get_balance(uid)
    
    # ИСПРАВЛЕНО: Обработка ошибок баланса
    if balance == "db_error":
        return bot.reply_to(msg, "❌ Ошибка: База данных не подключена.")
    if balance == "query_error":
        return bot.reply_to(msg, "❌ Ошибка запроса к балансу.")

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📤 Вывод", callback_data="bank_withdraw"),
        types.InlineKeyboardButton("➕ Пополнить", callback_data="bank_deposit")
    )
    kb.add(types.InlineKeyboardButton("💸 Отправить Gold", callback_data="start_gift_btn"))
    
    text = (
        "🏦 *Rucoy Bank*\n\n"
        f"👤 Игрок: *{name}*\n"
        f"🆔 ID: `{uid}`\n"
        f"💰 Баланс: *{balance:,}* gold"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=kb)
    

# --- ЛОГИКА ПЕРЕВОДА (GIFT) ---

@bot.message_handler(commands=['gift'])
def gift_init(msg):
    uid = str(msg.from_user.id)
    
    # Антиспам 2 минуты (120 секунд)
    now = datetime.datetime.now()
    if uid in last_transfer_time:
        diff = (now - last_transfer_time[uid]).total_seconds()
        if diff < 120:
            return bot.reply_to(msg, f"⏳ Анти-спам! Подождите {int(120 - diff)} сек.")

    parts = msg.text.split()
    target_id = None

    if msg.reply_to_message:
        target_id = str(msg.reply_to_message.from_user.id)
    elif len(parts) > 1:
        target_id = parts[1]
    else:
        return bot.reply_to(msg, "📝 Чтобы перевести: `/gift ID` или ответь на сообщение.", parse_mode="Markdown")

    if target_id == uid:
        return bot.reply_to(msg, "❌ Нельзя переводить самому себе.")

    target_name = get_player_name(target_id)
    transfer_process[uid] = {'target_id': target_id, 'target_name': target_name}
    
    sent = bot.reply_to(msg, f"💰 Перевод для: *{target_name}*\n🆔 ID: `{target_id}`\n\n*Введите сумму перевода (минимум 25,000):*", parse_mode="Markdown")
    bot.register_next_step_handler(sent, gift_get_amount)

def gift_get_amount(msg):
    uid = str(msg.from_user.id)
    if uid not in transfer_process: return

    try:
        # Убираем пробелы и запятые, если юзер их ввел
        amount_str = msg.text.replace(" ", "").replace(",", "")
        amount = int(amount_str)
        
        if amount < 25000:
            return bot.reply_to(msg, "❌ Минимальная сумма перевода: 25,000 gold.")
        
        balance = get_balance(uid)
        if balance < amount:
            return bot.reply_to(msg, f"❌ Недостаточно средств. Ваш баланс: {balance:,}")

        data = transfer_process[uid]
        data['amount'] = amount

        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"gconfirm_yes_{uid}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data=f"gconfirm_no_{uid}")
        )

        bot.send_message(msg.chat.id, f"❓ Вы уверены, что хотите отправить *{amount:,}* gold игроку *{data['target_name']}*?", 
                         parse_mode="Markdown", reply_markup=kb)
    except ValueError:
        bot.reply_to(msg, "❌ Ошибка! Введите сумму только цифрами.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("gconfirm_"))
def gift_final_stage(call):
    _, action, uid = call.data.split("_")
    if str(call.from_user.id) != uid:
        return bot.answer_callback_query(call.id, "❌ Это не ваш перевод!", show_alert=True)

    if uid not in transfer_process:
        return bot.edit_message_text("❌ Время ожидания истекло.", call.message.chat.id, call.message.message_id)

    data = transfer_process.pop(uid)
    if action == "no":
        return bot.edit_message_text("❌ Перевод отменен.", call.message.chat.id, call.message.message_id)

    amount = data['amount']
    target = data['target_id']
    
    if add_balance(uid, -amount) and add_balance(target, amount):
        last_transfer_time[uid] = datetime.datetime.now()
        
        # Формируем данные для чека
        now = datetime.datetime.utcnow()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d%m%Y")
        # Формат: Время!Получатель!Отправитель!Дата!Сумма
        check_raw = f"{time_str}!{target}!{uid}!{date_str}!{amount}"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📄 Посмотреть чек", callback_data=f"vcheck_{check_raw}"))
        
        bot.edit_message_text(f"✅ Перевод доставлен успешно!\nСохраните это сообщение и чек.", 
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        
        try:
            bot.send_message(target, f"💰 Вам пришел перевод: *{amount:,}* gold!\nПроверьте `/bank`.", parse_mode="Markdown")
        except: pass
    else:
        bot.edit_message_text("❌ Ошибка транзакции. Свяжитесь с админом.", call.message.chat.id, call.message.message_id)

# --- ВСплывающее ОКНО ЧЕКА ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("vcheck_"))
def show_popup_check(call):
    raw = call.data.replace("vcheck_", "")
    p = raw.split("!") # 0:время, 1:target, 2:sender, 3:дата, 4:сумма
    
    # Только отправитель или админ herozvz может смотреть чек
    if str(call.from_user.id) != p[2] and call.from_user.username != ADMIN_USERNAME:
        return bot.answer_callback_query(call.id, "❌ Доступ к чеку только у отправителя!", show_alert=True)

    # Формируем текст как вы просили
    # перевод✅: 16:30!676767!7676767!6012026!800000
    check_text = f"перевод✅: {p[0]}!{p[1]}!{p[2]}!{p[3]}!{p[4]}"
    
    bot.answer_callback_query(call.id, text=check_text, show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "start_gift_btn")
def gift_btn_handler(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Чтобы отправить золото, используй:\n`/gift ID` или ответь на сообщение игрока.", parse_mode="Markdown")

# --- КОНЕЦ БЛОКА BANK SYSTEM ---

# -------- GUILD --------
@bot.message_handler(commands=['guild'])
def guild(msg):
    try:
        parts = msg.text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(
                msg,
                "🔴 `УКАЖИ НАЗВАНИЕ ГИЛЬДИИ`\n\nПример:\n`/guild Imperia Of Titans`",
                parse_mode="Markdown"
            )
            return

        name = parts[1].strip()
        url = f"https://www.rucoyonline.com/guild/{quote(name)}"

        r = requests.get(url, headers=HEADERS, timeout=5)
        
        if r.status_code != 200:
            bot.reply_to(msg, "Гильдия не найдена 📛")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        text_all = soup.get_text("\n", strip=True)

        created = re.search(r"Founded on ([A-Za-z0-9 ,]+)", text_all)
        created = created.group(1) if created else "Не указано"

        members_rows = soup.find_all("tr")
        members_count = sum(1 for r in members_rows if r.find_all("td"))

        desc = extract_description(soup, name)
        desc_clean = desc.replace("```", "`\u200b``")

        reply = (
            f"⚔️ *{name}*\n"
            f"👥 Members: *{members_count}*\n"
            f"📅 Created: *{created}*\n\n"
            f"```\n{desc_clean}\n```\n"
            f"🔗 {url}"
        )

        bot.reply_to(msg, reply, parse_mode="Markdown", disable_web_page_preview=True)

    except requests.exceptions.Timeout:
        bot.reply_to(msg, "⚠️ Ошибка: Сайт Rucoy не отвечает (Таймаут).")
    except Exception as e:
        print(f"Ошибка в команде guild: {e}")
        bot.reply_to(msg, "❌ Произошла ошибка при поиске гильдии.")


# -------- USER --------
@bot.message_handler(commands=['user'])
def user(msg):
    parts = msg.text.split(" ", 1)
    if len(parts) < 2:
        bot.reply_to(
            msg,
            "🔴 `УКАЖИ НИК ИГРОКА`\n\nПример:\n`/user Hero Of Titan`",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/characters/{quote(name)}"

    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code != 200:
            bot.reply_to(msg, "Игрок не найден 📛")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            bot.reply_to(msg, "Нет данных 📛")
            return

        data = {}
        for tr in table.find_all("tr"):
            td = tr.find_all("td")
            if len(td) == 2:
                data[td[0].text.strip()] = td[1].text.strip()

        reply = (
            f"👤 {data.get('Name', name)}\n"
            f"📊 Level: {data.get('Level', '?')}\n"
            f"⚔️ Guild: {data.get('Guild', 'None')}\n"
            f"🟢 Last online: {data.get('Last online', '?')}\n"
            f"📅 Born: {data.get('Born', '?')}\n"
            f"🔗 {url}"
        )

        bot.reply_to(msg, reply, disable_web_page_preview=True)
    except Exception as e:
        print(f"Ошибка в /user: {e}")
        bot.reply_to(msg, "❌ Ошибка при поиске игрока")


# -------- SCAM --------
@bot.message_handler(commands=['skamer'])
def add_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        return
    try:
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(msg, "Используй: `/skamer Nick link`", parse_mode="Markdown")
            return
        data = load_scammers()
        data[parts[1]] = parts[2]
        save_scammers(data)
        bot.reply_to(msg, "✅ Добавлено")
    except Exception as e:
        print(f"Error in skamer: {e}")


@bot.message_handler(commands=['skam'])
def list_scam(msg):
    try:
        data = load_scammers()
        if not data:
            bot.reply_to(msg, "🛡️ Список пуст")
            return
        
        txt = "🚫 *SCAM LIST*\n\n"
        for i, (k, v) in enumerate(data.items(), 1):
            clean_name = k.replace("_", "\\_").replace("*", "")
            txt += f"{i}. {clean_name}: [Ссылка]({v})\n"
            
        bot.reply_to(msg, txt, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        print(f"Ошибка в /skam: {e}")
        bot.reply_to(msg, "❌ Не удалось загрузить список")

# ----------------HeroDolbayop не трогай тут ничего----------------

if __name__ == "__main__":
    # 1. Запускаем веб-сервер для Render (чтобы не засыпал)
    keep_alive()
    
    # 2. Запускаем самого бота
    print("✅ Бот запущен и готов к работе!")
    bot.polling(none_stop=True)
    
      
