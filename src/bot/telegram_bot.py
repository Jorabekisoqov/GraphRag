import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.core.orchestrator import process_query
from src.bot.rate_limiter import rate_limiter
from src.api.health import get_health_status
from src.core.logging_config import setup_logging, get_logger

load_dotenv()

# Setup structured logging
setup_logging(log_level="INFO", json_logs=False)
logger = get_logger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Hello! I'm your GraphRAG bot. Ask me anything about the data."
    )

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command."""
    health_status = get_health_status()
    
    status_text = f"System Status: {health_status['status'].upper()}\n\n"
    status_text += f"Neo4j: {'✓' if health_status['neo4j']['healthy'] else '✗'} {health_status['neo4j']['message']}\n"
    status_text += f"OpenAI: {'✓' if health_status['openai']['healthy'] else '✗'} {health_status['openai']['message']}"
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=status_text
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages with rate limiting."""
    user_id = update.effective_user.id
    user_text = update.message.text
    
    # Check rate limit
    is_allowed, rate_limit_message = rate_limiter.is_allowed(user_id)
    if not is_allowed:
        logger.warning("rate_limit_exceeded", user_id=user_id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=rate_limit_message
        )
        return
    
    # Run synchronous process_query in a thread pool to avoid blocking the event loop
    try:
        response = await asyncio.to_thread(process_query, user_text)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=str(response))
        logger.info("message_processed", user_id=user_id)
    except Exception as e:
        logger.error("message_processing_error", user_id=user_id, error=str(e), exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I encountered an error processing your message. Please try again."
        )

if __name__ == '__main__':
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token":
        print("Error: TELEGRAM_BOT_TOKEN not found or not set in environment variables.")
        exit(1)
        
    application = ApplicationBuilder().token(token).build()
    
    start_handler = CommandHandler('start', start)
    health_handler = CommandHandler('health', health)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(health_handler)
    application.add_handler(message_handler)
    
    print("Bot is polling...")
    application.run_polling()
