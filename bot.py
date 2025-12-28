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
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения.")

bot = telebot.TeleBot(TOKEN)

# ---------------- Баннеры ----------------
BANNERS = {
    "start": "https://i.ibb.co/5X2W2c8q/e9a3f45d2f734f9126820cdca7b55266.jpg",
    "guild": "https://allwebs.ru/images/2025/12/27/e8447e2372bd8244de34f836d970efb8.jpg",
    "user": "https://allwebs.ru/images/2025/12/27/e8447e2372bd8244de34f836d970efb8.jpg",
    "skam": "https://allwebs.ru/images/2025/12/27/e8447e2372bd8244de34f836d970efb8.jpg",
    "default": "https://allwebs.ru/images/2025/12/27/e8447e2372bd8244de34f836d970efb8.jpg"
}

def send_with_banner(chat_id, text, banner_type="default", **kwargs):
    url = BANNERS.get(banner_type, BANNERS["default"])
    try:
        bot.send_photo(chat_id, url, caption=text, **kwargs)
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")
        bot.send_message(chat_id, text, **kwargs)

# ---------------- SCAM STORAGE ----------------
def load_scammers():
    try:
        if os.path.exists(SCAM_FILE):
            with open(SCAM_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_scammers(data):
    with open(SCAM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ---------------- KEEP ALIVE ----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run_web_server, daemon=True).start()

# ---------------- PARSING UTILS ----------------
HEADERS = {"User-Agent": "Mozilla/5.0"}
MENU_WORDS = {"navigation","rucoy online","welcome","news","highscores","characters","guilds","sign in"}

def remove_adjacent_duplicates(lines):
    out = []
    for l in lines:
        if not out or l != out[-1]:
            out.append(l)
    return out

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
    return "\n".join(lines) if lines else "Нет описания"

# ---------------- COMMANDS ----------------

@bot.message_handler(commands=['start'])
def send_start(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📘 Rucoy Wiki", url="https://t.me/ttinperia"))
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

    send_with_banner(
        message.chat.id,
        "⚔️ *Rucoy Hub*\n\nВыберите раздел:",
        banner_type="start",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "calc")
def send_calculator(call):
    try:
        with open("calculator.pdf", "rb") as doc:
            bot.send_document(call.message.chat.id, doc)
    except FileNotFoundError:
        bot.answer_callback_query(call.id, "❌ Файл calculator.pdf не найден.")

@bot.callback_query_handler(func=lambda c: c.data == "buy_gold")
def buy_gold_menu(call):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📊 Курсы и топ-трейдеры", callback_data="gold_rates"))
    
    bot.edit_message_caption(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        caption="💰 *Покупка Gold*\n\nСредний курс:\n16₽ ≈ 1кк",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "gold_rates")
def gold_rates(call):
    bot.answer_callback_query(call.id, "Информация обновляется...")
    bot.send_message(call.message.chat.id, "📊 *Курсы Gold*\n\nЛучшие трейдеры и цены скоро здесь.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "info")
def info(call):
    bot.send_message(
        call.message.chat.id,
        "ℹ️ *Информация*\n\n📌 Команды:\n`/guild` — о гильдии\n`/user` — об игроке\n`/skam` — список скамеров\n\nсоздатель: @herozvz",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['guild'])
def guild(msg):
    parts = msg.text.split(" ", 1)
    if len(parts) < 2:
        send_with_banner(msg.chat.id, "🔴 Укажите название гильдии\n`/guild Imperia Of Titans`", "guild", parse_mode="Markdown")
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/guild/{quote(name)}"
    r = requests.get(url, headers=HEADERS)
    
    if r.status_code != 200:
        bot.reply_to(msg, "Гильдия не найдена 📛")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    created = re.search(r"Founded on ([A-Za-z0-9 ,]+)", text)
    created = created.group(1) if created else "Не указано"
    
    members = sum(1 for tr in soup.find_all("tr") if tr.find_all("td"))
    desc = extract_description(soup, name)
    
    reply = f"⚔️ *{name}*\n👥 Members: *{members}*\n📅 Created: *{created}*\n\n`{desc}`\n\n🔗 {url}"
    send_with_banner(msg.chat.id, reply, "guild", parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['user'])
def user(msg):
    parts = msg.text.split(" ", 1)
    if len(parts) < 2:
        send_with_banner(msg.chat.id, "🔴 Укажите ник\n`/user Hero Of Titan`", "user", parse_mode="Markdown")
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/characters/{quote(name)}"
    r = requests.get(url, headers=HEADERS)
    
    if r.status_code != 200:
        bot.reply_to(msg, "Игрок не найден 📛")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        bot.reply_to(msg, "Данные скрыты или отсутствуют.")
        return

    data = {tr.find_all("td")[0].text.strip(): tr.find_all("td")[1].text.strip() for tr in table.find_all("tr") if len(tr.find_all("td")) == 2}
    
    reply = (
        f"👤 {data.get('Name', name)}\n"
        f"📊 Level: {data.get('Level', '?')}\n"
        f"⚔️ Guild: {data.get('Guild', 'None')}\n"
        f"🟢 Online: {data.get('Last online', '?')}\n"
        f"🔗 {url}"
    )
    send_with_banner(msg.chat.id, reply, "user")

# ---------------- SCAM SYSTEM ----------------

@bot.message_handler(commands=['skamer'])
def add_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME: return
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(msg, "Используй: `/skamer Nick Link`", parse_mode="Markdown")
        return
    data = load_scammers()
    data[parts[1]] = parts[2]
    save_scammers(data)
    bot.send_message(msg.chat.id, "✅ Добавлено")

@bot.message_handler(commands=['unskam'])
def remove_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME: return
    name = msg.text.split(" ", 1)[-1].strip()
    data = load_scammers()
    if name in data:
        del data[name]
        save_scammers(data)
        bot.send_message(msg.chat.id, f"🗑 {name} удален.")
    else:
        bot.send_message(msg.chat.id, "Ник не найден.")

@bot.message_handler(commands=['skam'])
def list_scam(msg):
    data = load_scammers()
    if not data:
        send_with_banner(msg.chat.id, "🛡️ Список чист", "skam")
        return
    
    txt = "🚫 *SCAM LIST*\n\n"
    for i, (k, v) in enumerate(data.items(), 1):
        txt += f"{i}. *{k}*\n🔗 {v}\n\n"
    
    send_with_banner(msg.chat.id, txt, "skam", parse_mode="Markdown", disable_web_page_preview=True)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.infinity_polling()
