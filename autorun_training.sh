#!/bin/bash
# Mini Chess Training Launcher

set -e

PROJECT_DIR="/srv/MiniChessVovka"
PYTHON_CMD="python3"
# Use absolute path to be safe
SCRIPT_NAME="/srv/MiniChessVovka/src/scheduled_self_play.py"
LOG_FILE="$PROJECT_DIR/training_log.txt"
MONITOR_LOG="$PROJECT_DIR/monitor.log"
PID_FILE="$PROJECT_DIR/training.pid"
HEALTH_CHECK_FILE="$PROJECT_DIR/training.health"

MAX_RETRIES=5
RETRY_DELAY=10
HEALTH_CHECK_INTERVAL=30
CPU_MASK="0-6"

log() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    message="[$timestamp] $1"
    echo "$message" | tee -a "$MONITOR_LOG"
}

update_health() {
    echo "$(date +%s)" > "$HEALTH_CHECK_FILE"
}

check_process_health() {
    local pid=$1
    
    if ! ps -p $pid > /dev/null 2>&1; then
        return 1
    fi
    
    local cpu_usage=$(ps -p $pid -o %cpu= 2>/dev/null | tr -d ' ')
    local mem_usage=$(ps -p $pid -o %mem= 2>/dev/null | tr -d ' ')
    
    if [ -z "$cpu_usage" ] || [ -z "$mem_usage" ]; then
        return 1
    fi
    
    return 0
}

run_training_with_restart() {
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log "Attempting to start training #$attempt of $MAX_RETRIES"
        
        cd "$PROJECT_DIR" || exit 1
        
        if ! command -v taskset &> /dev/null; then
            log "WARNING: taskset not found, running without CPU affinity"
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
        log "Training started with PID: $pid"
        
        sleep 3
        
        if ! ps -p $pid > /dev/null 2>&1; then
            log "ERROR: Process $pid exited immediately"
            attempt=$((attempt + 1))
            if [ $attempt -le $MAX_RETRIES ]; then
                log "Waiting ${RETRY_DELAY}s before retry..."
                sleep $RETRY_DELAY
            fi
            continue
        fi
        
        log "Process started successfully, monitoring health..."
        
        while ps -p $pid > /dev/null 2>&1; do
            update_health
            sleep $HEALTH_CHECK_INTERVAL
            
            if ! check_process_health $pid; then
                log "WARNING: Process $pid might be hung"
                break
            fi
        done
        
        log "Process $pid finished"
        
        wait $pid 2>/dev/null
        local exit_code=$?
        
        if [ $exit_code -eq 0 ]; then
            log "Process finished correctly (exit code: 0)"
            attempt=$((attempt + 1))
            if [ $attempt -le $MAX_RETRIES ]; then
                log "Pause before restart..."
                sleep 5
            fi
        elif [ $exit_code -eq 143 ] || [ $exit_code -eq 15 ]; then
            log "Process received SIGTERM (exit code: $exit_code), exiting"
            rm -f "$PID_FILE"
            return 0
        else
            log "ERROR: Process exited with error code: $exit_code"
            attempt=$((attempt + 1))
            if [ $attempt -le $MAX_RETRIES ]; then
                log "Waiting ${RETRY_DELAY}s before retry..."
                sleep $RETRY_DELAY
            fi
        fi
    done
    
    log "CRITICAL ERROR: Max retries reached ($MAX_RETRIES)"
    return 1
}

graceful_shutdown() {
    log "Received termination signal, shutting down..."
    
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            log "Sending SIGTERM to process $pid..."
            kill -TERM $pid
            
            for i in {1..30}; do
                if ! ps -p $pid > /dev/null 2>&1; then
                    log "Process exited correctly"
                    rm -f "$PID_FILE"
                    exit 0
                fi
                sleep 1
            done
            
            log "Forcing process termination..."
            kill -9 $pid 2>/dev/null || true
            rm -f "$PID_FILE"
        fi
    fi
    
    exit 0
}

trap graceful_shutdown SIGTERM SIGINT

log "================================"
log "Starting Mini Chess Auto-Training System"
log "Project: $PROJECT_DIR"
log "Script: $SCRIPT_NAME"
log "Log: $LOG_FILE"
log "Max retries: $MAX_RETRIES"
log "================================"

run_training_with_restart

log "Work finished"
