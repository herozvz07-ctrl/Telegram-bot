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

bot = telebot.TeleBot(TOKEN)

# --- WEB SERVER ДЛЯ RENDER ---
app = Flask('')
@app.route('/')
def home():
    return "Бот работает!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()

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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}

def extract_description(soup, guild_name):
    try:
        page_text = soup.get_text("\n", strip=True)
        idx = page_text.lower().find(guild_name.lower())
        if idx != -1:
            start = idx + len(guild_name)
            m = re.search(r"(Founded on|Members)\b", page_text[start:], re.I)
            desc = page_text[start:start + m.start() if m else len(page_text)].strip()
            return desc if desc else "Нет описания"
    except: pass
    return "Нет описания"

# ------------------------- КОМАНДЫ -------------------------

@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "✅ Бот онлайн!\n\nКоманды:\n/user [ник]\n/guild [название]\n/skam - список кидал")

@bot.message_handler(commands=['skamer'])
def add_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        bot.reply_to(message, "⛔ Отказано в доступе.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "📝 Формат: `/skamer Ник Ссылка`", parse_mode="Markdown")
            return
        name, link = parts[1], parts[2]
        data = load_scammers()
        data[name] = link
        save_scammers(data)
        bot.reply_to(message, f"✅ Игрок **{name}** добавлен.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['unskam'])
def remove_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    try:
        name = message.text.split(maxsplit=1)[1].strip()
        data = load_scammers()
        if name in data:
            del data[name]
            save_scammers(data)
            bot.reply_to(message, f"🗑 **{name}** удален.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "Не найден.")
    except:
        bot.reply_to(message, "📝 Формат: `/unskam Ник`")

@bot.message_handler(commands=['skam'])
def list_scammers(message):
    data = load_scammers()
    if not data:
        bot.send_message(message.chat.id, "🛡️ Список пуст.")
        return
    
    text = "🚫 **СПИСОК СКАМЕРОВ** 🚫\n\n"
    for i, (name, link) in enumerate(data.items(), 1):
        # Используем максимально простой текст без сложных скобок
        text += f"{i}. 👤 **{name}**\n🔗 {link}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2: return
        name_raw = parts[1].strip()
        url = f"https://www.rucoyonline.com/guild/{quote(name_raw)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            bot.reply_to(message, "Не найдено.")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        desc = extract_description(soup, name_raw)
        bot.reply_to(message, f"⚔️ Guild: **{name_raw}**\n📝 {desc}\n🔗 {url}", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Ошибка парсинга.")

@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2: return
        name = parts[1].strip()
        url = f"https://www.rucoyonline.com/characters/{quote(name)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            bot.reply_to(message, f"👤 Игрок: **{name}**\n🔗 {url}", parse_mode="Markdown")
        else:
            bot.reply_to(message, "Не найден.")
    except:
        bot.reply_to(message, "Ошибка.")

# --- ЗАПУСК ---
if __name__ == "__main__":
    keep_alive()
    print("Запуск...")
    
    # 1. Удаляем вебхук и ОЧИЩАЕМ все накопившиеся сообщения, чтобы бот не завис
    bot.remove_webhook(drop_pending_updates=True) 
    time.sleep(1)
    
    # 2. Бесконечный цикл с защитой
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)
                
