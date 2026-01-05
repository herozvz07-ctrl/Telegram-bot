import os
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

# -------- ВАШ БЛОК BANK SYSTEM (ИСПРАВЛЕННЫЙ) --------

pending_gifts = {}

@bot.message_handler(commands=['bank'])
def bank_profile(msg):
    uid = str(msg.from_user.id)
    balance = get_balance(uid)

    if balance == "db_error":
        bot.reply_to(msg, "❌ Ошибка: БД не подключена")
        return

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📤 Вывод", callback_data="bank_withdraw"),
        types.InlineKeyboardButton("➕ Пополнить", callback_data="bank_deposit")
    )
    kb.add(types.InlineKeyboardButton("💸 Отправить", callback_data="bank_send"))

    text = (
        "🏦 *Ваш Bank*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"💰 Счёт: *{balance}*"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=kb)

# Обработка кнопок вывода и депозита
@bot.callback_query_handler(func=lambda c: c.data in ["bank_withdraw", "bank_deposit", "bank_send"])
def bank_actions(call):
    bot.answer_callback_query(call.id)
    if call.data == "bank_withdraw":
        bot.send_message(call.message.chat.id, "📤 Для вывода напиши @herozvz")
    elif call.data == "bank_deposit":
        bot.send_message(call.message.chat.id, "➕ Для пополнения напиши @herozvz")
    elif call.data == "bank_send":
        bot.send_message(call.message.chat.id, "💸 Чтобы отправить:\n`/gift ID сумма`", parse_mode="Markdown")

@bot.message_handler(commands=['gift'])
def gift(msg):
    if bank_db is None: return bot.reply_to(msg, "❌ Банк недоступен")
    
    sender = str(msg.from_user.id)
    sender_balance = get_balance(sender)

    if isinstance(sender_balance, str) or sender_balance <= 0:
        bot.reply_to(msg, "❌ У вас нет средств")
        return

    try:
        if msg.reply_to_message:
            parts = msg.text.split()
            if len(parts) != 2: return bot.reply_to(msg, "Используй: /gift сумма")
            target = str(msg.reply_to_message.from_user.id)
            amount = int(parts[1])
        else:
            parts = msg.text.split()
            if len(parts) != 3: return bot.reply_to(msg, "Используй: /gift ID сумма")
            target = str(parts[1])
            amount = int(parts[2])

        if amount <= 0: return bot.reply_to(msg, "❌ Сумма должна быть > 0")
        if sender_balance < amount: return bot.reply_to(msg, "❌ Недостаточно средств")
        if sender == target: return bot.reply_to(msg, "❌ Нельзя отправить себе")

        pending_gifts[sender] = (target, amount)
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton("✅ Да", callback_data=f"gift_yes_{sender}"),
            types.InlineKeyboardButton("❌ Нет", callback_data=f"gift_no_{sender}")
        )
        bot.send_message(msg.chat.id, f"Вы уверены, что хотите отправить *{amount}*?", parse_mode="Markdown", reply_markup=kb)
    except:
        bot.reply_to(msg, "❌ Ошибка в команде")

@bot.callback_query_handler(func=lambda c: c.data.startswith("gift_"))
def gift_confirm(call):
    try:
        # Исправленный разбор данных кнопки
        parts = call.data.split("_")
        action = parts[1]
        uid = parts[2]

        if str(call.from_user.id) != uid:
            bot.answer_callback_query(call.id, "❌ Это не ваша кнопка", show_alert=True)
            return

        if uid not in pending_gifts:
            bot.answer_callback_query(call.id, "⏳ Время вышло")
            return

        target, amount = pending_gifts.pop(uid)

        if action == "no":
            bot.edit_message_text("❌ Отменено", call.message.chat.id, call.message.message_id)
            return

        # Финальная проверка баланса перед отправкой
        if get_balance(uid) < amount:
            bot.edit_message_text("❌ Баланс изменился", call.message.chat.id, call.message.message_id)
            return

        if add_balance(uid, -amount) and add_balance(target, amount):
            bot.edit_message_text(f"✅ Успешно отправлено {amount}!", call.message.chat.id, call.message.message_id)
            try: bot.send_message(target, f"💰 Вам переведено *{amount}*", parse_mode="Markdown")
            except: pass
        else:
            bot.edit_message_text("❌ Ошибка базы", call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"Ошибка gift_confirm: {e}")
    
@bot.message_handler(commands=['addbalance', 'setbalance'])
def admin_manage_bank(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        return
    
    parts = msg.text.split()
    if len(parts) < 3:
        return bot.reply_to(msg, "Используй: `/addbalance ID сумма` или `/setbalance ID сумма`")
    
    uid, amount = parts[1], int(parts[2])
    
    if msg.text.startswith('/addbalance'):
        res = add_balance(uid, amount)
        action = "изменен"
    else:
        res = set_balance(uid, amount)
        action = "установлен"
        
    if res:
        bot.reply_to(msg, f"✅ Баланс игрока `{uid}` {action}. Текущий: *{get_balance(uid)}*", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "❌ Ошибка базы данных")

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
    
      
