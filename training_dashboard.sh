#!/bin/bash
# Информационная панель обучения (live dashboard)

PROJECT_DIR="/srv/MiniChessVovka"
PROGRESS_FILE="$PROJECT_DIR/training_progress.txt"
LOG_FILE="$PROJECT_DIR/training_log.txt"
PID_FILE="$PROJECT_DIR/training.pid"

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
    process_running=false
    process_active=false
    activity_seconds=999999
    
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            process_running=true
            
            # Check activity via health file
            if [ -f "$PROJECT_DIR/training.health" ]; then
                last_update=$(cat "$PROJECT_DIR/training.health")
                current_time=$(date +%s)
                activity_seconds=$((current_time - last_update))
                
                if [ $activity_seconds -lt 600 ]; then
                    process_active=true
                fi
            fi
        fi
    else
        # Check for any running scheduled_self_play.py processes
        if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
            process_running=true
        fi
    fi
    
    # Determine overall health status
    in_training_time=false
    if is_training_time; then
        in_training_time=true
    fi
    
    status_icon=""
    status_text=""
    
    if [ "$in_training_time" = true ]; then
        # DURING working hours (2-10 AM UTC)
        if [ "$process_running" = true ] && [ "$process_active" = true ]; then
            # GREEN: Process running and active during working hours
            status_icon="✓"
            status_text="HEALTHY - Process active during working hours"
        else
            # RED: Process not running or inactive during working hours
            status_icon="✗"
            if [ "$process_running" = false ]; then
                status_text="PROBLEM - Process should be running during working hours"
            else
                status_text="PROBLEM - Process inactive for ${activity_seconds}s (>10 min)"
            fi
        fi
    else
        # OUTSIDE working hours (not 2-10 AM UTC)
        if [ "$process_running" = false ]; then
            # GREEN: Process correctly stopped outside working hours
            status_icon="✓"
            status_text="HEALTHY - Process correctly stopped outside working hours"
        else
            # RED: Process running when it shouldn't be
            status_icon="✗"
            status_text="PROBLEM - Process running outside working hours"
        fi
    fi
    
    # Display overall health status
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    OVERALL HEALTH STATUS                       ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  ${status_icon} ${status_text}"
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
