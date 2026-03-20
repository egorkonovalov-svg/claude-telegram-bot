# Setup Guide: Telegram Claude Code Bot

Complete step-by-step instructions for getting your Telegram Claude Code bot running.

---

## 1. Get Your Telegram Bot Token

### Via @BotFather (Official Method)

1. Open Telegram and search for **@BotFather**
2. Start a chat and send `/newbot`
3. Follow prompts:
   - Choose a name (e.g., "My Claude Bot")
   - Choose a username (e.g., "my_claude_bot") — must be unique and end with "bot"
4. BotFather will send you a token that looks like:
   ```
   123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh
   ```
5. **Save this token** — you'll need it for `.env`

---

## 2. Find Your Telegram User ID

### Option A: Using @userinfobot (Easiest)

1. Open Telegram and search for **@userinfobot**
2. Start a chat and send `/start`
3. It will reply with your user ID (a number like `123456789`)
4. **Save this ID** — you'll need it for `.env`

### Option B: Using Any Bot That Echoes IDs

1. Start a chat with any Telegram bot
2. Send `/start`
3. If the bot shows "Your ID is: 123456789", copy that number

### Option C: Get from a message in a group

If you send a message in a group where the bot is active, it logs the user ID.

---

## 3. Set Up Your Project Directory

Create a directory for your bot:

```bash
mkdir telegram-bot
cd telegram-bot
```

Create the required files:

### `requirements.txt`

```
python-telegram-bot==21.8
python-dotenv==1.0.1
```

### `.env` (Never commit this!)

```env
TELEGRAM_BOT_TOKEN=your_token_from_botfather
AUTHORIZED_USER_ID=your_user_id_from_userinfobot
```

**Important**: Add `.env` to `.gitignore` so it's never committed to git:

```bash
echo ".env" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

### `.gitignore`

```
.env
__pycache__/
*.pyc
*.pyo
venv/
.DS_Store
```

### `bot.py`

Copy the complete code from `bot_template.py` in the references folder.

---

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

If you're using a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 5. Test Locally

```bash
python bot.py
```

You should see:

```
2026-03-20 10:30:45,123 - telegram.ext._application - INFO - Application started
🤖 Bot is running. Press Ctrl+C to stop.
```

Now open Telegram and send a message to your bot. It should respond with Claude's output!

---

## 6. Keep the Bot Running 24/7

### Option A: tmux (Recommended for Development)

```bash
# Start a new session
tmux new-session -d -s claude-bot "cd /path/to/telegram-bot && python bot.py"

# View logs
tmux capture-pane -t claude-bot -p

# Stop
tmux kill-session -t claude-bot
```

### Option B: screen

```bash
# Start
screen -S claude-bot -dm bash -c "cd /path/to/telegram-bot && python bot.py"

# View logs
screen -x claude-bot

# Stop (inside screen)
Ctrl+A, then D to detach
screen -S claude-bot -X quit
```

### Option C: systemd (Linux)

Create `/etc/systemd/system/claude-bot.service`:

```ini
[Unit]
Description=Claude Code Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/telegram-bot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl enable claude-bot
sudo systemctl start claude-bot
sudo systemctl status claude-bot
```

View logs:

```bash
sudo journalctl -u claude-bot -f
```

### Option D: Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

CMD ["python", "bot.py"]
```

Build and run:

```bash
docker build -t claude-bot .
docker run -d --name claude-bot \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e AUTHORIZED_USER_ID="your_id" \
  claude-bot
```

---

## 7. Troubleshooting

### "CLAUDECODE not found" error

**Problem**: When the bot runs `claude -p`, you see an error about `CLAUDECODE`.

**Solution**: Ensure the bot is removing `CLAUDECODE` from the subprocess environment:

```python
env = os.environ.copy()
env.pop('CLAUDECODE', None)
process = subprocess.run([...], env=env)
```

This is already in `bot_template.py`.

### Claude command not found

**Problem**: `FileNotFoundError: [Errno 2] No such file or directory: 'claude'`

**Solutions**:
1. Ensure Claude CLI is installed: `claude --version`
2. Ensure Claude CLI is in your PATH:
   ```bash
   which claude
   ```
3. If running in a virtual environment, install Claude in that venv:
   ```bash
   pip install claude-code  # or however you install Claude
   ```
