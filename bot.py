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

print("--- [ЭТАП 1] ИНИЦИАЛИЗАЦИЯ ---")
if not TOKEN:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена!")
else:
    print(f"✅ Токен получен (начало: {TOKEN[:5]}...)")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# --- РАБОТА С ФАЙЛОМ СКAMЕРОВ ---
def load_scammers():
    try:
        if os.path.exists(SCAM_FILE):
            with open(SCAM_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
    except Exception as e:
        print(f"Ошибка загрузки скам-листа: {e}")
    return {}

def save_scammers(data):
    try:
        with open(SCAM_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения скам-листа: {e}")

# --- WEB SERVER ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Alive!"

def run_web_server():
    # Render автоматически подставляет порт в переменную PORT
    port = int(os.environ.get("PORT", 8080))
    print(f"--- [ЭТАП 2] ЗАПУСК FLASK НА ПОРТУ {port} ---")
    app.run(host='0.0.0.0', port=port)

# --- ПАРСИНГ ОПИСАНИЯ ГИЛЬДИИ ---
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
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
            filtered = [ln for ln in lines if not any(w in ln.lower() for w in MENU_WORDS)]
            return "\n".join(filtered[:5]).strip() or "Нет описания"
    except: pass
    return "Нет описания"

# ------------------------- КОМАНДЫ БОТА -------------------------

@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "⚔️ Бот Rucoy Online готов! \nКоманды: /user [ник], /guild [название], /skam")

@bot.message_handler(commands=['skamer'])
def add_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        bot.reply_to(message, "⛔ У вас нет прав админа.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Формат: `/skamer Nick Link`", parse_mode="Markdown")
            return
        data = load_scammers()
        data[parts[1]] = parts[2]
        save_scammers(data)
        bot.reply_to(message, f"✅ Игрок *{parts[1]}* добавлен в список скамеров.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['skam'])
def list_scammers(message):
    data = load_scammers()
    if not data:
        bot.reply_to(message, "🛡️ Список скамеров пуст.")
        return
    text = "🚫 *СПИСОК ИЗВЕСТНЫХ СКАМЕРОВ* 🚫\n\n"
    for i, (name, link) in enumerate(data.items(), 1):
        text += f"{i}. 👤 *{name}*\n🔗 {link}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Введи ник игрока: `/user Ник`", parse_mode="Markdown")
            return
        
        name = parts[1].strip()
        url = f"https://www.rucoyonline.com/characters/{quote(name)}"
        
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            bot.reply_to(message, "Игрок не найден 📛")
            return
            
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            bot.reply_to(message, "Информация о персонаже скрыта или не найдена 📛")
            return
            
        d = {r.find_all("td")[0].get_text(strip=True): r.find_all("td")[1].get_text(strip=True) for r in table.find_all("tr") if len(r.find_all("td")) == 2}
        
        reply = (f"👤 *Nik:* {d.get('Name', name)}\n"
                 f"📊 *LvL:* {d.get('Level', '???')}\n"
                 f"⚔️ *Гильдия:* {d.get('Guild', 'Нет')}\n"
                 f"🟢 *Online:* {d.get('Last online', '???')}\n"
                 f"📅 *Создан:* {d.get('Born', '???')}\n"
                 f"🔗 [Открыть профиль]({url})")
        bot.reply_to(message, reply, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка в /user: {e}")

@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Введи название гильдии: `/guild Название`", parse_mode="Markdown")
            return
            
        g_name = parts[1].strip()
        url = f"https://www.rucoyonline.com/guild/{quote(g_name)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        
        if resp.status_code != 200:
            bot.reply_to(message, "Гильдия не найдена 📛")
            return
            
        soup = BeautifulSoup(resp.text, "html.parser")
        desc = extract_description(soup, g_name)
        
        bot.reply_to(message, f"⚔️ *Guild:* {g_name}\n\n📝 *Описание:*\n{desc}\n\n🔗 [Страница гильдии]({url})", 
                     parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка в /guild: {e}")

# ------------------------- ЗАПУСК -------------------------
if __name__ == "__main__":
    # 1. Запуск Flask в потоке
    server_thread = Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    # 2. Очистка очереди и запуск поллинга
    print("--- [ЭТАП 3] ПОДКЛЮЧЕНИЕ К TELEGRAM ---")
    try:
        bot.remove_webhook(drop_pending_updates=True)
        time.sleep(1)
        print("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
    
