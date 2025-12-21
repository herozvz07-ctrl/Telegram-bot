import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import telebot

# 🔑 Получаем токен из переменной окружения
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

# Создаём объект бота
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# 🧠 Настройки заголовков
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

# 🧩 Команда /start
@bot.message_handler(commands=["start"])
def start_message(message):
    bot.reply_to(
        message,
        "👋 Добавь меня в чат, чтобы я начал работать!\n\n"
        "🔹 Доступные команды:\n"
        "`/user <ник>` — Информация об игроке\n"
        "`/guild <название>` — Информация о гильдии",
        parse_mode="Markdown"
    )

# ⚔️ Команда /guild
@bot.message_handler(commands=["guild"])
def handle_guild(message):
    try:
        cmd_parts = message.text.split(" ", 1)
        if len(cmd_parts) < 2:
            bot.reply_to(message, "⚠️ Укажи название гильдии после команды, например:\n`/guild Lotus`")
            return

        guild_name_raw = cmd_parts[1].strip()
        encoded = quote(guild_name_raw, safe="")
        url = f"https://www.rucoyonline.com/guild/{encoded}"  # исправленный URL

        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            bot.reply_to(message, "📛 Гильдия не найдена.")
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        # Извлечение данных
        page_text = soup.get_text("\n", strip=True)
        name = " ".join(w.capitalize() for w in guild_name_raw.split())

        m_created = re.search(r"Founded on\s*([A-Za-z0-9 ,]+)", page_text)
        created = m_created.group(1).strip() if m_created else "Не указано"

        table = soup.find("table")
        members = "Не указано"
        if table:
            rows = table.find_all("tr")
            num = sum(1 for r in rows if r.find_all("td"))
            members = str(num)

        desc = "Нет описания"
        h1 = soup.find("h1")
        if h1:
            desc_tags = h1.find_all_next(["p", "div"], limit=10)
            desc_parts = []
            for t in desc_tags:
                txt = t.get_text(" ", strip=True)
                if txt and not re.search(r"(Founded on|Members)", txt, re.I):
                    desc_parts.append(txt)
            if desc_parts:
                desc = " ".join(desc_parts)

        info_text = (
            f"⚔️ Guild: *{name}*\n"
            f"👥 Members: *{members}*\n"
            f"📅 Created on: *{created}*\n"
            f"📝 Description: {desc}\n"
            f"🔗 Ссылка: {url}"
        )

        bot.reply_to(message, info_text)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# 👤 Команда /user
@bot.message_handler(commands=["user"])
def handle_user(message):
    try:
        cmd_parts = message.text.split(" ", 1)
        if len(cmd_parts) < 2:
            bot.reply_to(message, "⚠️ Укажи ник игрока, например:\n`/user Hero Of Titan`")
            return

        username = cmd_parts[1].strip()
        encoded = quote(username, safe="")
        url = f"https://www.rucoyonline.com/characters/{encoded}"

        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            bot.reply_to(message, "📛 Игрок не найден.")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text("\n", strip=True)

        # --- Извлечение информации ---
        name_match = re.search(r"Name\s+([A-Za-z0-9 _]+)", page_text)
        level_match = re.search(r"Level\s+(\d+)", page_text)
        guild_match = re.search(r"Guild\s+([A-Za-z0-9 _]+)", page_text)
        online_match = re.search(r"Last online\s+([A-Za-z0-9 ,]+)", page_text)
        born_match = re.search(r"Born\s+([A-Za-z0-9 ,]+)", page_text)

        name = name_match.group(1).strip() if name_match else username
        lvl = level_match.group(1).strip() if level_match else "?"
        guild = guild_match.group(1).strip() if guild_match else "Без гильдии"
        online = online_match.group(1).strip() if online_match else "Неизвестно"
        born = born_match.group(1).strip() if born_match else "Неизвестно"

        reply = (
            f"👤 Nik: *{name}*\n"
            f"📊 LvL: *{lvl}*\n"
            f"⚔️ Гильдия: *{guild}*\n"
            f"🟢 Online: *{online}*\n"
            f"📅 Создан: *{born}*\n"
            f"🔗 Ссылка: {url}"
        )

        bot.reply_to(message, reply)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# 🚀 Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as ex:
            print("Ошибка:", ex)
            time.sleep(3)
