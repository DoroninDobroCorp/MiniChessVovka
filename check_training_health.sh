#!/bin/bash
# Скрипт проверки здоровья обучения

PROJECT_DIR="/srv/MiniChessVovka"
PID_FILE="$PROJECT_DIR/training.pid"
HEALTH_FILE="$PROJECT_DIR/training.health"
LOG_FILE="$PROJECT_DIR/training_log.txt"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

echo "================================"
echo "Проверка здоровья обучения Mini Chess"
echo "================================"
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
        if [ -f "$HEALTH_FILE" ]; then
            last_update=$(cat "$HEALTH_FILE")
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

status_color=""
status_icon=""
status_text=""

if [ "$in_training_time" = true ]; then
    # DURING working hours (2-10 AM UTC)
    if [ "$process_running" = true ] && [ "$process_active" = true ]; then
        # GREEN: Process running and active during working hours
        status_color="$GREEN"
        status_icon="✓"
        status_text="HEALTHY - Process active during working hours"
    else
        # RED: Process not running or inactive during working hours
        status_color="$RED"
        status_icon="✗"
        if [ "$process_running" = false ]; then
            status_text="PROBLEM - Process should be running during working hours"
        else
            status_text="PROBLEM - Process inactive for ${activity_seconds}s (>10 min threshold)"
        fi
    fi
else
    # OUTSIDE working hours (not 2-10 AM UTC)
    if [ "$process_running" = false ]; then
        # GREEN: Process correctly stopped outside working hours
        status_color="$GREEN"
        status_icon="✓"
        status_text="HEALTHY - Process correctly stopped outside working hours"
    else
        # RED: Process running when it shouldn't be
        status_color="$RED"
        status_icon="✗"
        status_text="PROBLEM - Process running outside working hours (2-10 AM UTC)"
    fi
fi

# Display overall health status
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    OVERALL HEALTH STATUS                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${status_color}${status_icon} ${status_text}${NC}"
echo ""

# Time window information
current_time_utc=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
echo "🕐 TIME WINDOW:"
echo "  Current Time: $current_time_utc"
echo "  Working Hours: 02:00-10:00 UTC (8-hour window)"
if [ "$in_training_time" = true ]; then
    echo -e "  ${BLUE}Within working hours - AI should be active${NC}"
    echo -e "  ${BLUE}$(get_next_availability)${NC}"
else
    echo -e "  ${YELLOW}Outside working hours - AI should be stopped${NC}"
    echo -e "  ${YELLOW}$(get_next_availability)${NC}"
fi
echo ""
echo "================================"
echo ""

# Detailed process information
echo "📊 PROCESS DETAILS:"
if [ ! -f "$PID_FILE" ]; then
    echo -e "  ${YELLOW}⚠ PID файл не найден${NC}"
    echo "  Обучение, вероятно, не запущено"
    echo ""
    
    # Проверяем, запущены ли процессы напрямую
    if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
        echo -e "  ${YELLOW}! Но найдены процессы scheduled_self_play.py:${NC}"
        pgrep -f "scheduled_self_play.py" | while read p; do
            ps -p $p -o pid,ppid,cmd,%cpu,%mem,etime=
        done
    fi
else
    pid=$(cat "$PID_FILE")
    echo "  PID из файла: $pid"
    
    # Проверяем, работает ли процесс
    if ps -p $pid > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Процесс работает${NC}"
        echo ""
        ps -p $pid -o pid,ppid,cmd,%cpu,%mem,etime
        
        # Проверяем использование ресурсов
        echo ""
        cpu=$(ps -p $pid -o %cpu= | tr -d ' ')
        mem=$(ps -p $pid -o %mem= | tr -d ' ')
        
        echo -e "  Использование ресурсов:"
        echo -e "    CPU: ${GREEN}$cpu%${NC}"
        echo -e "    MEM: ${GREEN}$mem%${NC}"
        
        # Проверяем health file
        if [ -f "$HEALTH_FILE" ]; then
            echo ""
            echo "  Последнее обновление здоровья: $activity_seconds сек назад"
            
            if [ $activity_seconds -gt 600 ]; then
                echo -e "  ${RED}✗ ВНИМАНИЕ: Нет обновлений более 10 минут!${NC}"
            elif [ $activity_seconds -gt 300 ]; then
                echo -e "  ${YELLOW}! Нет обновлений более 5 минут${NC}"
            else
                echo -e "  ${GREEN}✓ Процесс отзывчив${NC}"
            fi
        else
            echo ""
            echo -e "  ${YELLOW}⚠ Health файл не найден${NC}"
        fi
    else
        echo -e "  ${RED}✗ Процесс с PID $pid не работает${NC}"
        
        # Проверяем, есть ли другие процессы
        if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
            echo -e "  ${YELLOW}! Но найдены другие процессы:${NC}"
            pgrep -f "scheduled_self_play.py" | while read p; do
                ps -p $p -o pid,ppid,cmd,%cpu,%mem,etime=
            done
        else
            echo -e "  ${RED}✗ Никаких процессов обучения не найдено${NC}"
        fi
    fi
fi

echo ""
echo "================================"
echo "Последние записи в логе:"
echo "================================"

if [ -f "$LOG_FILE" ]; then
    tail -n 20 "$LOG_FILE"
else
    echo "Лог файл не найден: $LOG_FILE"
fi

echo ""
echo "================================"
echo "Рекомендации:"
echo "================================"
echo ""
echo "Если обучение не запущено:"
echo "  1. sudo systemctl start minichesstrain.service"
echo ""
echo "Если процесс зависший:"
echo "  1. sudo systemctl restart minichesstrain.service"
echo ""
echo "Для просмотра полных логов:"
echo "  tail -f $LOG_FILE"
echo ""
echo "Для просмотра systemd логов:"
echo "  sudo journalctl -u minichesstrain.service -f"
echo ""
