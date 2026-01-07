#!/bin/bash
# Скрипт проверки здоровья обучения

PROJECT_DIR="/srv/MiniChessVovka"
SCRIPT_PATH="$PROJECT_DIR/src/scheduled_self_play.py"
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

# Function to check if we're in pre-training window (00:00-02:00 UTC, waiting for training)
is_waiting_time() {
    current_hour=$(date -u +%H | sed 's/^0*//')
    [ -z "$current_hour" ] && current_hour=0
    [ "$current_hour" -lt 2 ]
}

# Function to get next availability window
get_next_availability() {
    current_hour=$(date -u +%H | sed 's/^0*//')
    [ -z "$current_hour" ] && current_hour=0
    
    if [ "$current_hour" -lt 2 ]; then
        echo "Ожидание начала обучения в $((2 - current_hour)) часов (в 02:00 UTC)"
    elif [ "$current_hour" -ge 10 ]; then
        echo "Следующий запуск через $((24 - current_hour)) часов (в 00:00 UTC завтра)"
    else
        echo "Обучение активно до 10:00 UTC (осталось $((10 - current_hour)) часов)"
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
in_waiting_time=false
if is_training_time; then
    in_training_time=true
elif is_waiting_time; then
    in_waiting_time=true
fi

status_color=""
status_icon=""
status_text=""

if [ "$in_training_time" = true ]; then
    # DURING training hours (2-10 AM UTC)
    if [ "$process_running" = true ] && [ "$process_active" = true ]; then
        status_color="$GREEN"
        status_icon="✓"
        status_text="HEALTHY - Обучение активно (02:00-10:00 UTC)"
    else
        status_color="$RED"
        status_icon="✗"
        if [ "$process_running" = false ]; then
            status_text="PROBLEM - Процесс должен работать в это время"
        else
            status_text="PROBLEM - Процесс неактивен ${activity_seconds}с (порог: 10 мин)"
        fi
    fi
elif [ "$in_waiting_time" = true ]; then
    # WAITING period (00:00-02:00 UTC)
    if [ "$process_running" = true ]; then
        status_color="$BLUE"
        status_icon="⏳"
        status_text="WAITING - Процесс ожидает начала обучения (02:00 UTC)"
    else
        status_color="$RED"
        status_icon="✗"
        status_text="PROBLEM - Процесс должен быть запущен (ожидание 02:00 UTC)"
    fi
else
    # OUTSIDE working hours (10:00-24:00 UTC)
    if [ "$process_running" = false ]; then
        status_color="$GREEN"
        status_icon="✓"
        status_text="HEALTHY - Процесс корректно остановлен (вне рабочих часов)"
    else
        status_color="$YELLOW"
        status_icon="!"
        status_text="NOTE - Процесс всё ещё работает (завершится вскоре)"
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
echo "TIME WINDOW:"
echo "  Current Time: $current_time_utc"
echo "  Timer Start:  00:00 UTC (запуск systemd таймера)"
echo "  Training:     02:00-10:00 UTC (8-часовое окно обучения)"
echo ""
if [ "$in_training_time" = true ]; then
    echo -e "  ${GREEN}Окно обучения активно${NC}"
elif [ "$in_waiting_time" = true ]; then
    echo -e "  ${BLUE}Период ожидания (процесс ждёт 02:00 UTC)${NC}"
else
    echo -e "  ${YELLOW}Вне рабочих часов (таймер запустится в 00:00 UTC)${NC}"
fi
echo -e "  $(get_next_availability)"
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
