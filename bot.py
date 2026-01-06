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
from datetime import datetime, timedelta

transfer_states = {}   # uid -> {target, amount, msg_id}
last_transfer = {}     # антиспам

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
    # Новая кнопка Банк
    kb.add(types.InlineKeyboardButton("🏦 Мой Банк", callback_data="open_bank"))
    
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

# Обработчик для кнопки Банк из меню старт
@bot.callback_query_handler(func=lambda c: c.data == "open_bank")
def open_bank_callback(call):
    bot.answer_callback_query(call.id)
    bank_profile(call.message) # Вызываем функцию профиля

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

# -------- ИСПРАВЛЕННАЯ СИСТЕМА БАНКА И ПЕРЕВОДОВ --------

user_states = {} # Храним данные о переводе: {user_id: {'target_id': 123, 'step': 'amount'}}

@bot.message_handler(commands=['bank'])
def bank_profile(msg):
    uid = str(msg.from_user.id)
    # Если это колбэк (нажатие кнопки), достаем ник правильно
    name = msg.from_user.first_name if msg.from_user.first_name else "Player"
    
    # Проверка на бан
    user_data = bank_db.find_one({"uid": uid}) if bank_db is not None else None
    if user_data and user_data.get("banned", False):
        return bot.reply_to(msg, "🚫 Вы заблокированы в банковской системе.")

    if bank_db is not None:
        bank_db.update_one({"uid": uid}, {"$set": {"name": name}}, upsert=True)
    
    balance = get_balance(uid)
    if balance in ["db_error", "query_error"]:
        return bot.reply_to(msg, "❌ Ошибка базы данных.")

    kb = types.InlineKeyboardMarkup(row_width=2)
    url_deposit = f"https://t.me/herozvz?text=Я%20хочу%20пополнить%20счёт%20(ID:%20{uid})"
    url_withdraw = f"https://t.me/herozvz?text=Я%20хочу%20вывести%20gold%20(ID:%20{uid})"
    
    kb.add(
        types.InlineKeyboardButton("➕ Пополнить", url=url_deposit),
        types.InlineKeyboardButton("📤 Вывод", url=url_withdraw)
    )
    kb.add(types.InlineKeyboardButton("💸 Отправить Gold", callback_data="start_gift_btn"))
    
    text = (
        "🏦 *Rucoy Bank*\n\n"
        f"👤 Игрок: *{name}*\n"
        f"🆔 ID: `{uid}`\n"
        f"💰 Баланс: *{balance:,}* gold"
    )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(commands=['gift'])
def gift_init(msg):
    uid = str(msg.from_user.id)
    
    # Антиспам (2 минуты)
    now = datetime.datetime.now()
    if uid in last_transfer_time:
        diff = (now - last_transfer_time[uid]).total_seconds()
        if diff < 120:
            return bot.reply_to(msg, f"⏳ Подождите {int(120 - diff)} сек.")

    parts = msg.text.split()
    target_id = None

    if msg.reply_to_message:
        target_id = str(msg.reply_to_message.from_user.id)
    elif len(parts) > 1:
        target_id = parts[1]
    else:
        return bot.reply_to(msg, "📝 Чтобы перевести:\n`/gift ID` или ответь на сообщение игрока этой командой.", parse_mode="Markdown")

    if target_id == uid:
        return bot.reply_to(msg, "❌ Нельзя переводить самому себе.")

    target_name = get_player_name(target_id)
    # Запоминаем, что этот юзер начал перевод
    user_states[uid] = {'target_id': target_id, 'target_name': target_name, 'action': 'waiting_gift_amount'}
    
    bot.reply_to(msg, f"💰 Перевод для: *{target_name}*\n🆔 ID: `{target_id}`\n\n*Введите сумму (минимум 25,000):*", parse_mode="Markdown")

