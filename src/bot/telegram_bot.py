import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.core.orchestrator import process_query

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm your GraphRAG bot. Ask me anything about the data.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # Check if process_query is async or sync. In previous step it was sync.
    # To avoid blocking the bot loop, we should ideally run it in run_in_executor if it's blocking/long-running.
    # For now, strict simplicity: just call it.
    response = process_query(user_text)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=str(response))

if __name__ == '__main__':
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token":
        print("Error: TELEGRAM_BOT_TOKEN not found or not set in environment variables.")
        exit(1)
        
    application = ApplicationBuilder().token(token).build()
    
    start_handler = CommandHandler('start', start)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(message_handler)
    
    print("Bot is polling...")
    application.run_polling()
