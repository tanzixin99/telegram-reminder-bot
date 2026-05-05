import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]

ALLOWED_GROUP_IDS = [-1002769452421, -1003434455784]

reminders = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


def is_allowed_group(update: Update):
    return update.effective_chat.id in ALLOWED_GROUP_IDS


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    item = context.job.data

    await context.bot.send_message(
        chat_id=item["chat_id"],
        text=f"⏰ REMINDER\n\n{item['msg']}"
    )

    if item in reminders:
        reminders.remove(item)


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return

    message = update.effective_message
    chat_id = update.effective_chat.id
    lines = message.text.split("\n")

    if len(lines) < 2:
        await message.reply_text(
            "Use format:\n/remind DD-MM HHMM\n[message]\n\n"
            "Example:\n/remind 06-05 1500\nGood Day Bears..."
        )
        return

    try:
        first_line = lines[0].split()

        if len(first_line) != 3:
            raise ValueError

        date_text = first_line[1]
        time_text = first_line[2]

        day, month = map(int, date_text.split("-"))

        if len(time_text) != 4:
            raise ValueError

        hour = int(time_text[:2])
        minute = int(time_text[2:])

        now = datetime.now()
        target_time = datetime(now.year, month, day, hour, minute)

        if target_time <= now:
            target_time = datetime(now.year + 1, month, day, hour, minute)

        seconds = (target_time - now).total_seconds()

    except Exception:
        await message.reply_text(
            "Invalid format. Use:\n/remind DD-MM HHMM\n[message]"
        )
        return

    msg_body = "\n".join(lines[1:]).strip()

    if not msg_body:
        await message.reply_text("Message cannot be empty.")
        return

    try:
        await message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📢 ADMIN MESSAGE\n\n{msg_body}"
    )

    item = {
        "time": target_time,
        "msg": msg_body,
        "chat_id": chat_id,
        "job": None
    }

    job = context.job_queue.run_once(
        send_reminder,
        when=seconds,
        data=item
    )

    item["job"] = job
    reminders.append(item)
    reminders.sort(key=lambda x: x["time"])

    no = reminders.index(item) + 1

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ Reminder scheduled\nNo: {no}\nTime: {target_time.strftime('%d-%m-%Y %H:%M')}"
    )


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return

    chat_id = update.effective_chat.id
    chat_reminders = [r for r in reminders if r["chat_id"] == chat_id]
    chat_reminders.sort(key=lambda x: x["time"])

    if not chat_reminders:
        await update.message.reply_text("No active reminders.")
        return

    text = "📋 Active reminders:\n\n"

    for i, r in enumerate(chat_reminders, 1):
        preview = r["msg"][:70].replace("\n", " ")
        text += f"{i}. {r['time'].strftime('%d-%m-%Y %H:%M')} - {preview}...\n"

    await update.message.reply_text(text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed_group(update):
        return

    if len(context.args) != 1:
        await update.message.reply_text("Use: /cancel NUMBER\nExample: /cancel 1")
        return

    try:
        number = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return

    chat_id = update.effective_chat.id
    chat_reminders = [r for r in reminders if r["chat_id"] == chat_id]
    chat_reminders.sort(key=lambda x: x["time"])

    if number < 1 or number > len(chat_reminders):
        await update.message.reply_text("Reminder number not found.")
        return

    item = chat_reminders[number - 1]
    item["job"].schedule_removal()
    reminders.remove(item)

    await update.message.reply_text(f"❌ Reminder {number} cancelled.")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Bot is running ✅")


def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("ping", ping))

    app.run_polling()


if __name__ == "__main__":
    main()
