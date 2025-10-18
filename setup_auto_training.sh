#!/bin/bash
# Скрипт установки автоматического обучения

PROJECT_DIR="/srv/MiniChessVovka"
SCHEDULER_SCRIPT="$PROJECT_DIR/run_scheduled_training.sh"
CRON_JOB="*/15 * * * * $SCHEDULER_SCRIPT >> $PROJECT_DIR/scheduler.log 2>&1"

echo "================================================="
echo "Установка автоматического обучения Mini Chess AI"
echo "================================================="
echo ""

# Проверяем права на файлы
echo "1. Установка прав выполнения на скрипты..."
chmod +x "$SCHEDULER_SCRIPT"
chmod +x "$PROJECT_DIR/scheduled_self_play.py"
echo "   ✓ Права установлены"
echo ""

# Проверяем наличие taskset
echo "2. Проверка наличия утилиты taskset..."
if command -v taskset &> /dev/null; then
    echo "   ✓ taskset найден - будет использоваться ограничение на 7 ядер"
else
    echo "   ⚠ taskset не найден - обучение будет использовать все ядра"
    echo "   Для установки taskset (на Ubuntu/Debian):"
    echo "   sudo apt-get install util-linux"
fi
echo ""

# Показываем информацию о процессоре
echo "3. Информация о процессоре:"
if command -v lscpu &> /dev/null; then
    CORES=$(lscpu | grep "^CPU(s):" | awk '{print $2}')
    echo "   Доступно ядер: $CORES"
    if [ "$CORES" -ge 8 ]; then
        echo "   ✓ Достаточно ядер для ограничения на 7"
    else
        echo "   ⚠ У вас меньше 8 ядер, настройте CPU_MASK в скрипте"
    fi
else
    echo "   Не удалось определить количество ядер"
fi
echo ""

# Настройка cron
echo "4. Настройка автоматического запуска через cron..."
echo "   Задача cron будет запускаться каждые 15 минут"
echo "   и проверять, нужно ли запустить/остановить обучение"
echo ""

# Проверяем существующую запись cron
if crontab -l 2>/dev/null | grep -q "$SCHEDULER_SCRIPT"; then
    echo "   ⚠ Задача cron уже существует"
    read -p "   Обновить? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Удаляем старую и добавляем новую
        (crontab -l 2>/dev/null | grep -v "$SCHEDULER_SCRIPT"; echo "$CRON_JOB") | crontab -
        echo "   ✓ Задача cron обновлена"
    else
        echo "   → Пропускаем обновление"
    fi
else
    # Добавляем новую задачу
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "   ✓ Задача cron добавлена"
fi
echo ""

# Создаем файлы логов если их нет
echo "5. Подготовка файлов логов..."
touch "$PROJECT_DIR/training_log.txt"
touch "$PROJECT_DIR/scheduler.log"
touch "$PROJECT_DIR/training_progress.txt"
echo "   ✓ Файлы логов готовы"
echo ""

# Показываем текущее расписание
echo "================================================="
echo "Установка завершена!"
echo "================================================="
echo ""
echo "Параметры обучения:"
echo "  • Время работы: 02:00 - 10:00 каждый день"
echo "  • CPU ядра: 0-6 (7 из 8 ядер)"
echo "  • Проверка каждые: 15 минут"
echo ""
echo "Файлы:"
echo "  • Лог обучения: $PROJECT_DIR/training_log.txt"
echo "  • Лог планировщика: $PROJECT_DIR/scheduler.log"
echo "  • Прогресс: $PROJECT_DIR/training_progress.txt"
echo "  • База данных: $PROJECT_DIR/move_cache.db"
echo ""
echo "Управление:"
echo "  • Запустить сейчас:    $SCHEDULER_SCRIPT start"
echo "  • Остановить:          $SCHEDULER_SCRIPT stop"
echo "  • Проверить статус:    $SCHEDULER_SCRIPT status"
echo "  • Просмотр прогресса:  cat $PROJECT_DIR/training_progress.txt"
echo "  • Просмотр последнего лога: tail -f $PROJECT_DIR/training_log.txt"
echo ""
echo "Для изменения времени работы отредактируйте переменные"
echo "START_HOUR и END_HOUR в файле $SCHEDULER_SCRIPT"
echo ""
echo "Для удаления автозапуска выполните:"
echo "  crontab -l | grep -v run_scheduled_training.sh | crontab -"
echo ""
echo "================================================="
