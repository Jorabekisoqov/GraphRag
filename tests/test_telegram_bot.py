"""Tests for telegram_bot module."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from telegram import Update, Message, Chat, User
from telegram.ext import ContextTypes
from src.bot.telegram_bot import start, handle_message


@pytest.fixture
def mock_update():
    """Create a mock Telegram update."""
    update = Mock(spec=Update)
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 12345
    update.message = Mock(spec=Message)
    update.message.text = "test query"
    return update


@pytest.fixture
def mock_context():
    """Create a mock Telegram context."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context):
    """Test /start command handler."""
    await start(mock_update, mock_context)
    mock_context.bot.send_message.assert_called_once()
    call_args = mock_context.bot.send_message.call_args
    assert call_args[1]['chat_id'] == 12345
    assert "GraphRAG" in call_args[1]['text'].lower() or "hello" in call_args[1]['text'].lower()


@pytest.mark.asyncio
@patch('src.bot.telegram_bot.process_query')
async def test_handle_message_success(mock_process_query, mock_update, mock_context):
    """Test successful message handling."""
    mock_process_query.return_value = "Test response"
    
    await handle_message(mock_update, mock_context)
    
    mock_process_query.assert_called_once_with("test query")
    mock_context.bot.send_message.assert_called_once()
    call_args = mock_context.bot.send_message.call_args
    assert call_args[1]['text'] == "Test response"


@pytest.mark.asyncio
@patch('src.bot.telegram_bot.process_query')
async def test_handle_message_error(mock_process_query, mock_update, mock_context):
    """Test error handling in message processing."""
    mock_process_query.side_effect = Exception("Test error")
    
    # Should not raise exception, but handle gracefully
    try:
        await handle_message(mock_update, mock_context)
    except Exception:
        pytest.fail("handle_message should handle errors gracefully")
