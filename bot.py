import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import telebot
from flask import Flask
from threading import Thread

# ---------------- Конфигурация ----------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "herozvz"
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ---------------- Баннеры ----------------
BANNERS = {
    "start": "https://raw.githubusercontent.com/USERNAME/REPO/main/start.png",
    "guild": "https://raw.githubusercontent.com/USERNAME/REPO/main/guild.png",
    "user": "https://raw.githubusercontent.com/USERNAME/REPO/main/user.png",
    "skam": "https://raw.githubusercontent.com/USERNAME/REPO/main/skam.png",
    "default": "https://raw.githubusercontent.com/USERNAME/REPO/main/default.png"
}

def send_with_banner(chat_id, text, banner_type="default", **kwargs):
    url = BANNERS.get(banner_type, BANNERS["default"])
    try:
        bot.send_photo(chat_id, url, caption=text, **kwargs)
    except:
        bot.send_message(chat_id, text, **kwargs)

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
def start(msg):
    send_with_banner(
        msg.chat.id,
        "Привет! Я бот Rucoy.\n\nКоманды:\n/user [ник]\n/guild [название]\n/skam - список скамеров",
        banner_type="start"
    )

# -------- GUILD --------
@bot.message_handler(commands=['guild'])
def guild(msg):
    parts = msg.text.split(" ",1)
    if len(parts) < 2:
        send_with_banner(
            msg.chat.id,
            "🔴 `УКАЖИ НАЗВАНИЕ ГИЛЬДИИ`\n\nПример:\n`/guild Imperia Of Titans`",
            banner_type="guild",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/guild/{quote(name)}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        send_with_banner(msg.chat.id, "Гильдия не найдена 📛", banner_type="guild")
        return

    soup = BeautifulSoup(r.text,"html.parser")
    text = soup.get_text("\n",strip=True)

    created = re.search(r"Founded on ([A-Za-z0-9 ,]+)", text)
    created = created.group(1) if created else "Не указано"

    table = soup.find_all("tr")
    members = sum(1 for r in table if r.find_all("td"))

    desc = extract_description(soup, name)
    desc_clean = desc.replace("```", "`\u200b``")
    
    reply = (
        f"⚔️ *{name}*\n"
        f"👥 Members: *{members}*\n"
        f"📅 Created: *{created}*\n\n"
        f"```\n{desc_clean}\n```\n"
        f"🔗 {url}"
    )

    send_with_banner(
        msg.chat.id,
        reply,
        banner_type="guild",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# -------- USER --------
@bot.message_handler(commands=['user'])
def user(msg):
    parts = msg.text.split(" ",1)
    if len(parts) < 2:
        send_with_banner(
            msg.chat.id,
            "🔴 `УКАЖИ НИК ИГРОКА`\n\nПример:\n`/user Hero Of Titan`",
            banner_type="user",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/characters/{quote(name)}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        send_with_banner(msg.chat.id, "Игрок не найден 📛", banner_type="user")
        return

    soup = BeautifulSoup(r.text,"html.parser")
    table = soup.find("table")
    if not table:
        send_with_banner(msg.chat.id, "Нет данных 📛", banner_type="user")
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

    send_with_banner(
        msg.chat.id,
        reply,
        banner_type="user",
        disable_web_page_preview=True
    )

# -------- SCAM --------
@bot.message_handler(commands=['skamer'])
def add_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        return
    parts = msg.text.split(maxsplit=2)
    if len(parts)<3:
        send_with_banner(msg.chat.id,"`/skamer Nick link`",banner_type="skam",parse_mode="Markdown")
        return
    data = load_scammers()
    data[parts[1]] = parts[2]
    save_scammers(data)
    send_with_banner(msg.chat.id,"✅ Добавлено", banner_type="skam")

@bot.message_handler(commands=['unskam'])
def remove_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        send_with_banner(msg.chat.id,"⛔ Нет прав", banner_type="skam")
        return

    parts = msg.text.split(" ",1)
    if len(parts)<2:
        send_with_banner(
            msg.chat.id,
            "🔴 `УКАЖИ НИК`\n\nПример:\n`/unskam HeroOfTitan`",
            banner_type="skam",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    data = load_scammers()
    if name in data:
        del data[name]
        save_scammers(data)
        send_with_banner(msg.chat.id,f"🗑 *{name}* удалён из скам-листа.", banner_type="skam", parse_mode="Markdown")
    else:
        send_with_banner(msg.chat.id,"❌ Этот игрок не найден в скам-листе.", banner_type="skam")

@bot.message_handler(commands=['skam'])
def list_scam(msg):
    data = load_scammers()
    if not data:
        send_with_banner(msg.chat.id,"🛡️ Список пуст", banner_type="skam")
        return

    def escape_md(text):
        return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

    txt = "🚫 *SCAM LIST*\n\n"
    for i, (k,v) in enumerate(data.items(),1):
        safe_name = escape_md(k)
        safe_link = escape_md(v)
        txt += f"{i}. 👤 *{safe_name}*\n🔗 {safe_link}\n\n"

    send_with_banner(
        msg.chat.id,
        txt,
        banner_type="skam",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )

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
