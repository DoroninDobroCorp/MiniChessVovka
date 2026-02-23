#!/bin/bash
# Stop the MiniChess bot and all its child processes

# Kill all play_online.py processes (main + any spawned copies)
PIDS=$(pgrep -f "play_online.py" 2>/dev/null)
if [ -z "$PIDS" ]; then
    echo "ℹ️  Bot is not running"
else
    for PID in $PIDS; do
        # Kill entire process group (catches playwright, browsers, etc.)
        PGID=$(ps -o pgid= -p "$PID" 2>/dev/null | tr -d ' ')
        if [ -n "$PGID" ] && [ "$PGID" != "0" ]; then
            kill -- -"$PGID" 2>/dev/null
        fi
        kill "$PID" 2>/dev/null
    done
    echo "🛑 Bot stopped (PIDs: $PIDS)"

    # Wait up to 5 seconds for processes to actually die
    for i in $(seq 1 5); do
        REMAINING=$(pgrep -f "play_online.py" 2>/dev/null)
        if [ -z "$REMAINING" ]; then
            break
        fi
        sleep 1
    done

    # Force kill if still alive
    REMAINING=$(pgrep -f "play_online.py" 2>/dev/null)
    if [ -n "$REMAINING" ]; then
        for PID in $REMAINING; do
            kill -9 "$PID" 2>/dev/null
        done
        echo "⚡ Force-killed remaining processes"
    fi
fi

# Stop monitor too
MPID=$(pgrep -f "monitor_bot.sh" 2>/dev/null)
if [ -n "$MPID" ]; then
    for PID in $MPID; do
        kill "$PID" 2>/dev/null
    done
    echo "🛑 Monitor stopped"
fi

# Show cache stats
cd "$(dirname "$0")"
python3 -c "
import sqlite3
c = sqlite3.connect('move_cache.db').cursor()
c.execute('SELECT COUNT(*) FROM move_cache')
print(f'💾 Cache: {c.fetchone()[0]} entries')
" 2>/dev/null
