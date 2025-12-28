import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# ---------------- Конфигурация ----------------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = "herozvz"
SCAM_FILE = "scammers.json"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ---------------- Банеры ----------------
START_BANNER = "https://i.ibb.co/5X2W2c8q/e9a3f45d2f734f9126820cdca7b55266.jpg"

# ---------------- SCAM STORAGE ----------------
def load_scammers():
    try:
        if os.path.exists(SCAM_FILE):
            with open(SCAM_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if data:
                    return json.loads(data)
    except:
        pass
    return {}

def save_scammers(data):
    with open(SCAM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ---------------- RENDER KEEP ALIVE ----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run_web_server, daemon=True).start()

# ---------------- PARSING ----------------
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MENU_WORDS = {
    "le navigation","rucoy online","welcome","news","highscores",
    "characters","guilds","sign in","sign in with google","sign in with apple"
}

def remove_adjacent_duplicates(lines):
    out = []
    for l in lines:
        if not out or l != out[-1]:
            out.append(l)
    return out

def remove_repeated_block(lines):
    n = len(lines)
    for k in range(1, n//2 + 1):
        if lines[:k] == lines[k:2*k]:
            return lines[k:]
    return lines

def extract_description(soup, name):
    text = soup.get_text("\n", strip=True)
    idx = text.lower().find(name.lower())
    chunk = ""
    if idx != -1:
        start = idx + len(name)
        m = re.search(r"(Founded on|Members)", text[start:], re.I)
        end = start + m.start() if m else len(text)
        chunk = text[start:end]
    if not chunk:
        return "РќРµС‚ РѕРїРёСЃР°РЅРёСЏ"

    lines = [l.strip() for l in chunk.split("\n") if l.strip()]
    lines = [l for l in lines if not any(m in l.lower() for m in MENU_WORDS)]
    lines = remove_adjacent_duplicates(lines)
    lines = remove_repeated_block(lines)
    return "\n".join(lines) if lines else "РќРµС‚ РѕРїРёСЃР°РЅРёСЏ"

# ---------------- COMMANDS ----------------

# НОВОЕ МЕНЮ START
@bot.message_handler(commands=['start'])
def send_start(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📘 Rucoy Wiki", url="https://t.me/rucoy_wiki"))
    kb.add(
        types.InlineKeyboardButton("💬 Rucoy Chat", url="https://t.me/Bancus_Rucoy/13"),
        types.InlineKeyboardButton("🛒 Rucoy Market", url="https://t.me/Bancus_Rucoy/4")
    )
    kb.add(types.InlineKeyboardButton("🧮 Calculator", callback_data="calc"))
    kb.add(
        types.InlineKeyboardButton("💰 Купить Gold", callback_data="buy_gold"),
        types.InlineKeyboardButton("📤 Продать Gold", url="https://t.me/Bancus_Rucoy/159")
    )
    kb.add(types.InlineKeyboardButton("ℹ️ Информация", callback_data="info"))

    bot.send_photo(
        message.chat.id,
        START_BANNER,
        caption="⚔️ *Rucoy Hub*\n\nВыберите раздел:",
        parse_mode="Markdown",
        reply_markup=kb
    )

# Обработка кнопок нового меню
@bot.callback_query_handler(func=lambda c: c.data == "calc")
def send_calculator(call):
    try:
        bot.forward_message(call.message.chat.id, "@rucoy_calculyator", 2)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Не удалось переслать файл: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "buy_gold")
def buy_gold_menu(call):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📊 Курсы и топ-трейдеры", callback_data="gold_rates"))
    kb.add(types.InlineKeyboardButton("➕ Ещё", url="https://t.me/Bancus_Rucoy/159"))
    bot.send_message(
        call.message.chat.id,
        "💰 *Покупка Gold*\n\nСредний курс:\n16₽ ≈ 1кк",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "gold_rates")
def gold_rates(call):
    bot.send_message(call.message.chat.id, "📊 *Курсы Gold*\n\nЛучшие трейдеры и цены скоро здесь.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "info")
def info(call):
    bot.send_message(
        call.message.chat.id,
        "ℹ️ *Информация*\n\n📌 Команды:\n`/guild` — информация о гильдии\n`/user` — информация об игроке\n`/skam` — список скамеров\n\n👨‍💻 Создатель: @herozvz",
        parse_mode="Markdown"
    )

# ТВОЙ ОРИГИНАЛЬНЫЙ ТЕКСТ ДЛЯ GUILD
@bot.message_handler(commands=['guild'])
def guild(msg):
    parts = msg.text.split(" ",1)
    if len(parts) < 2:
        bot.reply_to(
            msg,
            "рџ”ґ `РЈРљРђР–Р РќРђР—Р’РђРќРР• Р“РР›Р¬Р”РР•`\n\nРџСЂРёРјРµСЂ:\n`/guild Imperia Of Titans`",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/guild/{quote(name)}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        bot.reply_to(msg, "Р“РёР»СЊРґРёСЏ РЅРµ РЅР°Р№РґРµРЅР° рџ“›")
        return

    soup = BeautifulSoup(r.text,"html.parser")
    text = soup.get_text("\n",strip=True)

    created = re.search(r"Founded on ([A-Za-z0-9 ,]+)", text)
    created = created.group(1) if created else "РќРµ СѓРєР°Р·Р°РЅРѕ"

    members = soup.find_all("tr")
    members = sum(1 for r in members if r.find_all("td"))

    desc = extract_description(soup, name)

    reply = (
        f"вљ”пёЏ *{name}*\n"
        f"рџ‘Ґ Members: *{members}*\n"
        f"рџ“… Created: *{created}*\n\n"
        f"```\n{desc}\n```\n"
        f"рџ”— {url}"
    )

    bot.reply_to(msg, reply, parse_mode="Markdown", disable_web_page_preview=True)

# ТВОЙ ОРИГИНАЛЬНЫЙ ТЕКСТ ДЛЯ USER
@bot.message_handler(commands=['user'])
def user(msg):
    parts = msg.text.split(" ",1)
    if len(parts) < 2:
        bot.reply_to(
            msg,
            "рџ”ґ `РЈРљРђР–Р РќРРљ РР“Р РћРљРђ`\n\nРџСЂРёРјРµСЂ:\n`/user Hero Of Titan`",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    url = f"https://www.rucoyonline.com/characters/{quote(name)}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        bot.reply_to(msg, "РРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ рџ“›")
        return

    soup = BeautifulSoup(r.text,"html.parser")
    table = soup.find("table")
    if not table:
        bot.reply_to(msg, "РќРµС‚ РґР°РЅРЅС‹С… рџ“›")
        return

    data = {}
    for tr in table.find_all("tr"):
        td = tr.find_all("td")
        if len(td)==2:
            data[td[0].text.strip()] = td[1].text.strip()

    reply = (
        f"рџ‘¤ {data.get('Name',name)}\n"
        f"рџ“Љ Level: {data.get('Level','?')}\n"
        f"вљ”пёЏ Guild: {data.get('Guild','None')}\n"
        f"рџџў Last online: {data.get('Last online','?')}\n"
        f"рџ“… Born: {data.get('Born','?')}\n"
        f"рџ”— {url}"
    )

    bot.reply_to(msg, reply, disable_web_page_preview=True)

# ТВОЙ ОРИГИНАЛЬНЫЙ UNSKAM
@bot.message_handler(commands=['unskam'])
def remove_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        bot.reply_to(msg, "в›” РќРµС‚ РїСЂР°РІ.")
        return

    parts = msg.text.split(" ", 1)
    if len(parts) < 2:
        bot.reply_to(
            msg,
            "рџ”ґ `РЈРљРђР–Р РќРРљ`\n\nРџСЂРёРјРµСЂ:\n`/unskam pidor`",
            parse_mode="Markdown"
        )
        return

    name = parts[1].strip()
    data = load_scammers()

    if name in data:
        del data[name]
        save_scammers(data)
        bot.reply_to(msg, f"рџ—‘ *{name}* СѓРґР°Р»С‘РЅ РёР· СЃРєР°Рј-Р»РёСЃС‚Р°.", parse_mode="Markdown")
    else:
        bot.reply_to(msg, "вќЊ Р­С‚РѕС‚ РёРіСЂРѕРє РЅРµ РЅР°Р№РґРµРЅ РІ СЃРєР°Рј-Р»РёСЃС‚Рµ.")
        
# -------- SCAM --------
@bot.message_handler(commands=['skamer'])
def add_scam(msg):
    if msg.from_user.username != ADMIN_USERNAME:
        return
    parts = msg.text.split(maxsplit=2)
    if len(parts)<3:
        bot.reply_to(msg,"`/skamer Nick link`",parse_mode="Markdown")
        return
    data = load_scammers()
    data[parts[1]] = parts[2]
    save_scammers(data)
    bot.reply_to(msg,"вњ… Р”РѕР±Р°РІР»РµРЅРѕ")

@bot.message_handler(commands=['skam'])
def list_scam(msg):
    data = load_scammers()
    if not data:
        bot.reply_to(msg,"рџ›ЎпёЏ РЎРїРёСЃРѕРє РїСѓСЃС‚")
        return
    txt="рџљ« *SCAM LIST*\n\n"
    for i,(k,v) in enumerate(data.items(),1):
        txt+=f"{i}. *{k}*\n{v}\n\n"
    bot.send_message(msg.chat.id, txt, disable_web_page_preview=True)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    keep_alive()
    bot.remove_webhook()
    time.sleep(1)
    print("Bot started")
    bot.infinity_polling()
                  
