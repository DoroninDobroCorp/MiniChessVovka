#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расширенный режим самообучения с подробным логированием
Логирует каждый ход с временной меткой для отслеживания прогресса
"""

import signal
import sys
import time
import random
import os
import threading
from datetime import datetime, timezone
from gamestate import GameState
import ai
from utils import format_move_for_print


# Глобальный флаг для graceful shutdown
shutdown_requested = False
health_updater_running = False

# Файл логов
LOG_FILE = "training_log.txt"
PROGRESS_FILE = "training_progress.txt"
HEALTH_FILE = "training.health"
PID_FILE = "training.pid"


def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    global shutdown_requested
    log_message("\n" + "="*60)
    log_message("Получен сигнал прерывания. Завершаем работу...")
    log_message("="*60)
    shutdown_requested = True
    
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass

def write_pid():
    """Writes current PID to file"""
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def setup_signal_handlers():
    """Устанавливает обработчики сигналов"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    write_pid()


def update_health():
    """Обновляет health файл текущим timestamp для мониторинга"""
    try:
        with open(HEALTH_FILE, 'w') as f:
            f.write(str(int(time.time())))
    except Exception as e:
        # Не прерываем работу, если не удалось записать health файл
        pass


def health_updater_thread():
    """Фоновый поток для регулярного обновления health файла"""
    global health_updater_running
    health_updater_running = True
    
    while not shutdown_requested and health_updater_running:
        update_health()
        # Обновляем каждые 30 секунд
        for _ in range(30):
            if shutdown_requested:
                break
            time.sleep(1)
    
    health_updater_running = False


def start_health_updater():
    """Запускает фоновый поток обновления health"""
    thread = threading.Thread(target=health_updater_thread, daemon=True)
    thread.start()
    return thread


