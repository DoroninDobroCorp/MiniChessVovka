#!/bin/bash
# Stop the MiniChess bot

PID=$(pgrep -f "play_online.py --auto" | head -1)
if [ -z "$PID" ]; then
    echo "ℹ️  Bot is not running"
else
    kill "$PID"
    echo "🛑 Bot stopped (PID $PID)"
fi

# Stop monitor too
MPID=$(pgrep -f "monitor_bot.sh" | head -1)
if [ -n "$MPID" ]; then
    kill "$MPID"
    echo "🛑 Monitor stopped (PID $MPID)"
fi

# Show cache stats
cd "$(dirname "$0")"
python3 -c "
import sqlite3
c = sqlite3.connect('move_cache.db').cursor()
c.execute('SELECT COUNT(*) FROM move_cache')
print(f'💾 Cache: {c.fetchone()[0]} entries')
" 2>/dev/null
