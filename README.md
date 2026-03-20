# telegram-claude

A Claude Code skill that builds a Telegram bot interface for Claude Code CLI — chat with Claude from your phone with full session continuity.

## What it does

This skill scaffolds a personal Telegram bot that bridges your messages directly to `claude -p`, streaming responses back in real time. Each conversation maintains context across messages via Claude's session system, so you can have long, coherent chats from Telegram just like you would in the terminal.

```
You (Telegram)
     │ message
     ▼
Telegram Bot (bot.py)
     │ subprocess: claude -p "..." --resume <session_id>
     ▼
Claude Code CLI
     │ stream-json (NDJSON)
     ▼
Telegram Bot (parses & streams chunks)
     │ send_message / edit_message_text
     ▼
You (Telegram)
```

## Prerequisites

Before starting, you need:

- **Telegram Bot Token** — create a bot via [@BotFather](https://t.me/BotFather) with `/newbot`
- **Your Telegram User ID** — get it from [@userinfobot](https://t.me/userinfobot)
- **Claude CLI installed and authenticated** — `claude --version` and `claude auth login`
- **Python 3.9+** and **pip**

## Installation

### 1. Create the project directory

```bash
mkdir telegram-bot && cd telegram-bot
```

### 2. Copy the bot template

```bash
cp /path/to/telegram-skill/references/bot_template.py bot.py
```

Or if you're using this as a Claude Code skill, just ask Claude to set it up — it will copy and configure everything for you.

### 3. Create `requirements.txt`

```
python-telegram-bot==21.8
python-dotenv==1.0.1
```

### 4. Create `.env`

```
TELEGRAM_BOT_TOKEN=your_token_here
AUTHORIZED_USER_ID=your_telegram_user_id
```

> Never commit `.env` to version control.

### 5. Create `.gitignore`

```
.env
__pycache__/
*.pyc
```

### 6. Install dependencies and run

```bash
pip install -r requirements.txt
python bot.py
```

Send a message to your bot on Telegram — it will forward to Claude and stream the response back.

## Configuration

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `AUTHORIZED_USER_ID` | Your Telegram numeric user ID — only this user can interact with the bot |

The bot rejects all messages from other users silently (logged as warnings).

## Usage

Once the bot is running, just send it any message. You can also use these commands:

| Command | Description |
|---|---|
| `/start` | Show welcome message and command list |
| `/help` | Show available commands |
| `/new` | Clear the current session and start fresh |
| `/cancel` | Stop the current generation |

### Example

```
You: explain how async/await works in Python

Bot: [streams response from Claude...]

You: give me a code example

Bot: [Claude remembers the previous context and continues...]

You: /new

Bot: ✨ Fresh session started!
```

## Session management

Sessions are stored in memory as `{chat_id: session_id}`. After each message, the bot extracts the `session_id` from Claude's output and passes it back on the next call via `--resume <session_id>`.

- Each Telegram chat has its own independent session
- Sessions persist in Claude's local cache (`~/.claude/sessions/`) as `.jsonl` files
- Use `/new` to reset and start a fresh context
- Long sessions accumulate disk usage — consider resetting periodically for 24/7 bots

## Deployment

### Development (tmux)

```bash
tmux new-session -d -s claude-bot "python bot.py"
# Attach to view logs:
tmux attach -t claude-bot
```

### Development (screen)

```bash
screen -S claude-bot -dm bash -c "python bot.py"
screen -r claude-bot
```

### Production (systemd, Linux)

Create `/etc/systemd/system/claude-bot.service`:

```ini
[Unit]
Description=Claude Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/telegram-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10
EnvironmentFile=/path/to/telegram-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable claude-bot
sudo systemctl start claude-bot
sudo systemctl status claude-bot
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY bot.py .
CMD ["python", "bot.py"]
```

```bash
docker build -t claude-bot .
docker run -d --env-file .env --name claude-bot claude-bot
```

## How it works

The bot runs `claude -p` as an async subprocess with `--output-format stream-json --include-partial-messages`, which produces NDJSON — one JSON event per line:

```json
{"type": "message", "content": "Hello, here is..."}
{"type": "result", "session_id": "abc123", ...}
```

The bot accumulates `message` events into a buffer, sending/editing a Telegram message every 500 characters for a live-streaming effect. When the `result` event arrives, it saves the `session_id` for the next call.

**Critical detail:** When the bot runs inside Claude Code (e.g. during skill setup), it must strip the `CLAUDECODE` environment variable before spawning the subprocess — otherwise the nested `claude` call fails:

```python
env = os.environ.copy()
env.pop("CLAUDECODE", None)
process = await asyncio.create_subprocess_exec(*cmd, env=env)
```

## Troubleshooting

**Bot doesn't respond to messages**
- Verify `AUTHORIZED_USER_ID` matches your actual Telegram numeric ID (not a username)
- Check the bot token is correct and the bot is started in Telegram

**`claude` command not found**
- Ensure Claude CLI is installed and on `PATH`: `which claude`
- If running as a service, you may need to specify the full path in the subprocess call

**Session ID not persisting**
- Confirm `--output-format stream-json` is in the command
- Check logs for JSON parse errors on the `result` event line

**Subprocess hangs**
- Add a timeout: `asyncio.wait_for(process.communicate(), timeout=300)`
- Use `/cancel` to kill the running process

**Messages truncated**
- Telegram has a 4096-character limit per message
- For long responses, the bot will need to split into multiple messages (not handled by default in the template — extend `handle_message` if needed)

**Running inside Claude Code (nested call fails)**
- Remove `CLAUDECODE` from the subprocess env as shown above

## Files

```
telegram-skill/
├── SKILL.md                     # Skill instructions for Claude Code
├── references/
│   ├── bot_template.py          # Complete bot implementation — copy to bot.py
│   └── setup_guide.md           # Detailed deployment guide
└── .claude/
    └── settings.local.json      # Skill permissions
```
