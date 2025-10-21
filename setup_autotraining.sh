#!/bin/bash
# Скрипт установки systemd service и timer для автообучения

set -e

echo "================================"
echo "Установка системы автообучения Mini Chess"
echo "================================"
echo ""

# Проверяем права администратора
if [ "$EUID" -ne 0 ]; then 
    echo "ОШИБКА: Этот скрипт требует прав администратора (sudo)"
    echo "Запустите: sudo bash setup_autotraining.sh"
    exit 1
fi

PROJECT_DIR="/srv/MiniChessVovka"

# Проверяем, что файлы существуют
if [ ! -f "$PROJECT_DIR/minichesstrain.service" ]; then
    echo "ОШИБКА: Не найден $PROJECT_DIR/minichesstrain.service"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/minichesstrain.timer" ]; then
    echo "ОШИБКА: Не найден $PROJECT_DIR/minichesstrain.timer"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/autorun_training.sh" ]; then
    echo "ОШИБКА: Не найден $PROJECT_DIR/autorun_training.sh"
    exit 1
fi

# Копируем файлы в systemd
echo "1. Копируем systemd файлы..."
cp "$PROJECT_DIR/minichesstrain.service" /etc/systemd/system/
cp "$PROJECT_DIR/minichesstrain.timer" /etc/systemd/system/

# Даём права на исполнение
chmod 644 /etc/systemd/system/minichesstrain.service
chmod 644 /etc/systemd/system/minichesstrain.timer
chmod 755 "$PROJECT_DIR/autorun_training.sh"

# Перезагружаем systemd daemon
echo "2. Перезагружаем systemd..."
systemctl daemon-reload

# Активируем service
echo "3. Активируем service..."
systemctl enable minichesstrain.service

# Активируем timer
echo "4. Активируем timer..."
systemctl enable minichesstrain.timer

# Запускаем timer
echo "5. Запускаем timer..."
systemctl start minichesstrain.timer

echo ""
echo "================================"
echo "Установка завершена!"
echo "================================"
echo ""
echo "Полезные команды:"
echo ""
echo "  # Проверить статус"
echo "  sudo systemctl status minichesstrain.service"
echo "  sudo systemctl status minichesstrain.timer"
echo ""
echo "  # Посмотреть логи (real-time)"
echo "  sudo journalctl -u minichesstrain.service -f"
echo ""
echo "  # Посмотреть логи (последние 100 строк)"
echo "  sudo journalctl -u minichesstrain.service -n 100"
echo ""
echo "  # Запустить вручную"
echo "  sudo systemctl start minichesstrain.service"
echo ""
echo "  # Остановить"
echo "  sudo systemctl stop minichesstrain.service"
echo ""
echo "  # Перезагрузить"
echo "  sudo systemctl restart minichesstrain.service"
echo ""
echo "  # Посмотреть расписание timer'а"
echo "  systemctl list-timers minichesstrain.timer"
echo ""
echo "================================"
