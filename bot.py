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

# 🔑 Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "herozvz"
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

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
    bot.reply_to(msg, "🤖 Бот готов!\n/user\n/guild\n/skam")

# -------- GUILD --------
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

# -------- USER --------
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

# -------- SCAM --------
@bot.message_handler(commands=['skamer'])
def add_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        return
    parts = msg.text.split(maxsplit=2)
    if len(parts)<3:
        bot.reply_to(msg,"`/skamer Nick link`",parse_mode="Markdown")
        return
    data = load_scammers()
    data[parts[1]] = parts[2]
    save_scammers(data)
    bot.reply_to(msg,"✅ Добавлено")

@bot.message_handler(commands=['skam'])
def list_scam(msg):
    data = load_scammers()
    if not data:
        bot.reply_to(msg,"🛡️ Список пуст")
        return
    txt="🚫 *SCAM LIST*\n\n"
    for i,(k,v) in enumerate(data.items(),1):
        txt+=f"{i}. *{k}*\n{v}\n\n"
    bot.send_message(msg.chat.id,txt,parse_mode="Markdown",disable_web_page_preview=True)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    time.sleep(1)
    print("Bot started")
    bot.infinity_polling()
