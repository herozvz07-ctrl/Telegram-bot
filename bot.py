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

# 🔑 КОНФИГУРАЦИЯ
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "herozvz" 
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# --- РАБОТА С ФАЙЛОМ ---
def load_scammers():
    try:
        if os.path.exists(SCAM_FILE):
            with open(SCAM_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
    except: pass
    return {}

def save_scammers(data):
    with open(SCAM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- WEB SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Alive"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()

# --- ПАРСИНГ ---
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
MENU_WORDS = {"le navigation","rucoy online","welcome","news","highscores","characters","guilds","sign in"}

def extract_description(soup, guild_name_raw):
    try:
        page_text = soup.get_text("\n", strip=True)
        idx = page_text.lower().find(guild_name_raw.lower())
        if idx != -1:
            start = idx + len(guild_name_raw)
            m = re.search(r"(Founded on|Members)\b", page_text[start:], re.I)
            chunk = page_text[start:start + m.start() if m else len(page_text)].strip()
            lines = [ln.strip() for ln in re.split(r"\n+", chunk) if ln.strip()]
            filtered = [ln for ln in lines if not any(m in ln.lower() for m in MENU_WORDS)]
            return "\n".join(filtered[:5]).strip() or "Нет описания"
    except: pass
    return "Нет описания"

# ------------------------- КОМАНДЫ -------------------------

@bot.message_handler(commands=['skamer'])
def add_scammer(message):
    if message.from_user.username != ADMIN_USERNAME: return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3: return
        data = load_scammers()
        data[parts[1]] = parts[2]
        save_scammers(data)
        bot.reply_to(message, f"✅ Игрок {parts[1]} добавлен.")
    except: pass

@bot.message_handler(commands=['skam'])
def list_scammers(message):
    data = load_scammers()
    if not data:
        bot.reply_to(message, "🛡️ Список пуст.")
        return
    text = "🚫 *СПИСОК СКАМЕРОВ* 🚫\n\n"
    for i, (name, link) in enumerate(data.items(), 1):
        text += f"{i}. 👤 *{name}*\n🔗 {link}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2: return
        
        name = parts[1].strip()
        # ИСПРАВЛЕНО: Чистый URL без Markdown скобок
        url = f"https://www.rucoyonline.com/characters/{quote(name)}"
        
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            bot.reply_to(message, "Игрок не найден 📛")
            return
            
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            bot.reply_to(message, "Информация не найдена 📛")
            return
            
        d = {r.find_all("td")[0].get_text(strip=True): r.find_all("td")[1].get_text(strip=True) for r in table.find_all("tr") if len(r.find_all("td")) == 2}
        
        reply = (f"👤 Nik: {d.get('Name', name)}\n📊 LvL: {d.get('Level', '???')}\n"
                 f"⚔️ Гильдия: {d.get('Guild', 'Нет')}\n🟢 Online: {d.get('Last online', '???')}\n"
                 f"🔗 Ссылка: {url}")
        bot.reply_to(message, reply, disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2: return
        g_name = parts[1].strip()
        url = f"https://www.rucoyonline.com/guild/{quote(g_name)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            bot.reply_to(message, "Не найдено.")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        desc = extract_description(soup, g_name)
        bot.reply_to(message, f"⚔️ Guild: *{g_name}*\n📝 {desc}\n🔗 {url}", parse_mode="Markdown", disable_web_page_preview=True)
    except: pass

# --- ЗАПУСК ---
if __name__ == "__main__":
    keep_alive()
    try: bot.remove_webhook()
    except: pass
    print("Запущено!")
    bot.infinity_polling()
    
