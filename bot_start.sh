#!/bin/bash
# Start the MiniChess bot (minihouse on chess.com)
# Usage: ./bot_start.sh [casual|rated]

cd "$(dirname "$0")"
MODE="${1:-casual}"

# Auto-detect Python (prefer venv, fallback to system python3)
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f "../research-automation/venv/bin/python" ]; then
    PYTHON="../research-automation/venv/bin/python"
else
    PYTHON="python3"
fi

LOG="/tmp/minichess_bot.log"

# Check dependencies
if ! $PYTHON -c "import playwright" 2>/dev/null; then
    echo "❌ Missing dependencies. Install first:"
    echo "   pip install -r requirements.txt"
    echo "   python -m playwright install chromium"
    exit 1
fi

# Check credentials
if [ ! -f ".env" ] && [ -z "$CHESS_COM_EMAIL" ]; then
    echo "❌ No credentials found!"
    echo "   1. Copy .env.example to .env"
    echo "   2. Edit .env and add your chess.com email/password"
    echo "   OR set CHESS_COM_EMAIL and CHESS_COM_PASSWORD environment variables"
    exit 1
fi

# Check if already running
PID=$(pgrep -f "play_online.py --auto" | head -1)
if [ -n "$PID" ]; then
    echo "⚠️  Bot already running (PID $PID)"
    echo "   Use ./bot_stop.sh first"
    exit 1
fi

# Set rated mode in play_online.py
if [ "$MODE" = "rated" ]; then
    sed -i '' 's/create_minihouse_game(page, rated=False)/create_minihouse_game(page, rated=True)/' play_online.py
    echo "🏆 Mode: RATED"
else
    sed -i '' 's/create_minihouse_game(page, rated=True)/create_minihouse_game(page, rated=False)/' play_online.py
    echo "🎮 Mode: CASUAL"
fi

# Launch bot
PYTHONUNBUFFERED=1 $PYTHON play_online.py --auto > "$LOG" 2>&1 &
BOT_PID=$!
echo "✅ Bot started (PID $BOT_PID)"
echo "📄 Logs: tail -f $LOG"
