# ✅ Автоматическое обучение Mini Chess AI - УСТАНОВЛЕНО

## 🎉 Статус: РАБОТАЕТ!

Система автоматического обучения успешно установлена и работает!

### ✅ Что было сделано:

1. **Восстановлен venv** - пересоздан виртуальное окружение для Linux
2. **Создан autorun_training.sh** - скрипт с автоперезапуском при сбоях
3. **Установлены systemd service и timer** - автоматический запуск по расписанию
4. **Настроен мониторинг и здоровье-проверки** - контроль состояния
5. **Создана документация** - полные инструкции использования

## 🚀 Текущее состояние

```
Service:  ✅ RUNNING (minichesstrain.service)
Timer:    ✅ ACTIVE  (minichesstrain.timer)
Process:  ✅ ALIVE   (PID: 3265922)
Health:   ✅ GOOD    (отзывчив, использует ресурсы)
Training: ✅ STARTED (Партия 1 в процессе)
```

**AI уже считает ходы и улучшает свои навыки! 🧠**

## 📅 Расписание обучения

**Время работы**: 00:00 - 08:00 UTC каждый день (ночные часы)

- ✅ Проверка каждые 30 минут
- ✅ Автоматический запуск в 00:00 UTC
- ✅ Автоматическая остановка в 08:00 UTC
- ✅ Перезапуск при сбоях (до 5 попыток)

## 🎯 Что делает система ночью

1. AI играет сам с собой (depth 6)
2. В 20% случаев выбирает альтернативные ходы
3. Каждый ход сохраняется в кэш БД
4. Логируется каждое событие
5. При крахе - автоматически перезапускается
6. Утром (08:00) процесс корректно завершается

## 📊 Команды для мониторинга

### Быстрая проверка здоровья
```bash
./check_training_health.sh
```

### Live dashboard (обновляется каждые 10 сек)
```bash
./training_dashboard.sh
```

### Просмотр логов в реальном времени
```bash
sudo journalctl -u minichesstrain.service -f
```

### Просмотр статуса
```bash
sudo systemctl status minichesstrain.service
systemctl list-timers minichesstrain.timer
```

## 🛠️ Управление

### Запустить сейчас (тест)
```bash
sudo systemctl start minichesstrain.service
```

### Остановить
```bash
sudo systemctl stop minichesstrain.service
```

### Перезагрузить
```bash
sudo systemctl restart minichesstrain.service
```

### Отключить автозапуск
```bash
sudo systemctl disable minichesstrain.service
sudo systemctl disable minichesstrain.timer
```

## 📁 Файлы и логирование

### Основные файлы
- `autorun_training.sh` - скрипт с автоперезапуском
- `scheduled_self_play.py` - логика обучения
- `check_training_health.sh` - проверка здоровья
- `training_dashboard.sh` - мониторинг

### Логи
- `training_log.txt` - подробный лог каждого хода и партии
- `monitor.log` - логи мониторинга и перезапусков
- `training_progress.txt` - файл прогресса и статистики
- systemd journal - через `journalctl -u minichesstrain.service`

## ⚙️ Конфигурация

### Окно обучения
В файле `run_scheduled_training.sh`:
```bash
START_HOUR=0   # Начало
END_HOUR=8     # Конец
```

### Глубина поиска
В файле `scheduled_self_play.py`:
```python
depth = 6  # Изменить на 4-8 (выше = медленнее, но сильнее)
```

### Исследование
```python
exploration_rate = 0.2  # 20% вероятность альтернативного хода
```

### Ресурсные ограничения
В файле `minichesstrain.service`:
```ini
CPUQuota=80%      # Максимум 80% CPU
MemoryLimit=4G    # Максимум 4 ГБ RAM
```

## 🔧 Если что-то не работает

### Проверить service
```bash
sudo systemctl status minichesstrain.service
```

### Проверить timer
```bash
sudo systemctl status minichesstrain.timer
systemctl list-timers minichesstrain.timer
```

### Посмотреть ошибки
```bash
sudo journalctl -u minichesstrain.service -n 50
```

### Перезапустить
```bash
sudo systemctl restart minichesstrain.service
```

### Убить зависший процесс
```bash
sudo systemctl stop minichesstrain.service
pkill -f scheduled_self_play.py
```

## 📈 Результаты

**Каждую ночь AI становится лучше!**

- ✅ Новые позиции в кэше
- ✅ Улучшенная оценка ходов
- ✅ Лучшее понимание Crazyhouse
- ✅ Развитие тактики и стратегии

За неделю непрерывного обучения AI значительно улучшится! 🚀

## 📞 Справка

Полная документация: см. `AUTOTRAINING_SETUP.md`

---

**Система готова! Обучение работает автоматически по ночам.** ✨

Проверяй прогресс через `./check_training_health.sh` или `./training_dashboard.sh`
