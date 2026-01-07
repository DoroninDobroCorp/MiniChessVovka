#!/bin/bash
# Информационная панель обучения (live dashboard)

PROJHEALTH_FILE="/srv/MiniChessVovka/training.health"
PID_FILE="/srv/MiniChessVovka/training.pid"
LOG_FILE="/srv/MiniChessVovka/training_log.txt"
PROGRESS_FILE="/srv/MiniChessVovka/training_progress.txt" # Kept as it's used later
SCRIPT_PATH="/srv/MiniChessVovka/src/scheduled_self_play.py"

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if current time is in AI training window (2 AM - 10 AM UTC)
is_training_time() {
    current_hour=$(date -u +%H | sed 's/^0*//')
    [ -z "$current_hour" ] && current_hour=0
    [ "$current_hour" -ge 2 ] && [ "$current_hour" -lt 10 ]
}

# Function to get next availability window
get_next_availability() {
    current_hour=$(date -u +%H | sed 's/^0*//')
    [ -z "$current_hour" ] && current_hour=0
    
    if [ "$current_hour" -lt 2 ]; then
        echo "Available in $((2 - current_hour)) hours (at 02:00 UTC)"
    elif [ "$current_hour" -ge 10 ]; then
        echo "Available in $((24 - current_hour + 2)) hours (at 02:00 UTC tomorrow)"
    else
        echo "Available now until 10:00 UTC (in $((10 - current_hour)) hours)"
    fi
}

while true; do
    clear
    
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║           Mini Chess AI - Live Training Dashboard              ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Check process state
    pid=""
    health_status="unknown" # ok, inactive, no_file
    activity_seconds=999999
    
    if [ -f "$PID_FILE" ]; then
        current_pid=$(cat "$PID_FILE")
        if ps -p $current_pid > /dev/null 2>&1; then
            pid=$current_pid
            
            # Check activity via health file
            if [ -f "$PROJHEALTH_FILE" ]; then
                last_update=$(cat "$PROJHEALTH_FILE")
                current_time=$(date +%s)
                activity_seconds=$((current_time - last_update))
                
                if [ $activity_seconds -lt 600 ]; then
                    health_status="ok"
                else
                    health_status="inactive"
                fi
            else
                health_status="no_file"
            fi
        fi
    fi
    
    # Determine overall health status
    # Логика статуса:
    # 02:00 - 10:00 UTC: Должен работать (PID есть + Health свежий) -> OK, иначе ERROR
    # 10:00 - 02:00 UTC: Должен отдыхать (PID нет) -> OK, иначе WARNING (или ERROR если работает)
    
    status_color=""
    status_text=""
    
    if is_training_time; then
        # НОЧЬ (Рабочее время)
        if [ -n "$pid" ] && [ "$health_status" == "ok" ]; then
             status_color=$GREEN
             status_text="АКТИВЕН (ОБУЧЕНИЕ)"
        elif [ -n "$pid" ]; then
             status_color=$YELLOW
             status_text="ЗАВИС?"
        else
             status_color=$RED
             status_text="ОСТАНОВЛЕН (ОШИБКА)"
        fi
    else
        # ДЕНЬ (Время отдыха)
        if [ -z "$pid" ]; then
             status_color=$GREEN
             status_text="ОЖИДАНИЕ (ОТДЫХ)"
        else
             status_color=$YELLOW
             status_text="РАБОТАЕТ ВНЕ ГРАФИКА"
        fi
    fi
    
    # Display overall health status
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    OVERALL HEALTH STATUS                       ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "  ${status_color}${status_text}${NC}"
    echo ""
    
    # Time window information
    echo "🕐 TIME WINDOW:"
    current_time_utc=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
    echo "  Current Time: $current_time_utc"
    echo "  Working Hours: 02:00-10:00 UTC (8-hour window)"
    
    if [ "$in_training_time" = true ]; then
        echo "  Within working hours - AI should be active"
        echo "  $(get_next_availability)"
    else
        echo "  Outside working hours - AI should be stopped"
        echo "  $(get_next_availability)"
    fi
    echo ""
    
    # Статус процесса
    echo "📊 PROCESS STATUS:"
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            printf "  ✓ Running (PID: %d)\n" $pid
            cpu=$(ps -p $pid -o %cpu= | tr -d ' ')
            mem=$(ps -p $pid -o %mem= | tr -d ' ')
            printf "  CPU: %s%% | MEM: %s%%\n" "$cpu" "$mem"
            
            # Show activity status
            if [ "$process_active" = true ]; then
                printf "  ✓ Active (last update: %ds ago)\n" $activity_seconds
            else
                printf "  ✗ Inactive (last update: %ds ago - exceeds 10 min threshold)\n" $activity_seconds
            fi
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
