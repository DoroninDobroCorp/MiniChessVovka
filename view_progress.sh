#!/bin/bash
# Скрипт для быстрого просмотра прогресса обучения

PROJECT_DIR="/srv/MiniChessVovka"
PROGRESS_FILE="$PROJECT_DIR/training_progress.txt"
LOG_FILE="$PROJECT_DIR/training_log.txt"
SCHEDULER_LOG="$PROJECT_DIR/scheduler.log"
PID_FILE="$PROJECT_DIR/training.pid"
DB_FILE="$PROJECT_DIR/move_cache.db"

clear

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Прогресс обучения Mini Chess AI                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Проверяем, запущено ли обучение
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "🟢 Статус: ОБУЧЕНИЕ ЗАПУЩЕНО (PID: $PID)"
        
        # Показываем использование ресурсов
        if command -v ps &> /dev/null; then
            CPU_USAGE=$(ps -p $PID -o %cpu --no-headers | tr -d ' ')
            MEM_USAGE=$(ps -p $PID -o %mem --no-headers | tr -d ' ')
            RUNTIME=$(ps -p $PID -o etime --no-headers | tr -d ' ')
            echo "   CPU: ${CPU_USAGE}% | RAM: ${MEM_USAGE}% | Время работы: $RUNTIME"
        fi
    else
        echo "🔴 Статус: НЕ ЗАПУЩЕНО"
    fi
else
    echo "🔴 Статус: НЕ ЗАПУЩЕНО"
fi

echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

# Показываем прогресс
if [ -f "$PROGRESS_FILE" ]; then
    cat "$PROGRESS_FILE"
else
    echo "⚠️  Файл прогресса не найден"
    echo "   Обучение еще не запускалось"
fi

echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

# Показываем размер базы данных
if [ -f "$DB_FILE" ]; then
    DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
    echo "📊 База данных: $DB_SIZE"
    
    if command -v sqlite3 &> /dev/null; then
        POSITIONS_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM move_cache;" 2>/dev/null)
        if [ ! -z "$POSITIONS_COUNT" ]; then
            echo "   Позиций в кэше: $POSITIONS_COUNT"
        fi
    fi
else
    echo "📊 База данных: не создана"
fi

echo ""

# Показываем размеры логов
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(du -h "$LOG_FILE" | cut -f1)
    LOG_LINES=$(wc -l < "$LOG_FILE")
    echo "📝 Лог обучения: $LOG_SIZE ($LOG_LINES строк)"
fi

if [ -f "$SCHEDULER_LOG" ]; then
    SCHED_SIZE=$(du -h "$SCHEDULER_LOG" | cut -f1)
    echo "📝 Лог планировщика: $SCHED_SIZE"
fi

echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

# Показываем последние события
echo "🕐 Последние события:"
echo ""

if [ -f "$LOG_FILE" ]; then
    echo "Из лога обучения:"
    tail -5 "$LOG_FILE" | while IFS= read -r line; do
        echo "   $line"
    done
    echo ""
fi

if [ -f "$SCHEDULER_LOG" ]; then
    echo "Из лога планировщика:"
    tail -3 "$SCHEDULER_LOG" | while IFS= read -r line; do
        echo "   $line"
    done
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Команды:"
echo "  • Следить за логом:      tail -f $LOG_FILE"
echo "  • Остановить обучение:   $PROJECT_DIR/run_scheduled_training.sh stop"
echo "  • Проверить статус:      $PROJECT_DIR/run_scheduled_training.sh status"
echo ""
