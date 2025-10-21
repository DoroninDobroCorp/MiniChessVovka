#!/bin/bash
# Скрипт проверки здоровья обучения

PROJECT_DIR="/srv/MiniChessVovka"
PID_FILE="$PROJECT_DIR/training.pid"
HEALTH_FILE="$PROJECT_DIR/training.health"
LOG_FILE="$PROJECT_DIR/training_log.txt"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================"
echo "Проверка здоровья обучения Mini Chess"
echo "================================"
echo ""

# Проверка PID файла
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠ PID файл не найден${NC}"
    echo "  Обучение, вероятно, не запущено"
    echo ""
    
    # Проверяем, запущены ли процессы напрямую
    if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
        echo -e "${YELLOW}! Но найдены процессы scheduled_self_play.py:${NC}"
        pgrep -f "scheduled_self_play.py" | while read pid; do
            ps -p $pid -o pid,ppid,cmd,%cpu,%mem,etime=
        done
    fi
else
    pid=$(cat "$PID_FILE")
    echo "PID из файла: $pid"
    
    # Проверяем, работает ли процесс
    if ps -p $pid > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Процесс работает${NC}"
        echo ""
        ps -p $pid -o pid,ppid,cmd,%cpu,%mem,etime
        
        # Проверяем использование ресурсов
        echo ""
        cpu=$(ps -p $pid -o %cpu= | tr -d ' ')
        mem=$(ps -p $pid -o %mem= | tr -d ' ')
        
        echo -e "Использование ресурсов:"
        echo -e "  CPU: ${GREEN}$cpu%${NC}"
        echo -e "  MEM: ${GREEN}$mem%${NC}"
        
        # Проверяем health file
        if [ -f "$HEALTH_FILE" ]; then
            last_update=$(cat "$HEALTH_FILE")
            current_time=$(date +%s)
            diff=$((current_time - last_update))
            
            echo ""
            echo "Последнее обновление здоровья: $diff сек назад"
            
            if [ $diff -gt 300 ]; then
                echo -e "${RED}✗ ВНИМАНИЕ: Нет обновлений более 5 минут!${NC}"
            elif [ $diff -gt 120 ]; then
                echo -e "${YELLOW}! Нет обновлений более 2 минут${NC}"
            else
                echo -e "${GREEN}✓ Процесс отзывчив${NC}"
            fi
        else
            echo ""
            echo -e "${YELLOW}⚠ Health файл не найден${NC}"
        fi
    else
        echo -e "${RED}✗ Процесс с PID $pid не работает${NC}"
        
        # Проверяем, есть ли другие процессы
        if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
            echo -e "${YELLOW}! Но найдены другие процессы:${NC}"
            pgrep -f "scheduled_self_play.py" | while read p; do
                ps -p $p -o pid,ppid,cmd,%cpu,%mem,etime=
            done
        else
            echo -e "${RED}✗ Никаких процессов обучения не найдено${NC}"
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
