---
name: telegram-bot-skill
description: Build a Telegram bot that interfaces with Claude Code CLI, enabling headless Claude conversations with session continuity
---

# Telegram ↔ Claude Code Skill

Use this skill when the user wants to:
- Build a Telegram bot that forwards messages to Claude Code CLI (`claude -p`)
- Set up a personal Telegram interface for Claude conversations
- Bridge Telegram chat to Claude with session memory
- Deploy a Claude chatbot accessible via Telegram

## Pre-flight Checklist

Before starting, ensure you have:

- **Telegram Bot Token**: Obtain from @BotFather on Telegram (via `/newbot` command)
- **Your Telegram User ID**: Get from @userinfobot or with `/start` on any bot that echoes IDs
- **Claude CLI installed**: `claude --version` should work
- **Claude CLI authenticated**: `claude auth login` completed
- **Python 3.9+**: Required for python-telegram-bot library
- **pip**: Python package manager

## Project Structure

Create the following directory layout (or use the templates provided):

```
telegram-bot/
├── bot.py                    # Main bot file (copy from references/bot_template.py)
├── .env                      # Environment variables (create locally, don't commit)
├── requirements.txt          # Python dependencies
└── .gitignore               # Ignore .env and __pycache__
```

## Step-by-Step Implementation

### 1. Create `requirements.txt`

```
python-telegram-bot==21.8
python-dotenv==1.0.1
```

### 2. Create `.env` (locally only, never commit)

```
TELEGRAM_BOT_TOKEN=your_token_here
AUTHORIZED_USER_ID=your_telegram_user_id
```

### 3. Create `bot.py`

Copy the complete bot template from `references/bot_template.py` into your project.

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Bot

```bash
python bot.py
```

The bot will start polling for messages. Send it a message on Telegram—it will forward to Claude Code CLI and stream the response back.

---

## How It Works

### Message Flow

1. **User sends message** to Telegram bot
2. **Authorization check**: Only messages from `AUTHORIZED_USER_ID` are processed
3. **Session lookup**: Bot checks if this chat has an active session ID
   - **First message**: No `--resume`, Claude Code creates a new session
   - **Subsequent messages**: Uses `--resume <session_id>` to continue context
4. **Execute Claude Code**: `claude -p "<message>"` runs as subprocess
5. **Stream response**: Parse `stream-json` output, send chunks back to Telegram
6. **Extract session ID**: From the `result` event in the stream, save for next message

### Session Management

Sessions are stored as a dictionary in memory: `{chat_id: session_id}`

- **`/new` command**: Clears the session ID, next message starts fresh
- **`/cancel` command**: Kills the running `claude` subprocess (if supported by your OS)
- **Session persistence**: Sessions are stored as `.jsonl` files in Claude's cache by default

### Key Technical Details

#### Removing CLAUDECODE env var

When calling `claude -p` from inside Claude Code (nested calls), **you must remove the `CLAUDECODE` environment variable** from the subprocess environment:

```python
env = os.environ.copy()
env.pop('CLAUDECODE', None)
result = subprocess.run(['claude', '-p', message], env=env, ...)
```

Failure to do this will cause the nested Claude subprocess to fail.

#### Stream-JSON Output Format

Use `--output-format stream-json --include-partial-messages` to enable streaming:

```bash
claude -p "message" --output-format stream-json --include-partial-messages
```

This outputs NDJSON (newline-delimited JSON). Each line is an event:

- `type: "message"` — Text chunk from Claude (stream this to Telegram)
- `type: "result"` — Final result, contains `session_id` field

Example:

```json
{"type": "message", "content": "Hello"}
{"type": "result", "session_id": "abc123", ...}
```

#### Resuming Sessions

To continue a conversation:

```bash
claude -p "follow-up message" --resume abc123
```

The session ID persists in Claude's local cache. You can resume the same session across multiple calls.

### Streaming to Telegram

**Option 1: Batch responses** (simple)
- Collect all output from Claude
- Send as one Telegram message

**Option 2: Stream with message edits** (better UX)
- Send an initial "typing..." message with ID `msg_id`
- Collect chunks from stream
- Every N characters, `edit_message_text()` to update the same message
- Final message is the complete response

Both approaches are shown in `bot_template.py`.

---

## Error Handling

### Claude not found
If `claude` command fails or is not installed:
```python
except FileNotFoundError:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="❌ Claude CLI not found. Is it installed and in PATH?"
    )
```

### Timeout
Long-running Claude sessions may timeout. Wrap execution:
```python
try:
    result = subprocess.run(
        [...],
        timeout=300,  # 5 minutes
        capture_output=True,
        text=True
    )
except subprocess.TimeoutExpired:
    await context.bot.send_message(chat_id=..., text="⏱️ Request timed out")
```

### Subprocess errors
- Check `stderr` from Claude CLI output
- Log errors for debugging
- Return user-friendly messages to Telegram

---

## Commands

Implement these commands by handling in your message handler:

- **`/new`** — Start a fresh Claude session (clears stored session ID)
- **`/cancel`** — Stop the current generation (kills subprocess on Unix-like systems)
- **`/help`** — Show available commands

---

## Running the Bot

### Local Development
```bash
python bot.py
```

The bot will run in the foreground, logging to stdout.

### Keeping It Alive
For a persistent bot, use one of:

- **tmux**: `tmux new-session -d -s claude-bot python bot.py`
- **screen**: `screen -S claude-bot -dm python bot.py`
- **systemd** (Linux): Create a service file (see `setup_guide.md`)
- **Docker**: Containerize with a `Dockerfile`

See `references/setup_guide.md` for detailed instructions.

---

## Troubleshooting

### "CLAUDECODE not found" when running claude subprocess
- Ensure you remove `CLAUDECODE` from subprocess env (see above)

### Session ID not persisting across messages
- Check that `--output-format stream-json` is being used
- Verify the `result` event is being parsed correctly
- Ensure session dict is updated after each call

### Telegram messages not sending
- Check bot token is correct in `.env`
- Verify authorized user ID is correct
- Check internet connectivity

### Claude subprocess hangs
- Add a timeout (default 5 minutes recommended)
- Implement `/cancel` to kill hanging processes

### Memory issues with long conversations
- Claude's `.jsonl` session files grow with context
- Consider periodically calling `/new` to reset
- Monitor disk usage if bot runs 24/7

---

## Next Steps

1. Copy `bot_template.py` to your project as `bot.py`
2. Set up `.env` with your token and user ID
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python bot.py`
5. Send a test message in Telegram
6. Deploy to a server or keep running locally in tmux/screen

See `references/setup_guide.md` for detailed setup steps and deployment options.
