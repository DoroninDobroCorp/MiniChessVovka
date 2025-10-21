#!/bin/bash
# Улучшенный скрипт обучения с автоперезапуском при сбоях

set -e

PROJECT_DIR="/srv/MiniChessVovka"
PYTHON_CMD="python3"
SCRIPT_NAME="scheduled_self_play.py"
LOG_FILE="$PROJECT_DIR/training_log.txt"
MONITOR_LOG="$PROJECT_DIR/monitor.log"
PID_FILE="$PROJECT_DIR/training.pid"
HEALTH_CHECK_FILE="$PROJECT_DIR/training.health"

# Параметры
MAX_RETRIES=5
RETRY_DELAY=10
HEALTH_CHECK_INTERVAL=30
CPU_MASK="0-6"

# Функция логирования
log() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    message="[$timestamp] $1"
    echo "$message" | tee -a "$MONITOR_LOG"
}

# Функция для создания health-check файла
update_health() {
    echo "$(date +%s)" > "$HEALTH_CHECK_FILE"
}

# Функция проверки здоровья процесса
check_process_health() {
    local pid=$1
    
    if ! ps -p $pid > /dev/null 2>&1; then
        return 1  # Процесс мертв
    fi
    
    # Проверяем, использует ли процесс CPU/память
    local cpu_usage=$(ps -p $pid -o %cpu= 2>/dev/null | tr -d ' ')
    local mem_usage=$(ps -p $pid -o %mem= 2>/dev/null | tr -d ' ')
    
    # Если процесс не использует ресурсы длительное время, он может быть зависший
    if [ -z "$cpu_usage" ] || [ -z "$mem_usage" ]; then
        return 1
    fi
    
    return 0
}

# Функция запуска обучения с автоперезапуском
run_training_with_restart() {
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log "Попытка запуска обучения #$attempt из $MAX_RETRIES"
        
        cd "$PROJECT_DIR" || exit 1
        
        # Запускаем обучение в фоне с перехватом сигналов
        if ! command -v taskset &> /dev/null; then
            log "ВНИМАНИЕ: taskset не найден, запуск без ограничения CPU"
            (
                trap 'exit 0' TERM INT
                $PYTHON_CMD "$SCRIPT_NAME" >> "$LOG_FILE" 2>&1
            ) &
        else
            (
                trap 'exit 0' TERM INT
                taskset -c $CPU_MASK $PYTHON_CMD "$SCRIPT_NAME" >> "$LOG_FILE" 2>&1
            ) &
        fi
        
        local pid=$!
        echo $pid > "$PID_FILE"
        log "Обучение запущено с PID: $pid"
        
        # Даём процессу время на инициализацию
        sleep 3
        
        if ! ps -p $pid > /dev/null 2>&1; then
            log "ОШИБКА: Процесс $pid сразу же завершился"
            attempt=$((attempt + 1))
            if [ $attempt -le $MAX_RETRIES ]; then
                log "Ожидание ${RETRY_DELAY}с перед повторной попыткой..."
                sleep $RETRY_DELAY
            fi
            continue
        fi
        
        log "Процесс успешно запущен, мониторим здоровье..."
        
        # Мониторим процесс, пока он работает
        while ps -p $pid > /dev/null 2>&1; do
            update_health
            sleep $HEALTH_CHECK_INTERVAL
            
            if ! check_process_health $pid; then
                log "ПРЕДУПРЕЖДЕНИЕ: Процесс $pid может быть зависший"
                # Пробуем перезагрузить
                break
            fi
        done
        
        log "Процесс $pid завершился"
        
        # Проверяем exit code
        wait $pid 2>/dev/null
        local exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            log "Процесс завершился корректно (exit code: 0)"
            # Даём возможность перезагрузиться
            attempt=$((attempt + 1))
            if [ $attempt -le $MAX_RETRIES ]; then
                log "Пауза перед перезапуском..."
                sleep 5
            fi
        elif [ $exit_code -eq 143 ] || [ $exit_code -eq 15 ]; then
            log "Процесс получил SIGTERM (exit code: $exit_code), завершаем"
            rm -f "$PID_FILE"
            return 0
        else
            log "ОШИБКА: Процесс завершился с кодом ошибки: $exit_code"
            attempt=$((attempt + 1))
            if [ $attempt -le $MAX_RETRIES ]; then
                log "Ожидание ${RETRY_DELAY}с перед повторной попыткой..."
                sleep $RETRY_DELAY
            fi
        fi
    done
    
    log "КРИТИЧЕСКАЯ ОШИБКА: Исчерпаны попытки запуска ($MAX_RETRIES)"
    return 1
}

# Функция graceful shutdown
graceful_shutdown() {
    log "Получен сигнал завершения, завершаем работу..."
    
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log "Отправляем SIGTERM процессу $pid..."
            kill -TERM $pid
            
            # Ждем graceful shutdown
            for i in {1..30}; do
                if ! ps -p $pid > /dev/null 2>&1; then
                    log "Процесс корректно завершился"
                    rm -f "$PID_FILE"
                    exit 0
                fi
                sleep 1
            done
            
            # Force kill if needed
            log "Принудительное завершение процесса..."
            kill -9 $pid 2>/dev/null || true
            rm -f "$PID_FILE"
        fi
    fi
    
    exit 0
}

# Установка обработчиков сигналов
trap graceful_shutdown SIGTERM SIGINT

# Основной цикл
log "================================"
log "Запуск системы автообучения Mini Chess"
log "Проект: $PROJECT_DIR"
log "Скрипт: $SCRIPT_NAME"
log "Лог обучения: $LOG_FILE"
log "Максимум попыток перезапуска: $MAX_RETRIES"
log "================================"

run_training_with_restart

log "Работа завершена"
