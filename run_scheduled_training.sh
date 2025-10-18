#!/bin/bash
# Скрипт для запуска обучения в заданное время с ограничением CPU

# Конфигурация
PROJECT_DIR="/srv/MiniChessVovka"
PYTHON_CMD="python3"
SCRIPT_NAME="scheduled_self_play.py"
LOG_FILE="$PROJECT_DIR/training_log.txt"
SCHEDULER_LOG="$PROJECT_DIR/scheduler.log"
PID_FILE="$PROJECT_DIR/training.pid"

# Временное окно (часы)
START_HOUR=2
END_HOUR=10

# CPU ограничения (использовать первые 7 ядер: 0-6, оставить ядро 7 свободным)
CPU_MASK="0-6"

# Функция логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$SCHEDULER_LOG"
}

# Функция проверки времени
is_training_time() {
    current_hour=$(date +%H | sed 's/^0//')
    if [ $current_hour -ge $START_HOUR ] && [ $current_hour -lt $END_HOUR ]; then
        return 0
    else
        return 1
    fi
}

# Функция запуска обучения
start_training() {
    log "Запуск обучения..."
    log "CPU маска: $CPU_MASK (используем 7 из 8 ядер)"
    
    cd "$PROJECT_DIR" || exit 1
    
    # Проверяем наличие taskset
    if ! command -v taskset &> /dev/null; then
        log "ВНИМАНИЕ: taskset не найден, запуск без ограничения CPU"
        nohup $PYTHON_CMD "$SCRIPT_NAME" >> "$LOG_FILE" 2>&1 &
    else
        nohup taskset -c $CPU_MASK $PYTHON_CMD "$SCRIPT_NAME" >> "$LOG_FILE" 2>&1 &
    fi
    
    echo $! > "$PID_FILE"
    log "Обучение запущено с PID: $(cat $PID_FILE)"
    log "Будет работать до $END_HOUR:00"
}

# Функция остановки обучения
stop_training() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log "Остановка обучения (PID: $PID)..."
            
            # Отправляем SIGTERM главному процессу
            kill -TERM $PID 2>/dev/null
            
            # Ждем graceful shutdown
            for i in {1..30}; do
                # Проверяем, остались ли какие-то процессы scheduled_self_play
                if ! pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
                    log "Обучение успешно остановлено (все процессы завершены)"
                    rm "$PID_FILE"
                    return 0
                fi
                sleep 1
            done
            
            # Если через 30 секунд процессы все еще работают, убиваем принудительно
            if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
                log "ВНИМАНИЕ: Принудительная остановка всех процессов обучения"
                pkill -9 -f "scheduled_self_play.py"
                rm "$PID_FILE"
            fi
        else
            log "Процесс с PID $PID не найден, проверяем другие процессы..."
            # Проверяем, нет ли других процессов scheduled_self_play
            if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
                log "Найдены другие процессы обучения, останавливаем..."
                pkill -TERM -f "scheduled_self_play.py"
                sleep 5
                if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
                    pkill -9 -f "scheduled_self_play.py"
                fi
            fi
            rm "$PID_FILE"
        fi
    else
        log "PID файл не найден, проверяем процессы..."
        # Проверяем, нет ли запущенных процессов без PID файла
        if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
            log "Найдены процессы обучения без PID файла, останавливаем..."
            pkill -TERM -f "scheduled_self_play.py"
            sleep 5
            if pgrep -f "scheduled_self_play.py" > /dev/null 2>&1; then
                pkill -9 -f "scheduled_self_play.py"
            fi
            log "Процессы остановлены"
        else
            log "Процессы не запущены"
        fi
    fi
}

# Функция проверки запущенного процесса
is_training_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0
        else
            rm "$PID_FILE"
            return 1
        fi
    else
        return 1
    fi
}

# Главная логика
main() {
    log "=== Проверка расписания обучения ==="
    
    if is_training_time; then
        log "Текущее время находится в окне обучения ($START_HOUR:00 - $END_HOUR:00)"
        
        if is_training_running; then
            log "Обучение уже запущено, продолжаем работу"
        else
            log "Обучение не запущено, запускаем..."
            start_training
        fi
    else
        log "Текущее время НЕ в окне обучения ($START_HOUR:00 - $END_HOUR:00)"
        
        if is_training_running; then
            log "Обучение запущено, но время вышло - останавливаем"
            stop_training
        else
            log "Обучение не запущено, ничего не делаем"
        fi
    fi
    
    log "=== Проверка завершена ==="
    log ""
}

# Обработка аргументов командной строки
case "${1:-}" in
    start)
        log "Ручной запуск обучения"
        start_training
        ;;
    stop)
        log "Ручная остановка обучения"
        stop_training
        ;;
    status)
        if is_training_running; then
            PID=$(cat "$PID_FILE")
            log "Обучение запущено (PID: $PID)"
            
            if command -v ps &> /dev/null; then
                log "Использование CPU:"
                ps -p $PID -o pid,ppid,cmd,%cpu,%mem,etime
            fi
            
            if [ -f "$LOG_FILE" ]; then
                log "Последние 10 строк лога:"
                tail -n 10 "$LOG_FILE"
            fi
        else
            log "Обучение не запущено"
        fi
        ;;
    *)
        main
        ;;
esac
