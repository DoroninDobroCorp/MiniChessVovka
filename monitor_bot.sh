#!/bin/bash
# Monitor MiniChess bot — checks every 60 seconds that moves are being made/calculated.
# Usage: ./monitor_bot.sh

cd "$(dirname "$0")"

HEARTBEAT_FILE=".bot_heartbeat"
LOG="/tmp/minichess_bot.log"
MAX_STALE=300  # 5 minutes without heartbeat = problem

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

check_bot() {
    local now
    now=$(date +%s)

    # 1. Check process
    PID=$(pgrep -f "play_online.py" | head -1)
    if [ -z "$PID" ]; then
        echo -e "$(date '+%H:%M:%S') ${RED}✗ Bot NOT running${NC}"
        return
    fi

    # 2. Check heartbeat file
    if [ ! -f "$HEARTBEAT_FILE" ]; then
        echo -e "$(date '+%H:%M:%S') ${YELLOW}⚠ Bot running (PID $PID) but no heartbeat file yet${NC}"
        return
    fi

    IFS='|' read -r ts status extra < "$HEARTBEAT_FILE"
    local age=$(( now - ts ))

    if [ "$age" -gt "$MAX_STALE" ]; then
        echo -e "$(date '+%H:%M:%S') ${RED}✗ STALE! PID=$PID status=$status last_heartbeat=${age}s ago ($extra)${NC}"
    else
        echo -e "$(date '+%H:%M:%S') ${GREEN}✓${NC} PID=$PID ${CYAN}$status${NC} ${age}s ago ${extra}"
    fi

    # 3. Show last log line
    if [ -f "$LOG" ]; then
        last_line=$(tail -1 "$LOG" 2>/dev/null | tr -s ' ' | cut -c1-100)
        if [ -n "$last_line" ]; then
            echo -e "         log: $last_line"
        fi
    fi
}

echo "🔍 MiniChess Bot Monitor (checking every 60s, Ctrl+C to stop)"
echo "─────────────────────────────────────────────────────────────"

while true; do
    check_bot
    sleep 60
done
