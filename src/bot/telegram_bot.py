import os
import re
import asyncio
import tempfile
import uuid
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from src.core.orchestrator import process_query
from src.bot.rate_limiter import rate_limiter
from src.api.health import get_health_status
from src.core.logging_config import setup_logging, get_logger
from src.data.document_utils import read_file, chunk_text
from src.data.ingest_single import ingest_single_document

load_dotenv()

# Setup structured logging
setup_logging(log_level="INFO", json_logs=False)
logger = get_logger(__name__)

MAX_FILE_SIZE_MB = 10
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx"}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello! I'm your GraphRAG bot. Ask me anything about the data. You can also send PDF, DOC, DOCX, or TXT files to add them to the knowledge base.",
    )

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command."""
    health_status = get_health_status()
    
    status_text = f"System Status: {health_status['status'].upper()}\n\n"
    status_text += f"Neo4j: {'✓' if health_status['neo4j']['healthy'] else '✗'} {health_status['neo4j']['message']}\n"
    status_text += f"DeepSeek: {'✓' if health_status['openai']['healthy'] else '✗'} {health_status['openai']['message']}"
    
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
        text = str(response)
        # Convert markdown bold **text** to HTML <b>text</b> for Telegram
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Escape HTML entities so parse_mode works safely
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Restore intentional <b>/<i> tags
        text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            parse_mode="HTML",
        )
        logger.info("message_processed", user_id=user_id)
    except Exception as e:
        logger.error("message_processing_error", user_id=user_id, error=str(e), exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I encountered an error processing your message. Please try again."
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads: extract text, chunk, ingest into Neo4j."""
    user_id = update.effective_user.id
    document = update.message.document

    if not document:
        return

    # Rate limit
    is_allowed, rate_limit_message = rate_limiter.is_allowed(user_id)
    if not is_allowed:
        logger.warning("rate_limit_exceeded", user_id=user_id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=rate_limit_message,
        )
        return

    # File size limit (10 MB)
    if document.file_size and document.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"File too large. Maximum size is {MAX_FILE_SIZE_MB} MB.",
        )
        return

    file_name = document.file_name or "document"
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Unsupported format. Please send PDF, TXT, DOC, or DOCX.",
        )
        return

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Processing your file...",
    )

    try:
        file = await context.bot.get_file(document.file_id)
        suffix = ext or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        def _process():
            text = read_file(tmp_path)
            if not text or len(text.strip()) < 50:
                raise ValueError("Could not extract meaningful text from the file.")
            basename = f"upload_{uuid.uuid4().hex[:8]}"
            graph_data = chunk_text(text, max_chunk_size=800, chunk_overlap=150)
            metadata = {
                "file_name": f"{basename}.json",
                "document_title": file_name,
                "authority": "O'zbekiston Respublikasi",
            }
            ingest_single_document(metadata, graph_data)
            return len(graph_data)

        try:
            chunks_count = await asyncio.to_thread(_process)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"File added successfully ({chunks_count} chunks). You can now ask questions about it.",
        )
        logger.info("document_ingested", user_id=user_id, file_name=file_name, chunks=chunks_count)

    except ImportError as e:
        logger.error("document_import_error", error=str(e))
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Missing dependency for this file type. Contact administrator.",
        )
    except ValueError as e:
        logger.warning("document_processing_error", error=str(e))
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=str(e),
        )
    except Exception as e:
        logger.error("document_processing_error", user_id=user_id, error=str(e), exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, I could not process this file. Please try again or use a different format.",
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
    document_handler = MessageHandler(filters.Document.ALL, handle_document)

    application.add_handler(start_handler)
    application.add_handler(health_handler)
    application.add_handler(message_handler)
    application.add_handler(document_handler)
    
    print("Bot is polling...")
    application.run_polling()