4. If Claude is in a non-standard location, use the full path in the bot:
   ```python
   cmd = ["/usr/local/bin/claude", "-p", message_text]
   ```

### Bot token rejected

**Problem**: `error: Unauthorized`

**Solution**:
1. Verify your token is copied correctly from BotFather (no spaces, full token)
2. Verify the token is in `.env` as `TELEGRAM_BOT_TOKEN=...`
3. Get a new token from BotFather with `/newbot` again

### "Not authorized to use this bot" message

**Problem**: You send a message but get rejected.

**Solution**:
1. Verify your Telegram user ID is correct in `.env`
2. Check it matches what @userinfobot showed
3. Restart the bot after changing `.env`

### Session ID not persisting

**Problem**: Each message starts a fresh conversation instead of continuing.

**Solution**:
1. Ensure `--output-format stream-json` is in the command
2. Verify the `result` event is being parsed:
   ```python
   current_session_id = event.get("session_id")
   sessions[chat_id] = current_session_id
   ```
3. Check logs for `Stored session...` message
4. Verify the session dict is being updated

### Long messages get truncated

**Problem**: Telegram limits messages to 4096 characters.

**Solution**: The bot should automatically handle this by splitting long responses. If not, add:

```python
if len(response_text) > 4000:
    # Send in chunks
    for i in range(0, len(response_text), 4000):
        await context.bot.send_message(
            chat_id=chat_id,
            text=response_text[i:i+4000]
        )
else:
    await context.bot.send_message(
        chat_id=chat_id,
        text=response_text
    )
```

### Bot hangs or times out

**Problem**: Bot doesn't respond to messages.

**Solution**:
1. Check if the bot process is still running:
   ```bash
   ps aux | grep bot.py
   ```
2. Check if Claude CLI itself is hanging:
   ```bash
   timeout 10 claude -p "test"
   ```
3. Increase the timeout in `bot.py`:
   ```python
   process = subprocess.run([...], timeout=600)  # 10 minutes
   ```
4. Check logs for errors

### Memory usage grows over time

**Problem**: Bot uses more and more memory.

**Solution**:
1. Claude's session files can grow large with context history
2. Periodically clear sessions by sending `/new`
3. Or implement automatic session rotation after N messages
4. Monitor with `du -sh ~/.claude/sessions/`

---

## 8. Development Tips

### Enable Debug Logging

Add at the top of `bot.py`:

```python
logging.basicConfig(level=logging.DEBUG)
```

This will show all Telegram API calls and subprocess output.

### Test Claude CLI Directly

Before debugging the bot, test Claude CLI works:

```bash
claude -p "hello" --output-format stream-json --include-partial-messages
```

You should get JSON output with `message` and `result` events.

### Monitor Session Files

Sessions are stored in `~/.claude/sessions/`. You can see active sessions:

```bash
ls -lah ~/.claude/sessions/
```

Each one is a `.jsonl` file containing your conversation history.

### Simulate User Message

If the bot isn't responding, simulate it locally:

```python
# Add this to bot.py temporarily
if __name__ == "__main__":
    asyncio.run(handle_message_test())

async def handle_message_test():
    class FakeUpdate:
        class FakeUser:
            id = AUTHORIZED_USER_ID
        class FakeChat:
            id = 123456
        class FakeMessage:
            text = "hello"
        effective_user = FakeUser()
        effective_chat = FakeChat()
        message = FakeMessage()

    class FakeContext:
        user_data = {}
        async def send_chat_action(self, **kwargs):
            pass
        class bot:
            @staticmethod
            async def send_message(**kwargs):
                print(f"Message: {kwargs}")

    await handle_message(FakeUpdate(), FakeContext())
```

---

## 9. Next Steps

- Test with various prompts to ensure session continuity works
- Set up monitoring/logging for long-running bot
- Consider rate limiting (Telegram API has limits)
- Add commands like `/status` to check session info
- Extend with multi-user support if desired

---

## Support

If you run into issues:

1. Check the logs (see troubleshooting above)
2. Verify `.env` is correctly set
3. Test `claude -p` directly in your terminal
4. Ensure your Telegram user ID is correct
5. Try `/new` to reset the session
