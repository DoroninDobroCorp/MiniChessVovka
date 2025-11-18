#!/bin/bash
# Watchdog для проверки что timer активен

LOG_FILE="/srv/MiniChessVovka/watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Проверяем статус timer
TIMER_STATUS=$(systemctl is-active minichesstrain.timer)

if [ "$TIMER_STATUS" != "active" ]; then
    log "❌ КРИТИЧНО: Timer НЕ активен (статус: $TIMER_STATUS)!"
    log "Пытаемся перезапустить timer..."
    
    systemctl start minichesstrain.timer
    sleep 2
    
    NEW_STATUS=$(systemctl is-active minichesstrain.timer)
    if [ "$NEW_STATUS" = "active" ]; then
        log "✅ Timer успешно перезапущен"
    else
        log "❌ ОШИБКА: Не удалось перезапустить timer!"
    fi
else
    # Timer активен - проверяем когда следующий запуск
    NEXT_TRIGGER=$(systemctl status minichesstrain.timer | grep "Trigger:" | awk '{print $2, $3, $4}')
    log "✓ Timer активен. Следующий запуск: $NEXT_TRIGGER"
fi

# Проверяем не завис ли service
SERVICE_STATUS=$(systemctl is-active minichesstrain.service)
if [ "$SERVICE_STATUS" = "failed" ]; then
    log "⚠️  Service в статусе failed, сбрасываем..."
    systemctl reset-failed minichesstrain.service
    log "✓ Service сброшен"
fi
