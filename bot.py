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
ADMIN_USERNAME = "herozvz"  # Твой ник в Telegram
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# --- БЛОК ДЛЯ RENDER (WEB SERVER) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

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
                if not content: return {}
                return json.loads(content)
    except Exception as e:
        print(f"Ошибка загрузки JSON: {e}")
    return {}

def save_scammers(data):
    with open(SCAM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПАРСИНГА ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}
MENU_WORDS = {"le navigation","rucoy online","welcome","news","highscores","characters","guilds","sign in","sign in with google","sign in with apple"}

def remove_adjacent_duplicates(lines):
    if not lines: return lines
    out = [lines[0]]
    for ln in lines[1:]:
        if ln != out[-1]: out.append(ln)
    return out

def remove_repeated_block(lines):
    n = len(lines)
    if n < 2: return lines
    for k in range(1, n//2 + 1):
        if n >= 2*k and lines[0:k] == lines[k:2*k]:
            return lines[0:k] + lines[2*k:]
    return lines

def extract_description(soup, guild_name_raw):
    page_text = soup.get_text("\n", strip=True)
    idx = page_text.lower().find(guild_name_raw.lower())
    chunk = ""
    if idx != -1:
        start = idx + len(guild_name_raw)
        m = re.search(r"(Founded on|Members)\b", page_text[start:], re.I)
        end = start + m.start() if m else len(page_text)
        chunk = page_text[start:end].strip()
    else:
        h1 = soup.find("h1")
        if h1:
            pieces = []
            for elem in h1.next_elements:
                if isinstance(elem, str): t = elem.strip()
                else: t = elem.get_text(" ", strip=True)
                if not t: continue
                if re.search(r"(Founded on|Members)\b", t, re.I): break
                pieces.append(t)
            chunk = " ".join(pieces).strip()

    if not chunk: return "Нет описания"
    lines = [ln.strip() for ln in re.split(r"\n+", chunk) if ln.strip()]
    filtered = [ln for ln in lines if not any(menu in ln.lower() for menu in MENU_WORDS) and ln.lower() != guild_name_raw.lower()]
    filtered = remove_adjacent_duplicates(filtered)
    filtered = remove_repeated_block(filtered)
    desc = "\n".join(filtered).strip()
    return desc if desc else "Нет описания"

# ------------------------- SCAM SYSTEM -------------------------

@bot.message_handler(commands=['skamer'])
def add_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ Формат: `/skamer Nick Link`", parse_mode="Markdown")
            return
        name, link = parts[1], parts[2]
        data = load_scammers()
        data[name] = link
        save_scammers(data)
        bot.reply_to(message, f"✅ Игрок **{name}** добавлен в список.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unskam'])
def remove_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        bot.reply_to(message, "⛔ У вас нет прав.")
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Формат: `/unskam Nick`", parse_mode="Markdown")
            return
        name = parts[1].strip()
        data = load_scammers()
        if name in data:
            del data[name]
            save_scammers(data)
            bot.reply_to(message, f"🗑 Игрок **{name}** удален из списка.", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❓ Игрок не найден в списке.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['skam'])
def list_scammers(message):
    try:
        data = load_scammers()
        if not data:
            bot.send_message(message.chat.id, "🛡️ *Список скамеров пуст!*", parse_mode="Markdown")
            return
        
        text = "🚫 **СПИСОК ИЗВЕСТНЫХ СКАМЕРОВ** 🚫\n\n"
        for i, (name, link) in enumerate(data.items(), 1):
            # Используем жирный шрифт для имени и просто текст для ссылки, чтобы избежать ошибок Markdown
            text += f"{i}. 👤 **{name}**\n🔗 {link}\n\n"
        
        text += "⚠️ *Будьте осторожны при сделках!*"
        bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка вывода: {e}")

# ------------------------- СТАРЫЕ КОМАНДЫ -------------------------

@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "Бот готов! Команды: /user, /guild, /skam")

@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        text = message.text or ""
        parts = text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Укажи название гильдии.")
            return
        
        guild_name_raw = parts[1].strip()
        encoded = quote(guild_name_raw, safe="")
        url = f"https://www.rucoyonline.com/guild/{encoded}".strip()
        
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Гильдия не найдена 📛")
            return
        
        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text("\n", strip=True)
        
        pretty_title = " ".join(w.capitalize() for w in guild_name_raw.split())
        description = extract_description(soup, guild_name_raw)
        
        created = "Не указано"
        m_created = re.search(r"Founded on\s*([A-Za-z0-9 ,]+)", page_text)
        if m_created: created = m_created.group(1).strip()
        
        table = soup.find("table")
        members_count = str(sum(1 for r in table.find_all("tr") if r.find_all("td"))) if table else "Не указано"

        desc_clean = description.replace("```", "`\u200b``")
        reply = [f"⚔️ Guild: *{pretty_title}*", f"👥 Members: *{members_count}*", f"📅 Created on: *{created}*"]
        if desc_clean.lower() != "нет описания":
            reply.extend(["📝 Описание:", f"```\n{desc_clean}\n```"])
        reply.append(f"🔗 Ссылка: {url}")
        
        bot.reply_to(message, "\n".join(reply), parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        text = message.text or ""
        parts = text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Укажи ник.")
            return
        username = parts[1].strip()
        url = f"[https://www.rucoyonline.com/characters/](https://www.rucoyonline.com/characters/){quote(username, safe='')}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Игрок не найден 📛")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            bot.reply_to(message, "Информация не найдена 📛")
            return
        data = {row.find_all("td")[0].get_text(strip=True): row.find_all("td")[1].get_text(strip=True) for row in table.find_all("tr") if len(row.find_all("td")) == 2}
        reply = (f"👤 Nik: {data.get('Name', username)}\n📊 LvL: {data.get('Level', '???')}\n"
                 f"⚔️ Гильдия: {data.get('Guild', 'Нет')}\n🟢 Online: {data.get('Last online', '???')}\n"
                 f"📅 Создан: {data.get('Born', '???')}\n🔗 Ссылка: {url}")
        bot.reply_to(message, reply, disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

if __name__ == "__main__":
    keep_alive()
    
    # Пытаемся очистить старые соединения
    try:
        bot.remove_webhook()
        print("Старые соединения очищены.")
        time.sleep(2)  # Короткая пауза, чтобы сервер Telegram успел обновить статус
    except Exception as e:
        print(f"Ошибка при удалении вебхука: {e}")

    print("Бот запущен и готов к работе...")
    
    # Запускаем polling с автоматическим перезапуском
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

