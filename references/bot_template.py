#!/usr/bin/env python3
"""
Telegram bot that interfaces with Claude Code CLI.

Usage:
    1. Copy this file to your project directory as bot.py
    2. Create .env file with:
       TELEGRAM_BOT_TOKEN=your_token
       AUTHORIZED_USER_ID=your_user_id
    3. pip install -r requirements.txt
    4. python bot.py
"""

import os
import re
import json
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

# Session storage: {chat_id: session_id}
sessions = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Hello! I'm a Claude Code interface.\n\n"
        "Send me any message and I'll forward it to Claude Code.\n\n"
        "Commands:\n"
        "/new — Start a fresh session\n"
        "/cancel — Stop the current generation\n"
        "/help — Show this message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "📚 Claude Code Telegram Bot\n\n"
        "Commands:\n"
        "/new — Start a fresh Claude session\n"
        "/cancel — Stop the current generation\n"
        "/help — Show this message\n\n"
        "Just send a message to chat with Claude!"
    )


async def new_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command — start a fresh session."""
    if update.effective_user.id != AUTHORIZED_USER_ID:
        logger.warning(f"Unauthorized /new from user {update.effective_user.id}")
        return

    chat_id = update.effective_chat.id
    if chat_id in sessions:
        del sessions[chat_id]
        await update.message.reply_text("✨ Fresh session started!")
    else:
        await update.message.reply_text("✨ Next message will start a fresh session.")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command — kill running process."""
    if update.effective_user.id != AUTHORIZED_USER_ID:
        logger.warning(f"Unauthorized /cancel from user {update.effective_user.id}")
        return

    chat_id = update.effective_chat.id

    # Store a cancel flag in context.user_data
    if not hasattr(context.user_data, 'cancel_requested'):
        context.user_data['cancel_requested'] = False

    context.user_data['cancel_requested'] = True
    await update.message.reply_text("⏹️ Cancellation requested (will stop next generation).")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages from authorized user."""
    # Authorization check
    if update.effective_user.id != AUTHORIZED_USER_ID:
        logger.warning(f"Unauthorized message from user {update.effective_user.id}")
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return

    message_text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Build the claude command
        cmd = ["claude", "-p", message_text]

        # Add session resumption if we have a stored session
        if chat_id in sessions:
            session_id = sessions[chat_id]
            cmd.extend(["--resume", session_id])

        # Add streaming options
        cmd.extend(["--output-format", "stream-json", "--include-partial-messages"])

        # CRITICAL: Remove CLAUDECODE env var to avoid nested call issues
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        logger.info(f"Running command: {' '.join(cmd)}")

        # Start the subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        response_text = ""
        sent_message = None
        chunk_buffer = ""
        chunks_sent = 0
        current_session_id = None

        # Read and process stream-json output
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            # Check if cancellation was requested
            if context.user_data.get('cancel_requested', False):
                process.kill()
                await process.wait()
                context.user_data['cancel_requested'] = False
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⏹️ Generation cancelled."
                )
                return

            try:
                event = json.loads(line.decode("utf-8"))
                event_type = event.get("type")

                if event_type == "message":
                    # Stream message content
                    content = event.get("content", "")
                    response_text += content
                    chunk_buffer += content

                    # Send or update message every 500 characters (simple approach)
                    if len(chunk_buffer) > 500:
                        chunks_sent += 1
                        if sent_message is None:
                            # First batch: send new message
                            try:
                                sent_message = await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=response_text,
                                )
                            except Exception as e:
                                logger.error(f"Error sending message: {e}")
                        else:
                            # Subsequent batches: edit message (optional)
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=sent_message.message_id,
                                    text=response_text,
                                )
                            except Exception as e:
                                # Editing can fail if text is too large for one message
                                logger.warning(f"Could not edit message: {e}")
                        chunk_buffer = ""

                elif event_type == "result":
                    # Extract session ID from result event
                    current_session_id = event.get("session_id")
                    if current_session_id:
                        sessions[chat_id] = current_session_id
                        logger.info(f"Stored session {current_session_id} for chat {chat_id}")

            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON: {line}")
                continue

        # Wait for process to complete
        await process.wait()

        # Send final message if not already sent
        if response_text:
            if sent_message is None:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=response_text,
                    )
                except Exception as e:
                    logger.error(f"Error sending final message: {e}")
            else:
                # Update with final content
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=sent_message.message_id,
                        text=response_text,
                    )
                except Exception as e:
                    logger.warning(f"Could not update final message: {e}")
        else:
            # Check stderr for errors
            stderr_data = await process.stderr.read()
            if stderr_data:
                error_msg = stderr_data.decode("utf-8", errors="ignore")
                logger.error(f"Claude error: {error_msg}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Error from Claude:\n{error_msg[:200]}",
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ No response from Claude.",
                )

    except FileNotFoundError:
        logger.error("Claude CLI not found")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Claude CLI not found. Is it installed and in PATH?",
        )
    except asyncio.TimeoutError:
        logger.error("Request timed out")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⏱️ Request timed out. Try a shorter prompt.",
        )
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Unexpected error: {str(e)[:100]}",
        )


def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set in .env file")
        exit(1)
    if AUTHORIZED_USER_ID == 0:
        print("❌ Error: AUTHORIZED_USER_ID not set in .env file")
        exit(1)

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_session))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Run the bot
    logger.info("Starting bot...")
    print("🤖 Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
