# 🤖 Автоматическое обучение Mini Chess AI

Система настроена для автоматического обучения AI по ночам с автоперезапуском при сбоях.

## 🚀 Быстрая установка

### Вариант 1: Автоматическая установка (рекомендуется)

```bash
cd /srv/MiniChessVovka
sudo bash setup_autotraining.sh
```

Скрипт установит:
- ✅ systemd service (`minichesstrain.service`)
- ✅ systemd timer (`minichesstrain.timer`)
- ✅ Автоперезапуск при сбоях
- ✅ Логирование через journalctl

### Вариант 2: Ручная установка

```bash
# 1. Копируем файлы
sudo cp /srv/MiniChessVovka/minichesstrain.service /etc/systemd/system/
sudo cp /srv/MiniChessVovka/minichesstrain.timer /etc/systemd/system/

# 2. Перезагружаем systemd
sudo systemctl daemon-reload

# 3. Активируем
sudo systemctl enable minichesstrain.service
sudo systemctl enable minichesstrain.timer

# 4. Запускаем
sudo systemctl start minichesstrain.timer
```

## 📋 Управление

### Запуск обучения вручную
```bash
sudo systemctl start minichesstrain.service
```

### Остановка обучения
```bash
sudo systemctl stop minichesstrain.service
```

### Перезагрузка (restart)
```bash
sudo systemctl restart minichesstrain.service
```

### Проверка статуса
```bash
sudo systemctl status minichesstrain.service
sudo systemctl status minichesstrain.timer
```

### Просмотр расписания timer'а
```bash
systemctl list-timers minichesstrain.timer
```

## 📊 Мониторинг

### Просмотр логов в реальном времени
```bash
sudo journalctl -u minichesstrain.service -f
```

### Просмотр последних 100 строк логов
```bash
sudo journalctl -u minichesstrain.service -n 100
```

### Быстрая проверка здоровья
```bash
./check_training_health.sh
```

### Live dashboard (обновляется каждые 10 сек)
```bash
./training_dashboard.sh
```

## ⚙️ Конфигурация

### Окно обучения (часы работы)
Изменяется в файле `/srv/MiniChessVovka/run_scheduled_training.sh`:

```bash
START_HOUR=0   # Начало (часов UTC)
END_HOUR=8     # Конец (часов UTC)
```

Текущее расписание: **0:00 - 8:00 UTC ежедневно** (ночные часы)

### Глубина поиска
В файле `/srv/MiniChessVovka/scheduled_self_play.py`:

```python
depth = 6  # Измени на 4-8 (выше = медленнее, но сильнее)
```

### Вероятность исследования
```python
exploration_rate = 0.2  # 20% вероятность выбора 2-го лучшего хода
```

### Ресурсные ограничения
В файле `/srv/MiniChessVovka/minichesstrain.service`:

```ini
CPUQuota=80%              # Максимум 80% CPU
MemoryLimit=4G            # Максимум 4 ГБ RAM
```

## 📈 Что происходит ночью

1. **Timer проверяет расписание** каждые 30 минут
2. **Если в окне обучения (0-8:00)**: запускает/поддерживает обучение
3. **Если вне окна**: останавливает обучение
4. **При крахе**: автоматический перезапуск (до 5 попыток)
5. **Каждый ход сохраняется** в кэш БД
6. **Логи пишутся** в `training_log.txt` и systemd journal

## 📝 Файлы

| Файл | Назначение |
|------|-----------|
| `autorun_training.sh` | Основной скрипт с автоперезапуском |
| `scheduled_self_play.py` | Логика обучения AI |
| `run_scheduled_training.sh` | Управление расписанием (старый способ) |
| `check_training_health.sh` | Проверка здоровья процесса |
| `training_dashboard.sh` | Live мониторинг |
| `minichesstrain.service` | systemd service |
| `minichesstrain.timer` | systemd timer |
| `setup_autotraining.sh` | Установщик |

## 📊 Логи и мониторинг

### Файловые логи
- **training_log.txt** - детальный лог каждого хода
- **monitor.log** - логи мониторинга и перезапусков
- **scheduler.log** - логи расписания (старый способ)
- **training_progress.txt** - файл прогресса

### Systemd логи
```bash
# Real-time (как tail -f)
sudo journalctl -u minichesstrain.service -f

# Последние N строк
sudo journalctl -u minichesstrain.service -n 50

# За последние N минут
sudo journalctl -u minichesstrain.service --since "30 min ago"

# Уровень логирования
sudo journalctl -u minichesstrain.service -p err  # только ошибки
```

## 🔧 Отладка

### Проверить, что скрипты работают
```bash
# Тест autorun_training.sh (ВНИМАНИЕ: запустит обучение!)
timeout 10 ./autorun_training.sh

# Тест health check
./check_training_health.sh

# Тест dashboard
timeout 20 ./training_dashboard.sh
```

### Если обучение не запускается

1. Проверь статус service
```bash
sudo systemctl status minichesstrain.service
```

2. Проверь статус timer
```bash
sudo systemctl status minichesstrain.timer
systemctl list-timers minichesstrain.timer
```

3. Посмотри логи
```bash
sudo journalctl -u minichesstrain.service -n 50
```

4. Проверь разрешения файлов
```bash
ls -la /srv/MiniChessVovka/*.sh
ls -la /etc/systemd/system/minichesstrain.*
```

5. Запусти service вручную
```bash
sudo systemctl start minichesstrain.service
sleep 2
sudo systemctl status minichesstrain.service
```

### Если процесс зависает

```bash
# Перезагрузи service
sudo systemctl restart minichesstrain.service

# Или убей процесс вручную
sudo systemctl stop minichesstrain.service
pkill -f scheduled_self_play.py
```

## 🎯 Результаты обучения

Каждую ночь AI:
- ✅ Играет множество игр сам с собой
- ✅ Исследует новые позиции (20% второй лучший ход)
- ✅ Сохраняет все ходы в кэш
- ✅ Улучшает оценку позиций

**Результат:** AI становится сильнее ночь за ночью! 🚀

## 📞 Полезные команды

```bash
# Все за один раз
echo "=== STATUS ===" && \
sudo systemctl status minichesstrain.service && \
echo "" && \
echo "=== TIMER ===" && \
systemctl list-timers minichesstrain.timer && \
echo "" && \
echo "=== HEALTH ===" && \
./check_training_health.sh
```

---

**Система готова! Обучение будет работать автоматически по ночам.** ✨