# Общий обработчик текста для ввода сумм (чтобы не зависало)
@bot.message_handler(func=lambda msg: str(msg.from_user.id) in user_states)
def handle_text_states(msg):
    uid = str(msg.from_user.id)
    state = user_states[uid]

    if state.get('action') == 'waiting_gift_amount':
        try:
            amount_str = msg.text.replace(" ", "").replace(",", "")
            amount = int(amount_str)
            
            if amount < 25000:
                return bot.reply_to(msg, "❌ Минимальная сумма: 25,000.")
            
            balance = get_balance(uid)
            if balance < amount:
                return bot.reply_to(msg, f"❌ Недостаточно средств. Ваш баланс: {balance:,}")

            state['amount'] = amount
            state['action'] = 'confirm' # Меняем статус на ожидание подтверждения

            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"gconfirm_yes_{uid}"),
                types.InlineKeyboardButton("❌ Отмена", callback_data=f"gconfirm_no_{uid}")
            )
            bot.send_message(msg.chat.id, f"❓ Отправить *{amount:,}* gold игроку *{state['target_name']}*?", 
                             parse_mode="Markdown", reply_markup=kb)
        except ValueError:
            bot.reply_to(msg, "❌ Введите сумму цифрами.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("gconfirm_"))
def gift_final_stage(call):
    _, action, owner_id = call.data.split("_")
    
    # Только тот, кто начал перевод, может нажать кнопку
    if str(call.from_user.id) != owner_id:
        return bot.answer_callback_query(call.id, "❌ Это не ваш перевод!", show_alert=True)

    if owner_id not in user_states:
        return bot.edit_message_text("❌ Сессия истекла.", call.message.chat.id, call.message.message_id)

    data = user_states.pop(owner_id) # Удаляем состояние сразу после нажатия
    
    if action == "no":
        return bot.edit_message_text("❌ Перевод отменен.", call.message.chat.id, call.message.message_id)

    amount = data['amount']
    target = data['target_id']
    
    if add_balance(owner_id, -amount) and add_balance(target, amount):
        last_transfer_time[owner_id] = datetime.datetime.now()
        
        now = datetime.datetime.utcnow()
        check_raw = f"{now.strftime('%H:%M')}!{target}!{owner_id}!{now.strftime('%d%m%Y')}!{amount}"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📄 Посмотреть чек", callback_data=f"vcheck_{check_raw}"))
        
        bot.edit_message_text(f"✅ Перевод {amount:,} gold успешно выполнен!", 
                              call.message.chat.id, call.message.message_id, reply_markup=kb)
        try:
            bot.send_message(target, f"💰 Вам пришел перевод: *{amount:,}* gold!\nПроверьте `/bank`.", parse_mode="Markdown")
        except: pass
    else:
        bot.send_message(call.message.chat.id, "❌ Ошибка транзакции.")

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

# -------- ADMIN PANEL SYSTEM --------

# Временное хранилище для шагов админа
admin_states = {} 

@bot.message_handler(commands=['admin'])
def admin_panel(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        return

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Добавить Gold", callback_data="adm_add"),
        types.InlineKeyboardButton("➖ Снять Gold", callback_data="adm_sub")
    )
    kb.add(
        types.InlineKeyboardButton("⚙️ Установить баланс", callback_data="adm_set"),
        types.InlineKeyboardButton("🚫 Бан/Разбан", callback_data="adm_ban")
    )
    
    bot.send_message(msg.chat.id, "🛠 **Панель администратора**\nВыберите действие:", parse_mode="Markdown", reply_markup=kb)

# Обработка нажатий в админ-панели
@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def admin_callback(call):
    if call.from_user.username != ADMIN_USERNAME:
        return bot.answer_callback_query(call.id, "У вас нет прав!")

    action = call.data.split("_")[1]
    admin_states[call.from_user.id] = {"action": action}

    if action == "ban":
        sent = bot.edit_message_text("🚫 Введите **ID** игрока для бана/разбана:", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    else:
        sent = bot.edit_message_text("🆔 Введите **ID** игрока:", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    bot.register_next_step_handler(sent, admin_get_id)

def admin_get_id(msg):
    uid = msg.from_user.id
    if uid not in admin_states: return

    target_id = msg.text.strip()
    admin_states[uid]["target_id"] = target_id

    action = admin_states[uid]["action"]
    
    if action == "ban":
        if bank_db is None: return bot.send_message(msg.chat.id, "❌ База недоступна")
        
        user_data = bank_db.find_one({"uid": target_id})
        is_banned = user_data.get("banned", False) if user_data else False
        
        new_status = not is_banned
        bank_db.update_one({"uid": target_id}, {"$set": {"banned": new_status}}, upsert=True)
        
        status_text = "🚫 ЗАБАНЕН" if new_status else "✅ РАЗБАНЕН"
        bot.send_message(msg.chat.id, f"Игрок `{target_id}` теперь {status_text}", parse_mode="Markdown")
        del admin_states[uid]
    else:
        sent = bot.send_message(msg.chat.id, "💰 Теперь введите **сумму**:")
        bot.register_next_step_handler(sent, admin_get_amount)

def admin_get_amount(msg):
    uid = msg.from_user.id
    if uid not in admin_states: return

    try:
        amount = int(msg.text.replace(" ", "").replace(",", ""))
        target_id = admin_states[uid]["target_id"]
        action = admin_states[uid]["action"]

        if action == "add":
            add_balance(target_id, amount)
            res_text = f"✅ Добавлено {amount:,} gold игроку `{target_id}`"
        elif action == "sub":
            add_balance(target_id, -amount)
            res_text = f"✅ Снято {amount:,} gold у игрока `{target_id}`"
        elif action == "set":
            set_balance(target_id, amount)
            res_text = f"✅ Баланс игрока `{target_id}` установлен на {amount:,}"

        bot.send_message(msg.chat.id, res_text, parse_mode="Markdown")
        
        try:
            current_bal = get_balance(target_id)
            bot.send_message(target_id, f"🔔 Ваш баланс изменен администратором.\nТекущий счет: *{current_bal:,}*", parse_mode="Markdown")
        except: pass

    except:
        bot.send_message(msg.chat.id, "❌ Ошибка! Введите число.")
    
    if uid in admin_states: del admin_states[uid]

# --- ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ КНОПОК ---

@bot.callback_query_handler(func=lambda c: True)
def global_callbacks(call):
    if call.data == "open_bank":
        bot.answer_callback_query(call.id)
        bank_profile(call.message)
    elif call.data == "start_gift_btn":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "Чтобы отправить золото, используй:\n`/gift ID` или ответь на сообщение игрока.", parse_mode="Markdown")

# -------- ЗАПУСК --------

if __name__ == "__main__":
    keep_alive()
    print("✅ Бот запускается...")
    # Обязательно удаляем вебхук перед поллингом
    bot.remove_webhook()
    # Запуск бота
    bot.polling(none_stop=True, interval=0, timeout=20)
        

