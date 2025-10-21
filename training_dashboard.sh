#!/bin/bash
# Информационная панель обучения (live dashboard)

PROJECT_DIR="/srv/MiniChessVovka"
PROGRESS_FILE="$PROJECT_DIR/training_progress.txt"
LOG_FILE="$PROJECT_DIR/training_log.txt"
PID_FILE="$PROJECT_DIR/training.pid"

while true; do
    clear
    
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║           Mini Chess AI - Live Training Dashboard              ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Статус процесса
    echo "📊 STATUS:"
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            printf "  ✓ Running (PID: %d)\n" $pid
            cpu=$(ps -p $pid -o %cpu= | tr -d ' ')
            mem=$(ps -p $pid -o %mem= | tr -d ' ')
            printf "  CPU: %s%% | MEM: %s%%\n" "$cpu" "$mem"
        else
            echo "  ✗ Process stopped"
        fi
    else
        echo "  ⚠ Not running"
    fi
    
    echo ""
    echo "📈 PROGRESS:"
    
    # Прогресс
    if [ -f "$PROGRESS_FILE" ]; then
        cat "$PROGRESS_FILE" | head -20
    else
        echo "  No progress file yet"
    fi
    
    echo ""
    echo "📝 LATEST EVENTS:"
    if [ -f "$LOG_FILE" ]; then
        tail -n 10 "$LOG_FILE" | sed 's/^/  /'
    fi
    
    echo ""
    echo "⏱️  Last update: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Press Ctrl+C to exit, refreshing in 10 seconds..."
    echo ""
    
    sleep 10
done
