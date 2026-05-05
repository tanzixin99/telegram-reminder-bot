from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
TOKEN = os.environ["BOT_TOKEN"]

ALLOWED_GROUP_IDS = [-1002769452421, -1003434455784]


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data

    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"⏰ REMINDER\n\n{data['msg']}"
    )


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in ALLOWED_GROUP_IDS:
        return

    message = update.effective_message.text
    lines = message.split("\n")

    if len(lines) < 2:
        await update.message.reply_text(
            "Use format:\n/remind DD-MM HHMM\n[message]"
        )
        return

    try:
        first_line = lines[0].split()

        date_text = first_line[1]
        time_text = first_line[2]

        day, month = map(int, date_text.split("-"))
        hour = int(time_text[:2])
        minute = int(time_text[2:])

        now = datetime.now()
        target_time = datetime(now.year, month, day, hour, minute)

        if target_time <= now:
            target_time = datetime(now.year + 1, month, day, hour, minute)

        seconds = (target_time - now).total_seconds()

    except Exception:
        await update.message.reply_text("Invalid format. Use: /remind DD-MM HHMM")
        return

    msg_body = "\n".join(lines[1:]).strip()

    if not msg_body:
        await update.message.reply_text("Message cannot be empty.")
        return

    # Delete original /remind command message
    # Bot must be group admin with "Delete messages" permission
    try:
        await update.effective_message.delete()
    except Exception:
        pass

    # Send clean admin message immediately
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📢 ADMIN MESSAGE\n\n{msg_body}"
    )

    # Schedule reminder
    context.job_queue.run_once(
        send_reminder,
        when=seconds,
        data={
            "chat_id": chat_id,
            "msg": msg_body
        }
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ Reminder scheduled for {target_time.strftime('%d-%m-%Y %H:%M')}"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Bot is running ✅")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("ping", ping))
    threading.Thread(target=run_web_server, daemon=True).start()
    app.run_polling()


if __name__ == "__main__":
    main()
