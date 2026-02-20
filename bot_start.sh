#!/bin/bash
# Start the MiniChess bot (minihouse on chess.com)
# Usage: ./bot_start.sh [casual|rated]

cd "$(dirname "$0")"
MODE="${1:-casual}"
PYTHON="/Users/vladimirdoronin/VovkaNowEngineer/research-automation/venv/bin/python"
LOG="/tmp/minichess_bot.log"

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
