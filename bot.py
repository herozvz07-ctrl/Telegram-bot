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

# ---------------- Конфигурация ----------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "herozvz"
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# Ссылка на банер для меню /start
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

# Новое меню при команде /start
@bot.message_handler(commands=['start'])
def send_start(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📘 Rucoy Wiki", url="https://t.me/rucoy_wiki"))
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

# Обработчики кнопок меню
@bot.callback_query_handler(func=lambda c: c.data == "calc")
def send_calculator(call):
    try:
        bot.forward_message(call.message.chat.id, "@rucoy_calculyator", 2)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Не удалось переслать файл: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "buy_gold")
def buy_gold_menu(call):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📊 Курсы и топ-трейдеры", callback_data="gold_rates"))
    kb.add(types.InlineKeyboardButton("➕ Ещё", url="https://t.me/Bancus_Rucoy/159"))
    bot.send_message(
        call.message.chat.id,
        ""💰 Покупка Gold\n\n"
"🇷🇺 Россия (RUB)\n"
"> 20₽ = 1kk Gold\n"
"> 100₽ = 5kk\n"
"> 500₽ = 25kk\n"
"> 1000₽ = 50kk\n\n"

"🇺🇦 Украина (UAH)\n"
"> 3₴ = 1kk Gold\n"
"> 15₴ = 5kk\n"
"> 75₴ = 25kk\n"
"> 150₴ = 50kk\n\n"

"🇰🇿 Казахстан (KZT)\n"
"> 10₸ = 1kk Gold\n"
"> 50₸ = 5kk\n"
"> 250₸ = 25kk\n"
"> 500₸ = 50kk\n\n"

"🇧🇾 Беларусь (BYN)\n"
"> 0.70 BYN = 1kk Gold\n"
"> 3.50 BYN = 5kk\n"
"> 17.50 BYN = 25kk\n"
"> 35 BYN = 50kk\n\n"

"🇺🇸 Доллар (USD)\n"
"> $0.25 = 1kk Gold\n"
"> $1.25 = 5kk\n"
"> $6.25 = 25kk\n"
"> $12.50 = 50kk\n\n"",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "gold_rates")
def gold_rates(call):
    bot.send_message(call.message.chat.id, "📊 *Курсы Gold*\n\nЛучшие трейдеры и цены скоро здесь.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "info")
def info_callback(call):
    bot.send_message(
        call.message.chat.id,
        "ℹ️ *Информация*\n\n📌 Команды:\n`/guild` — информация о гильдии\n`/user` — информация об игроке\n`/skam` — список скамеров\n\n👨‍💻 Создатель: @herozvz",
        parse_mode="Markdown"
    )

# -------- GUILD (Твой оригинальный текст) --------
@bot.message_handler(commands=['guild'])
def guild(msg):
    parts = msg.text.split(" ",1)
    if len(parts) < 2:
        bot.reply_to(
            msg,
            "🔴 `УКАЖИ НАЗВАНИЕ ГИЛЬДИИ`\n\nПример:\n`/guild Imperia Of Titans`",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/guild/{quote(name)}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        bot.reply_to(msg, "Гильдия не найдена 📛")
        return

    soup = BeautifulSoup(r.text,"html.parser")
    text = soup.get_text("\n",strip=True)

    created = re.search(r"Founded on ([A-Za-z0-9 ,]+)", text)
    created = created.group(1) if created else "Не указано"

    members = soup.find_all("tr")
    members = sum(1 for r in members if r.find_all("td"))

    desc = extract_description(soup, name)

    reply = (
        f"⚔️ *{name}*\n"
        f"👥 Members: *{members}*\n"
        f"📅 Created: *{created}*\n\n"
        f"```\n{desc}\n```\n"
        f"🔗 {url}"
    )

    bot.reply_to(msg, reply, parse_mode="Markdown", disable_web_page_preview=True)

# -------- USER (Твой оригинальный текст) --------
@bot.message_handler(commands=['user'])
def user(msg):
    parts = msg.text.split(" ",1)
    if len(parts) < 2:
        bot.reply_to(
            msg,
            "🔴 `УКАЖИ НИК ИГРОКА`\n\nПример:\n`/user Hero Of Titan`",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/characters/{quote(name)}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        bot.reply_to(msg, "Игрок не найден 📛")
        return

    soup = BeautifulSoup(r.text,"html.parser")
    table = soup.find("table")
    if not table:
        bot.reply_to(msg, "Нет данных 📛")
        return

    data = {}
    for tr in table.find_all("tr"):
        td = tr.find_all("td")
        if len(td)==2:
            data[td[0].text.strip()] = td[1].text.strip()

    reply = (
        f"👤 {data.get('Name',name)}\n"
        f"📊 Level: {data.get('Level','?')}\n"
        f"⚔️ Guild: {data.get('Guild','None')}\n"
        f"🟢 Last online: {data.get('Last online','?')}\n"
        f"📅 Born: {data.get('Born','?')}\n"
        f"🔗 {url}"
    )

    bot.reply_to(msg, reply, disable_web_page_preview=True)

# -------- SCAM (Исправленный блок для групп) --------
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
            # Очищаем ник и ссылку от символов, которые ломают Markdown
            clean_name = k.replace("_", "\\_").replace("*", "")
            clean_link = v.replace("_", "\\_")
            txt += f"{i}. *{clean_name}*\n{clean_link}\n\n"
            
        # Используем обычный send_message, так как в группах reply_to может глючить при длинных списках
        bot.send_message(msg.chat.id, txt, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        print(f"Error in skam list: {e}")
        # Если Markdown все равно ломается, отправляем чистым текстом
        bot.send_message(msg.chat.id, "❌ Ошибка отображения списка. Попробуйте позже.")

@bot.message_handler(commands=['unskam'])
def remove_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        bot.reply_to(msg, "⛔ Нет прав.")
        return
    try:
        parts = msg.text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(msg, "🔴 `УКАЖИ НИК`", parse_mode="Markdown")
            return
        name = parts[1].strip()
        data = load_scammers()
        if name in data:
            del data[name]
            save_scammers(data)
            bot.reply_to(msg, f"🗑 *{name}* удалён из скам-листа.", parse_mode="Markdown")
        else:
            bot.reply_to(msg, "❌ Этот игрок не найден.")
    except Exception as e:
        print(f"Error in unskam: {e}")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    keep_alive()
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
    print("Bot started")
    bot.infinity_polling()
        