def log_message(message, console=True, file=True):
    """
    Логирует сообщение в файл и/или консоль
    
    Args:
        message: Сообщение для логирования
        console: Выводить ли в консоль
        file: Записывать ли в файл
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if console:
        print(message)
    
    if file:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            # Добавляем timestamp к каждой строке
            for line in message.split('\n'):
                if line.strip():
                    f.write(f"[{timestamp}] {line}\n")
                else:
                    f.write("\n")


def update_progress(stats, training_start_time):
    """
    Обновляет файл с прогрессом обучения
    
    Args:
        stats: Словарь со статистикой
        training_start_time: Время начала обучения
    """
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write(f"Прогресс обучения Mini Chess AI\n")
        f.write(f"Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        
        training_duration = time.time() - training_start_time
        hours = int(training_duration // 3600)
        minutes = int((training_duration % 3600) // 60)
        
        f.write(f"Время работы: {hours}ч {minutes}мин\n")
        f.write(f"Всего игр: {stats['total_games']}\n")
        f.write(f"Размер кэша: {len(ai.move_cache)} позиций\n\n")
        
        if stats['total_games'] > 0:
            f.write("Результаты:\n")
            f.write(f"  - Мат: {stats['checkmate']} ({stats['checkmate']/stats['total_games']*100:.1f}%)\n")
            f.write(f"    • Победы белых: {stats['white_wins']}\n")
            f.write(f"    • Победы черных: {stats['black_wins']}\n")
            f.write(f"  - Пат: {stats['stalemate']} ({stats['stalemate']/stats['total_games']*100:.1f}%)\n")
            f.write(f"  - Лимит ходов: {stats['max_moves']}\n\n")
            
            f.write("Статистика:\n")
            f.write(f"  - Среднее ходов в партии: {stats['total_moves']/stats['total_games']:.1f}\n")
            f.write(f"  - Среднее время партии: {stats['total_time']/stats['total_games']:.1f}с\n")
            f.write(f"  - Всего ходов сыграно: {stats['total_moves']}\n")
        
        f.write("\n" + "="*60 + "\n")
        f.write("Для остановки обучения нажмите Ctrl+C в терминале\n")
        f.write("или отправьте сигнал SIGTERM процессу\n")
        f.write("="*60 + "\n")


def choose_move_with_exploration(gamestate: GameState, depth: int, exploration_rate: float, game_num: int, move_num: int):
    """
    Выбирает ход с исследованием альтернатив и логированием
    
    Args:
        gamestate: Текущее состояние игры
        depth: Глубина поиска
        exploration_rate: Вероятность выбора второго лучшего хода
        game_num: Номер текущей игры
        move_num: Номер текущего хода
    
    Returns:
        Выбранный ход
    """
    move_calc_start = time.time()
    
    # Получаем топ-2 лучших хода
    top_moves = ai.find_best_move(gamestate, depth=depth, return_top_n=2)
    
    if not top_moves:
        log_message("Нет доступных ходов!")
        return None
    
    # Если есть только один ход, выбираем его
    if len(top_moves) == 1:
        move, score = top_moves[0]
        calc_time = time.time() - move_calc_start
        log_message(f"  Единственный ход: {format_move_for_print(move)}, оценка: {score:.1f}, время: {calc_time:.1f}с")
        return move
    
    # Проверяем, нужно ли исследовать
    explore = random.random() < exploration_rate
    
    best_move, best_score = top_moves[0]
    second_move, second_score = top_moves[1]
    
    # Не исследуем, если лучший ход - мат
    is_mate = abs(best_score) >= ai.CHECKMATE_SCORE * 0.9
    
    calc_time = time.time() - move_calc_start
    
    if explore and not is_mate:
        log_message(f"  ИССЛЕДОВАНИЕ: Выбираем 2-й лучший ход")
        log_message(f"    1-й: {format_move_for_print(best_move)}, оценка: {best_score:.1f}")
        log_message(f"    2-й: {format_move_for_print(second_move)}, оценка: {second_score:.1f} ← ВЫБРАН")
        log_message(f"    Время расчета: {calc_time:.1f}с")
        return second_move
    else:
        reason = "мат найден" if is_mate else "стандартный выбор"
        log_message(f"  Лучший ход ({reason}): {format_move_for_print(best_move)}, оценка: {best_score:.1f}")
        if not is_mate:
            log_message(f"    2-й вариант: {format_move_for_print(second_move)}, оценка: {second_score:.1f}")
        log_message(f"    Время расчета: {calc_time:.1f}с")
        return best_move


def get_current_utc_hour():
    """Возвращает текущий час в UTC"""
    return datetime.now(timezone.utc).hour

def is_training_time():
    """Проверяет находимся ли в окне обучения 02:00-10:00 UTC"""
    current_hour = get_current_utc_hour()
    return 2 <= current_hour < 10

def is_before_training_window():
    """Проверяет находимся ли ДО окна обучения (00:00-02:00 UTC)"""
    current_hour = get_current_utc_hour()
    return current_hour < 2

def should_exit():
    """Проверяет нужно ли завершать работу (достигли 10:00 UTC)"""
    current_hour = get_current_utc_hour()
    # Выходим только если час >= 10 (после окна обучения)
    return current_hour >= 10

def wait_for_training_window():
    """
    Ожидает начала окна обучения (02:00 UTC).
    Возвращает True если дождались, False если получен сигнал завершения.
    """
    global shutdown_requested
    
    if is_training_time():
        return True  # Уже в окне
    
    if should_exit():
        # После 10:00 UTC - выходим, таймер перезапустит завтра в 00:00
        log_message(f"Текущее время после окна обучения (час UTC: {get_current_utc_hour()}). Завершение, таймер перезапустит завтра.")
        return False
    
    # Мы в периоде 00:00-02:00 UTC - ждём начала окна
    log_message(f"\nОжидание начала окна обучения (02:00 UTC)...")
    log_message(f"Текущий час UTC: {get_current_utc_hour()}")
    
    while is_before_training_window() and not shutdown_requested:
        # Вычисляем сколько осталось ждать
        now = datetime.now(timezone.utc)
        minutes_to_wait = (2 - now.hour) * 60 - now.minute
        
        if minutes_to_wait > 0:
            log_message(f"До начала обучения: ~{minutes_to_wait} минут. Ждём...", console=True, file=False)
        
        # Спим по 60 секунд с проверкой shutdown
        for _ in range(60):
            if shutdown_requested:
                log_message("Получен сигнал завершения во время ожидания.")
                return False
            time.sleep(1)
            update_health()  # Обновляем health чтобы показать что процесс жив
    
    if shutdown_requested:
        return False
    
    log_message(f"\nОкно обучения началось! (час UTC: {get_current_utc_hour()})")
    return True


def play_self_game(depth: int, exploration_rate: float, max_moves: int, game_num: int):
    """
    Проводит одну игру AI против себя с подробным логированием
    
    Args:
        depth: Глубина поиска AI
        exploration_rate: Вероятность выбора 2-го лучшего хода
        max_moves: Максимальное количество ходов в партии
        game_num: Номер текущей игры
    
    Returns:
        dict с результатами игры
    """
    global shutdown_requested
    
    # Проверяем временное окно перед началом игры
    if should_exit():
        log_message(f"\nДостигнут конец окна обучения (10:00 UTC). Завершение работы.")
        ai.save_move_cache_to_db(ai.move_cache)
        sys.exit(0)

    
    gamestate = GameState()
    gamestate.setup_initial_board()
    
    game_start = time.time()
    move_count = 0
    move_times = []
    
    log_message("\n" + "="*60)
    log_message(f"Партия {game_num} (глубина: {depth}, исследование: {exploration_rate*100:.0f}%)")
    log_message("="*60 + "\n")
    
    while not shutdown_requested:
        # Проверяем временное окно перед каждым ходом
        if should_exit():
            log_message(f"\nДостигнут конец окна обучения (10:00 UTC). Завершение работы.")
            ai.save_move_cache_to_db(ai.move_cache)
            sys.exit(0)

        
        move_count += 1
        current_player = "Белые" if gamestate.current_turn == 'w' else "Черные"
        
        log_message(f"\n--- Ход {move_count} ({current_player}) ---")
        
        # Проверяем терминальное состояние
        if gamestate.checkmate:
            winner = "Черные" if gamestate.current_turn == 'w' else "Белые"
            log_message(f"\nМАТ! {winner} победили!")
            return {
                'result': 'checkmate',
                'winner': winner,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        if gamestate.stalemate:
            log_message("\nПАТ! Ничья.")
            return {
                'result': 'stalemate',
                'winner': None,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        # Проверяем лимит ходов
        if move_count > max_moves:
            log_message(f"\nДостигнут лимит ходов ({max_moves}). Ничья.")
            return {
                'result': 'max_moves',
                'winner': None,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        # Выбираем и делаем ход
        move_start = time.time()
        move = choose_move_with_exploration(gamestate, depth, exploration_rate, game_num, move_count)
        move_time = time.time() - move_start
        move_times.append(move_time)
        
        if move is None:
            log_message("Ошибка: нет доступных ходов!")
            return {
                'result': 'error',
                'winner': None,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        # Делаем ход
        if not gamestate.make_move(move):
            log_message(f"Ошибка: невозможно сделать ход {format_move_for_print(move)}")
            return {
                'result': 'error',
                'winner': None,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        # Обрабатываем промоушен если нужно
        if gamestate.needs_promotion_choice:
            promo_piece = 'R' if gamestate.current_turn == 'b' else 'r'
            gamestate.complete_promotion(promo_piece)
        
        # Сохраняем кэш после каждого хода
        ai.save_move_cache_to_db(ai.move_cache)
    
    # Если получили сигнал прерывания
    return {
        'result': 'interrupted',
        'winner': None,
        'moves': move_count - 1,
        'duration': time.time() - game_start,
        'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
    }


def run_self_play_training(num_games: int = None, depth: int = 5, exploration_rate: float = 0.2):
    """
    Запускает режим самообучения с полным логированием
    
    Args:
        num_games: Количество игр для проведения (None = бесконечно)
        depth: Глубина поиска AI
        exploration_rate: Вероятность выбора 2-го лучшего хода
    """
    global shutdown_requested
    
    # Создаем/очищаем файл логов для новой сессии
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write("\n" + "="*80 + "\n")
        f.write(f"Новая сессия обучения начата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
    
    log_message("\n" + "="*60)
    log_message("РЕЖИМ САМООБУЧЕНИЯ С РАСШИРЕННЫМ ЛОГИРОВАНИЕМ")
    log_message("="*60)
    log_message(f"Параметры:")
    log_message(f"  - Глубина поиска: {depth}")
    log_message(f"  - Вероятность исследования: {exploration_rate*100:.0f}%")
    log_message(f"  - Количество игр: {'∞' if num_games is None else num_games}")
    log_message(f"  - Файл логов: {LOG_FILE}")
    log_message(f"  - Файл прогресса: {PROGRESS_FILE}")
    log_message(f"\nДля остановки нажмите Ctrl+C или отправьте SIGTERM")
    log_message("="*60)
    
    # Загружаем кэш из БД
    log_message("\nЗагрузка кэша ходов из базы данных...")
    ai.load_move_cache_from_db()
    log_message(f"Загружено {len(ai.move_cache)} позиций из кэша")
    
    stats = {
        'total_games': 0,
        'checkmate': 0,
        'stalemate': 0,
        'max_moves': 0,
        'interrupted': 0,
        'errors': 0,
        'white_wins': 0,
        'black_wins': 0,
        'total_moves': 0,
        'total_time': 0
    }
    
    game_num = 0
    training_start = time.time()
    
    try:
        while not shutdown_requested:
            if num_games is not None and game_num >= num_games:
                log_message(f"\nВыполнено {num_games} игр. Завершаем...")
                break
            
            game_num += 1
            
            result = play_self_game(depth, exploration_rate, 200, game_num)
            
            # Обновляем статистику
            stats['total_games'] += 1
            stats[result['result']] = stats.get(result['result'], 0) + 1
            stats['total_moves'] += result['moves']
            stats['total_time'] += result['duration']
            
            if result.get('winner') == 'Белые':
                stats['white_wins'] += 1
            elif result.get('winner') == 'Черные':
                stats['black_wins'] += 1
            
            # Выводим промежуточную статистику
            log_message("\n" + "-"*60)
            log_message("Статистика текущей партии:")
            log_message(f"  Результат: {result['result']}")
            if result.get('winner'):
                log_message(f"  Победитель: {result['winner']}")
            log_message(f"  Ходов: {result['moves']}")
            log_message(f"  Длительность: {result['duration']:.1f}с ({result['duration']/60:.1f} мин)")
            log_message(f"  Среднее время хода: {result['avg_move_time']:.1f}с")
            
            log_message("\nОбщая статистика:")
            log_message(f"  Всего игр: {stats['total_games']}")
            log_message(f"  Мат: {stats['checkmate']} ({stats['checkmate']/stats['total_games']*100:.1f}%)")
            log_message(f"    - Победы белых: {stats['white_wins']}")
            log_message(f"    - Победы черных: {stats['black_wins']}")
            log_message(f"  Пат: {stats['stalemate']} ({stats['stalemate']/stats['total_games']*100:.1f}%)")
            log_message(f"  Лимит ходов: {stats['max_moves']}")
            log_message(f"  Среднее ходов в партии: {stats['total_moves']/stats['total_games']:.1f}")
            log_message(f"  Среднее время партии: {stats['total_time']/stats['total_games']:.1f}с")
            log_message(f"  Размер кэша: {len(ai.move_cache)} позиций")
            log_message("-"*60)
            
            # Обновляем файл прогресса
            update_progress(stats, training_start)
            
            if result['result'] == 'interrupted':
                break
    
    except KeyboardInterrupt:
        log_message("\n\nПолучен сигнал прерывания...")
    
    finally:
        # Финальное сохранение кэша
        log_message("\n" + "="*60)
        log_message("Сохранение кэша в базу данных...")
        ai.save_move_cache_to_db(ai.move_cache)
        
        training_duration = time.time() - training_start
        
        log_message("\n" + "="*60)
        log_message("ФИНАЛЬНАЯ СТАТИСТИКА")
        log_message("="*60)
        log_message(f"Всего игр: {stats['total_games']}")
        log_message(f"Время обучения: {training_duration/3600:.2f} часов ({training_duration/60:.1f} минут)")
        if stats['total_games'] > 0:
            log_message(f"\nРезультаты:")
            log_message(f"  Мат: {stats['checkmate']} ({stats['checkmate']/stats['total_games']*100:.1f}%)")
            log_message(f"    - Победы белых: {stats['white_wins']}")
            log_message(f"    - Победы черных: {stats['black_wins']}")
            log_message(f"  Пат: {stats['stalemate']} ({stats['stalemate']/stats['total_games']*100:.1f}%)")
            log_message(f"  Лимит ходов: {stats['max_moves']}")
            log_message(f"  Ошибки: {stats['errors']}")
            log_message(f"  Прервано: {stats['interrupted']}")
            log_message(f"\nСтатистика игры:")
            log_message(f"  Среднее ходов: {stats['total_moves']/stats['total_games']:.1f}")
            log_message(f"  Среднее время партии: {stats['total_time']/stats['total_games']:.1f}с")
            log_message(f"  Всего ходов: {stats['total_moves']}")
        log_message(f"\nРазмер кэша: {len(ai.move_cache)} позиций")
        log_message("="*60)
        
        # Финальное обновление прогресса
        update_progress(stats, training_start)


def main():
    """Точка входа"""
    setup_signal_handlers()
    
    # Запускаем фоновый поток для обновления health каждые 30 сек
    health_thread = start_health_updater()
    
    log_message("\n" + "="*60)
    log_message("Mini Chess AI Self-Play Training")
    log_message(f"Запуск: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log_message(f"Окно обучения: 02:00-10:00 UTC (8 часов)")
    log_message("="*60)
    
    # Ждём начала окна обучения если нужно
    if not wait_for_training_window():
        log_message("Обучение не начато - завершение.")
        return
    
    # Параметры самообучения
    num_games = None  # None = бесконечно, или укажите число
    depth = 6         # Глубина поиска (optimized: ~0.5s/move at depth 6)
    exploration_rate = 0.2  # 20% вероятность выбора 2-го лучшего хода
    
    run_self_play_training(num_games, depth, exploration_rate)


if __name__ == "__main__":
    main()
