import os
import sys
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# --- Bot Config ---
BOT_TOKEN = "8092249699:AAF4EjD-kggyuoK8ch_ipSLI5HU6gN002xg"
ADMIN_IDS = {6544649492}

# --- Logging Setup ---
os.makedirs("logs", exist_ok=True)
os.makedirs("chat_history", exist_ok=True)

bot_logger = logging.getLogger("LiveChatBot")
bot_logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("logs/bot.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
bot_logger.addHandler(file_handler)

error_handler = logging.FileHandler("logs/errors.log")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
bot_logger.addHandler(error_handler)

# --- Live Chat Bot Logic ---
class LiveChatBot:
    def __init__(self):
        self.user_sessions = {}
        self.pending_queue = []
        self.chat_logs = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in ADMIN_IDS:
            await update.message.reply_text("👮 Admin mode activated.")
            return
        await update.message.reply_text("🤖 Welcome! Please wait for an admin to join.")
        self.pending_queue.append(user_id)
        bot_logger.info(f"User {user_id} added to queue")
        for admin_id in ADMIN_IDS:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Accept", callback_data=f"accept_{user_id}")],
                [InlineKeyboardButton("Reject", callback_data=f"reject_{user_id}")]
            ])
            await context.bot.send_message(chat_id=admin_id, text=f"👤 New user in queue: {user_id}", reply_markup=keyboard)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        admin_id = query.from_user.id
        if admin_id not in ADMIN_IDS:
            await query.answer("⛔ Not authorized.")
            return
        if data.startswith("accept_"):
            user_id = int(data.split("_")[1])
            self.user_sessions[user_id] = admin_id
            self.user_sessions[admin_id] = user_id
            self.chat_logs[user_id] = []
            await context.bot.send_message(user_id, "✅ Admin joined the chat.")
            await context.bot.send_message(admin_id, f"✅ You joined chat with {user_id}")
            if user_id in self.pending_queue:
                self.pending_queue.remove(user_id)
            await query.answer("Chat started.")
        elif data.startswith("reject_"):
            user_id = int(data.split("_")[1])
            if user_id in self.pending_queue:
                self.pending_queue.remove(user_id)
                await context.bot.send_message(user_id, "❌ Your request was rejected.")
            await query.answer("User rejected.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        sender = update.effective_user.id
        if sender not in self.user_sessions:
            return
        receiver = self.user_sessions.get(sender)
        if not receiver:
            return
        text = update.message.text
        await context.bot.send_message(receiver, text)
        log = self.chat_logs.get(sender) or self.chat_logs.get(receiver)
        if log is not None:
            log.append(f"{sender}: {text}")

    async def end_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user.id
        partner = self.user_sessions.get(user)
        if not partner:
            await update.message.reply_text("❌ Not in chat.")
            return
        await context.bot.send_message(partner, "🚫 Chat ended.")
        await update.message.reply_text("✅ Chat ended.")
        self._end_session(user, partner)

    def _end_session(self, uid1, uid2):
        log = self.chat_logs.get(uid1) or self.chat_logs.get(uid2)
        if log:
            filename = f"chat_history/chat_{uid1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(log))
        for uid in (uid1, uid2):
            self.user_sessions.pop(uid, None)
            self.chat_logs.pop(uid, None)

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            return
        queue_status = "\n".join(str(uid) for uid in self.pending_queue) or "None"
        await update.message.reply_text(f"📋 Users in queue:\n{queue_status}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            return
        active = len(self.user_sessions) // 2
        queue = len(self.pending_queue)
        await update.message.reply_text(f"📊 Active Chats: {active}\n🕒 In Queue: {queue}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("ℹ️ Use /start to enter queue\n/end to leave chat")


# --- Run Application without asyncio.run() ---
def run():
    import platform
    from telegram.ext import ApplicationBuilder

    bot = LiveChatBot()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("end", bot.end_chat))
    app.add_handler(CommandHandler("admin", bot.admin_command))
    app.add_handler(CommandHandler("stats", bot.stats_command))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    print("✅ Live Chat Bot is running...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        loop.run_until_complete(app.run_polling(allowed_updates=Update.ALL_TYPES))
    except KeyboardInterrupt:
        print("🛑 Bot stopped.")
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    run()