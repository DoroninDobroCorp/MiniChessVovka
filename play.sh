#!/bin/bash
# Скрипт запуска Mini Chess с сильным AI

echo "=========================================="
echo "Mini Chess 6x6 Crazyhouse - Strong AI"
echo "=========================================="
echo ""
echo "AI настройки:"
echo "- Глубина поиска: 6 полуходов (быстрая игра)"
echo "- Параллельный поиск: 7 воркеров"
echo "- Quiescence depth: 4"
echo "- Move Cache: Включен (сохраняется в БД)"
echo ""
echo "Запуск игры..."
echo ""

# Переходим в директорию скрипта
cd "$(dirname "$0")"

# Проверяем наличие venv
if [ ! -d "venv" ]; then
    echo "ОШИБКА: venv не найден!"
    echo "Создайте его командой: python3 -m venv venv"
    echo "Затем установите зависимости: ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Запускаем игру
./venv/bin/python main.py

echo ""
echo "Игра завершена."
