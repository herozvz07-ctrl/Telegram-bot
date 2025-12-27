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
ADMIN_USERNAME = "herozvz"  # Твой ник в Telegram (без @)
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("Переменная BOT_TOKEN не найдена в настройках Render!")

bot = telebot.TeleBot(TOKEN)

# --- WEB SERVER ДЛЯ RENDER (Чтобы бот не засыпал) ---
app = Flask('')

@app.route('/')
def home():
    return "Бот активен!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()

# --- ФУНКЦИИ РАБОТЫ С ФАЙЛОМ ---
def load_scammers():
    try:
        if os.path.exists(SCAM_FILE):
            with open(SCAM_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
    return {}

def save_scammers(data):
    try:
        with open(SCAM_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка записи файла: {e}")

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ RUCOY ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

def get_guild_description(soup, guild_name):
    try:
        page_text = soup.get_text("\n", strip=True)
        idx = page_text.lower().find(guild_name.lower())
        if idx != -1:
            start = idx + len(guild_name)
            m = re.search(r"(Founded on|Members)\b", page_text[start:], re.I)
            end = start + m.start() if m else len(page_text)
            return page_text[start:end].strip()
    except:
        pass
    return "Нет описания"

# ------------------------- КОМАНДЫ БОТА -------------------------

@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "⚔️ **Rucoy Bot запущен!**\n\nКоманды:\n/user [ник] — инфо об игроке\n/guild [название] — инфо о гильдии\n/skam — список скамеров", parse_mode="Markdown")

@bot.message_handler(commands=['skamer'])
def add_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        bot.reply_to(message, "⛔ У вас нет прав администратора.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "📝 Формат: `/skamer Nick Link`", parse_mode="Markdown")
            return
        name, link = parts[1], parts[2]
        data = load_scammers()
        data[name] = link
        save_scammers(data)
        bot.reply_to(message, f"✅ Игрок **{name}** добавлен в скам-лист.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unskam'])
def remove_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "📝 Формат: `/unskam Nick`", parse_mode="Markdown")
            return
        name = parts[1].strip()
        data = load_scammers()
        if name in data:
            del data[name]
            save_scammers(data)
            bot.reply_to(message, f"🗑 Игрок **{name}** удален из списка.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Игрок не найден в списке.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['skam'])
def list_scammers(message):
    data = load_scammers()
    if not data:
        bot.send_message(message.chat.id, "🛡️ **Список скамеров пуст!**", parse_mode="Markdown")
        return
    
    text = "🚫 **СПИСОК ИЗВЕСТНЫХ СКАМЕРОВ** 🚫\n\n"
    for i, (name, link) in enumerate(data.items(), 1):
        # Вывод ссылки обычным текстом для избежания конфликтов Markdown
        text += f"{i}. 👤 **{name}**\n🔗 {link}\n\n"
    
    text += "⚠️ *Будьте осторожны при обмене!*"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Укажите название гильдии.")
            return
        name_raw = parts[1].strip()
        url = f"https://www.rucoyonline.com/guild/{quote(name_raw)}"
        
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            bot.reply_to(message, "Гильдия не найдена 📛")
            return
            
        soup = BeautifulSoup(resp.text, "html.parser")
        desc = get_guild_description(soup, name_raw)
        
        bot.reply_to(message, f"⚔️ Гильдия: **{name_raw}**\n📝 {desc}\n🔗 {url}", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при поиске гильдии.")

@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Укажите ник игрока.")
            return
        name = parts[1].strip()
        url = f"https://www.rucoyonline.com/characters/{quote(name)}"
        
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            bot.reply_to(message, f"👤 Игрок: **{name}**\n🔗 {url}", parse_mode="Markdown")
        else:
            bot.reply_to(message, "Игрок не найден 📛")
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка при поиске игрока.")

# --- ЗАПУСК БОТА ---
if __name__ == "__main__":
    keep_alive()
    print("Очистка старых соединений...")
    
    try:
        # Убрали drop_pending_updates, чтобы не было ошибки на старых версиях библиотеки
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    print("Бот запущен!")
    
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception as e:
            print(f"Перезапуск из-за ошибки: {e}")
            time.sleep(5)
    
