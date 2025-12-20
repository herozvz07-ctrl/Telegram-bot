import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import telebot

# ─── Токен берём из переменной окружения ───
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
# ──────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

# === Функции для обработки информации о гильдиях ===
def remove_adjacent_duplicates(lines):
    if not lines:
        return lines
    out = [lines[0]]
    for ln in lines[1:]:
        if ln != out[-1]:
            out.append(ln)
    return out

def remove_repeated_block(lines):
    n = len(lines)
    if n < 2:
        return lines
    for k in range(1, n//2 + 1):
        if n >= 2*k and lines[0:k] == lines[k:2*k]:
            if lines == lines[0:k] * (n // k):
                return lines[0:k]
            return lines[0:k] + lines[2*k:]
    return lines

# === Обработчики команд ===

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "👋 Добавь меня в чат, чтобы я начал работать!")

# Пример обработчика гильдии
@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "⚠️ Укажи название гильдии после команды, например /guild HeroGuild")
            return
        guild_name_raw = parts[1].strip()
        encoded = quote(guild_name_raw, safe="")
        url = f"https://www.rucoyonline.com/guilds/{encoded}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Гильдия не найдена 📛")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        # Здесь должна быть функция extract_guild_info_from_soup
        info = extract_guild_info_from_soup(soup, guild_name_raw)
        if not info:
            bot.reply_to(message, "Гильдия не найдена 📛")
            return

        desc = info["description"]
        show_description = desc.lower() != "нет описания"
        description_block = f"```\n{desc}\n```" if show_description else ""

        reply_lines = [
            f"⚔️ Guild: *{info['title']}*",
            f"👥 Members: *{info['members_count']}*",
            f"📅 Create on: *{info['created']}*",
        ]
        if show_description:
            reply_lines.append("📝 Описание:")
            reply_lines.append(description_block)
        reply_lines.append(f"🔗 Ссылка: {url}")

        bot.reply_to(message, "\n".join(reply_lines), parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# Обработчик пользователей
@bot.message_handler(commands=['user'])
def handle_user(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "⚠️ Укажи ник пользователя после команды, например /user Hero Of Titan")
            return
        user_name_raw = parts[1].strip()
        encoded = quote(user_name_raw, safe="")
        url = f"https://www.rucoyonline.com/characters/{encoded}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Пользователь не найден 📛")
            return
        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.find("table")
        info = {"Name":"Не указано","Level":"Не указано","Guild":"Нет","Online":"Не указано","Born":"Не указано"}
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    key = cols[0].get_text(strip=True)
                    val = cols[1].get_text(strip=True)
                    if "Name" in key:
                        info["Name"] = val
                    elif "Level" in key:
                        info["Level"] = val
                    elif "Guild" in key:
                        info["Guild"] = val if val else "Нет"
                    elif "Last online" in key:
                        info["Online"] = val
                    elif "Born" in key:
                        info["Born"] = val

        reply = f"👤 Nik: {info['Name']}\n"
        reply += f"📊 LvL: {info['Level']}\n"
        reply += f"⚔️ Гильдия: {info['Guild']}\n"
        reply += f"🟢 Online: {info['Online']}\n"
        reply += f"📅 Создан: {info['Born']}\n"
        reply += f"🔗 Ссылка: {url}"

        bot.reply_to(message, reply)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# === Запуск бота ===
if __name__ == "__main__":
    print("Бот запущен...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as ex:
            print("Polling crashed:", ex)
            time.sleep(3)
