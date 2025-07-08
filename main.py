import os
import asyncio
import sqlite3
from datetime import datetime
from flask import Flask
from threading import Thread

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import ChatInviteLink, ChatJoinRequest
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# === Google Sheets Setup ===
import os
import json
from oauth2client.service_account import ServiceAccountCredentials
import gspread

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Read JSON string from environment variable
creds_json = os.getenv("GOOGLE_CREDS_JSON")
creds_dict = json.loads(creds_json)

# Authorize with Google Sheets
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Delulu Data Invite").sheet1

def save_to_sheet(inviter_id, joiner_id):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([str(inviter_id), str(joiner_id), now])
        print(f"✅ Saved to Google Sheet: {inviter_id} invited {joiner_id}")
    except Exception as e:
        print(f"❌ Failed to save to Google Sheet: {e}")

# === SQLite Setup ===
conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS links (
    inviter_id INTEGER PRIMARY KEY,
    link TEXT
)
""")
conn.commit()

# === /getlink Command ===
@dp.message(Command("getlink"))
async def getlink(message: types.Message):
    if message.chat.type != 'private':
        return await message.reply("Please use this command in a private chat.")

    inviter_id = message.from_user.id
    link_name = f"invite_{inviter_id}"

    cur.execute("SELECT link FROM links WHERE inviter_id = ?", (inviter_id,))
    row = cur.fetchone()
    if row:
        return await message.answer(f"🔗 Your invite link:\n{row[0]}")

    link: ChatInviteLink = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        creates_join_request=True,
        name=link_name
    )

    cur.execute("INSERT OR REPLACE INTO links (inviter_id, link) VALUES (?, ?)", (inviter_id, link.invite_link))
    conn.commit()
    await message.answer(f"✅ Your invite link has been created:\n{link.invite_link}")

# === Handle Join Request ===
@dp.chat_join_request()
async def join_request(join: ChatJoinRequest):
    if not join.invite_link:
        return await bot.approve_chat_join_request(join.chat.id, join.from_user.id)

    joiner_id = join.from_user.id
    used_link = join.invite_link.invite_link

    cur.execute("SELECT inviter_id FROM links WHERE link = ?", (used_link,))
    row = cur.fetchone()
    if row:
        inviter_id = row[0]
        save_to_sheet(inviter_id, joiner_id)

    await bot.approve_chat_join_request(join.chat.id, joiner_id)

# === Flask Keep Alive ===
app = Flask(__name__)
@app.route('/')
def index():
    return "✅ Web server is running and bot is alive."

def run_web():
    app.run(host="0.0.0.0", port=8080)

# === Start Bot ===
async def main():
    print("✅ Telegram bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    Thread(target=run_web).start()
    asyncio.run(main())
