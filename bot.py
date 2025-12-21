import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import telebot
from flask import Flask        
from threading import Thread

# 🔑 Токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# --- БЛОК ДЛЯ RENDER (WEB SERVER) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    # Render сам назначит порт, обычно 10000 или 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()
# ------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

MENU_WORDS = {
    "le navigation","rucoy online","welcome","news","highscores",
    "characters","guilds","sign in","sign in with google","sign in with apple"
}

# ------------------------- Вспомогательные функции -------------------------
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

# ------------------------- START -------------------------
@bot.message_handler(commands=['start'])
def send_start(message):
    bot.reply_to(message, "Бот запущен и готов к работе! Доступные команды: /user и /guild")

# ------------------------- /GUILD -------------------------
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
        
        members_count = "Не указано"
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")
            num = sum(1 for r in rows if r.find_all("td"))
            members_count = str(num) if num > 0 else "Не указано"

        desc_clean = description.replace("```", "`\u200b``")
        show_desc = bool(desc_clean and desc_clean.lower() != "нет описания")
        
        reply = [f"⚔️ Guild: *{pretty_title}*", f"👥 Members: *{members_count}*", f"📅 Created on: *{created}*"]
        if show_desc:
            reply.extend(["📝 Описание:", f"```\n{desc_clean}\n```"])
        reply.append(f"🔗 Ссылка: {url}")
        
        bot.reply_to(message, "\n".join(reply), parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка в /guild: {str(e)}")

# ------------------------- /USER -------------------------
@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        text = message.text or ""
        parts = text.split(" ", 1)
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Укажи ник игрока.")
            return

        username_raw = parts[1].strip()
        encoded_name = quote(username_raw, safe="")
        
        # Собираем ссылку максимально аккуратно
        base_url = "[https://www.rucoyonline.com/characters/](https://www.rucoyonline.com/characters/)"
        full_url = (base_url + encoded_name).strip()

        resp = requests.get(full_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Игрок не найден 📛")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        char_table = soup.find("table")
        if not char_table:
            bot.reply_to(message, "Информация о игроке не найдена 📛")
            return

        data = {}
        for row in char_table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                data[key] = value

        reply = (
            f"👤 Nik: {data.get('Name', username_raw)}\n"
            f"📊 LvL: {data.get('Level', 'Не указано')}\n"
            f"⚔️ Гильдия: {data.get('Guild', 'Нет гильдии')}\n"
            f"🟢 Online: {data.get('Last online', 'Не указано')}\n"
            f"📅 Создан: {data.get('Born', 'Не указано')}\n"
            f"🔗 Ссылка: {full_url}"
        )
        bot.reply_to(message, reply, disable_web_page_preview=True)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка в /user: {str(e)}")

# ------------------------- MAIN -------------------------
if __name__ == "__main__":
    keep_alive() # Запуск веб-сервера для Render
    print("Бот запущен и веб-сервер активен...")
    
    while True:
        try:
            # infinity_polling сам перезапускается при ошибках сети
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as ex:
            print(f"Polling error: {ex}")
            time.sleep(5)
            
