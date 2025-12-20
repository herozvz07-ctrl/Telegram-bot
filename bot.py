import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import telebot

# --- ВСТАВЬ СВОЙ ТОКЕН ---
TOKEN = "8274918323:AAF2tC2tb_6TvblGuW1FIBTGggCCHN52hUk"
# --------------------------

bot = telebot.TeleBot(TOKEN, parse_mode=None)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

MENU_WORDS = {
    "le navigation","rucoy online","welcome","news","highscores",
    "characters","guilds","sign in","sign in with google","sign in with apple"
}


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
                t = elem.strip() if isinstance(elem, str) else elem.get_text(" ", strip=True)
                if not t:
                    continue
                if re.search(r"(Founded on|Members)\b", t, re.I):
                    break
                pieces.append(t)
            chunk = " ".join(pieces).strip()
    if not chunk:
        return "Нет описания"
    lines = [ln.strip() for ln in re.split(r"\n+", chunk) if ln.strip()]
    filtered = []
    for ln in lines:
        low = ln.lower()
        if any(menu in low for menu in MENU_WORDS):
            continue
        if low == guild_name_raw.lower():
            continue
        filtered.append(ln)
    filtered = remove_adjacent_duplicates(filtered)
    filtered = remove_repeated_block(filtered)
    return "\n".join(filtered).strip() if filtered else "Нет описания"


def extract_guild_info_from_soup(soup, guild_name_raw):
    page_text = soup.get_text("\n", strip=True)
    pretty_title = " ".join(w.capitalize() for w in guild_name_raw.split())

    description = extract_description(soup, guild_name_raw)

    created = None
    m_created = re.search(r"Founded on\s*([A-Za-z0-9 ,]+)", page_text)
    if m_created:
        created = m_created.group(1).strip()

    members_count = None
    table = soup.find("table")
    if table:
        rows = table.find_all("tr")
        num = sum(1 for r in rows if r.find_all("td"))
        if num > 0:
            members_count = str(num)

    if not created and not members_count:
        return None

    return {
        "title": pretty_title,
        "description": description if description else "Нет описания",
        "created": created if created else "Не указано",
        "members_count": members_count if members_count else "Не указано"
    }


@bot.message_handler(commands=['guild'])
def handle_guild(message):
    try:
        parts = message.text.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            bot.reply_to(message, "⚠️ Укажи название гильдии после команды, например /guild Imperia Of Titans")
            return
        guild_name_raw = parts[1].strip()
        encoded = quote(guild_name_raw, safe="")
        url = f"https://www.rucoyonline.com/guild/{encoded}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            bot.reply_to(message, "Гильдия не найдено 📛")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        info = extract_guild_info_from_soup(soup, guild_name_raw)
        if not info:
            bot.reply_to(message, "Гильдия не найдено 📛")
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


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.reply_to(message, "👋 Добавь меня в чат, чтобы я начал работать!")


if __name__ == "__main__":
    print("Бот запущен...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as ex:
            print("Polling crashed:", ex)
            time.sleep(3)
