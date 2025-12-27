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
ADMIN_USERNAME = "herozvz"  # Твой ник без @
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# --- ФУНКЦИИ ДЛЯ РАБОТЫ СО СКАМ-ЛИСТОМ ---
def load_scammers():
    try:
        if os.path.exists(SCAM_FILE):
            with open(SCAM_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
    except Exception as e:
        print(f"Error loading scammers: {e}")
    return {}

def save_scammers(data):
    with open(SCAM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПАРСИНГА (ИЗ ТВОЕГО КОДА) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

MENU_WORDS = {
    "le navigation","rucoy online","welcome","news","highscores",
    "characters","guilds","sign in","sign in with google","sign in with apple"
}

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
    filtered = [ln for ln in lines if not any(m in ln.lower() for m in MENU_WORDS) and ln.lower() != guild_name_raw.lower()]
    filtered = remove_adjacent_duplicates(filtered)
    filtered = remove_repeated_block(filtered)
    desc = "\n".join(filtered).strip()
    return desc if desc else "Нет описания"

def extract_guild_info_from_soup(soup, guild_name_raw):
    page_text = soup.get_text("\n", strip=True)
    pretty_title = " ".join(w.capitalize() for w in guild_name_raw.split())
    description = extract_description(soup, guild_name_raw)
    created = "Не указано"
    m_created = re.search(r"Founded on\s*([A-Za-z0-9 ,]+)", page_text)
    if m_created: created = m_created.group(1).strip()
    members_count = "Не указано"
    table = soup.find("table")
    if table:
        rows = table.find_all("tr")
        num = sum(1 for r in rows if r.find_all("td"))
        members_count = str(num) if num > 0 else "Не указано"
    if created == "Не указано" and members_count == "Не указано": return None
    return {"title": pretty_title, "description": description, "created": created, "members_count": members_count}

# ------------------------- КОМАНДЫ -------------------------

@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "Бот готов! Команды: /user [ник], /guild [гильдия], /skam")

@bot.message_handler(commands=['skamer'])
def add_scammer(message):
    if message.from_user.username != ADMIN_USERNAME:
        bot.reply_to(message, "⛔ Нет прав.")
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
        bot.reply_to(message, f"✅ Игрок *{name}* добавлен.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unskam'])
def remove_scammer(message):
    if message.from_user.username != ADMIN_USERNAME: return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2: return
        name = parts[1].strip()
        data = load_scammers()
        if name in data:
            del data[name]
            save_scammers(data)
            bot.reply_to(message, f"🗑 *{name}* удален.")
        else:
            bot.reply_to(message, "❌ Не найден.")
    except: pass

@bot.message_handler(commands=['skam'])
def list_scammers(message):
    scammers = load_scammers()
    if not scammers:
        bot.reply_to(message, "🛡️ Список скамеров пуст.")
        return
    text = "🚫 *СПИСОК СКАМЕРОВ* 🚫\n\n"
    for i, (name, link) in enumerate(scammers.items(), 1):
        text += f"{i}. 👤 *{name}*\n   🔗 {link}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "⚠️ Укажи название гильдии.")
            return
        guild_name_raw = parts[1].strip()
        url = f"https://www.rucoyonline.com/guild/{quote(guild_name_raw)}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Гильдия не найдена 📛")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        info = extract_guild_info_from_soup(soup, guild_name_raw)
        if not info:
            bot.reply_to(message, "Гильдия не найдена 📛")
            return
        desc = info["description"].replace("```", "`\u200b``")
        reply = [f"⚔️ Guild: *{info['title']}*", f"👥 Members: *{info['members_count']}*", f"📅 Create on: *{info['created']}*"]
        if desc.lower() != "нет описания":
            reply.extend(["📝 Описание:", f"```\n{desc}\n```"])
        reply.append(f"🔗 Ссылка: {url}")
        bot.reply_to(message, "\n".join(reply), parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "⚠️ Укажи ник игрока.")
            return
        username_raw = parts[1].strip()
        url = f"[https://www.rucoyonline.com/characters/](https://www.rucoyonline.com/characters/){quote(username_raw)}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Игрок не найден 📛")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        char_table = soup.find("table")
        if not char_table:
            bot.reply_to(message, "Информация не найдена 📛")
            return
        data = {r.find_all("td")[0].get_text(strip=True): r.find_all("td")[1].get_text(strip=True) for r in char_table.find_all("tr") if len(r.find_all("td")) == 2}
        reply = (f"👤 Nik: {data.get('Name', username_raw)}\n📊 LvL: {data.get('Level', '???')}\n"
                 f"⚔️ Гильдия: {data.get('Guild', 'Нет')}\n🟢 Online: {data.get('Last online', '???')}\n"
                 f"📅 Создан: {data.get('Born', '???')}\n🔗 Ссылка: {url}")
        bot.reply_to(message, reply, disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ------------------------- MAIN -------------------------
if __name__ == "__main__":
    keep_alive()
    try:
        bot.remove_webhook()
        time.sleep(1)
    except: pass
    print("Бот запущен...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as ex:
            time.sleep(3)
    
