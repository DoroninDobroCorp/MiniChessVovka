#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Режим самообучения для Mini Chess AI
AI играет сам с собой и в 20% случаев выбирает второй лучший ход
для исследования альтернативных веток игрового дерева.
"""

import signal
import sys
import time
import random
from datetime import datetime
from gamestate import GameState
import ai
from utils import format_move_for_print


# Глобальный флаг для graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    global shutdown_requested
    print("\n\n" + "="*60)
    print("Получен сигнал прерывания. Завершаем работу...")
    print("="*60)
    shutdown_requested = True


def setup_signal_handlers():
    """Устанавливает обработчики сигналов"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def choose_move_with_exploration(gamestate: GameState, depth: int, exploration_rate: float = 0.2):
    """
    Выбирает ход с исследованием альтернатив.
    
    Args:
        gamestate: Текущее состояние игры
        depth: Глубина поиска
        exploration_rate: Вероятность выбора второго лучшего хода (по умолчанию 20%)
    
    Returns:
        Выбранный ход
    """
    # Получаем топ-2 лучших хода
    top_moves = ai.find_best_move(gamestate, depth=depth, return_top_n=2)
    
    if not top_moves:
        print("Нет доступных ходов!")
        return None
    
    # Если есть только один ход, выбираем его
    if len(top_moves) == 1:
        move, score = top_moves[0]
        print(f"  Единственный ход: {format_move_for_print(move)}, оценка: {score:.1f}")
        return move
    
    # Проверяем, нужно ли исследовать
    explore = random.random() < exploration_rate
    
    best_move, best_score = top_moves[0]
    second_move, second_score = top_moves[1]
    
    # Не исследуем, если лучший ход - мат
    is_mate = abs(best_score) >= ai.CHECKMATE_SCORE * 0.9
    
    if explore and not is_mate:
        print(f"  ИССЛЕДОВАНИЕ: Выбираем 2-й лучший ход")
        print(f"    1-й: {format_move_for_print(best_move)}, оценка: {best_score:.1f}")
        print(f"    2-й: {format_move_for_print(second_move)}, оценка: {second_score:.1f} ← ВЫБРАН")
        return second_move
    else:
        reason = "мат найден" if is_mate else "стандартный выбор"
        print(f"  Лучший ход ({reason}): {format_move_for_print(best_move)}, оценка: {best_score:.1f}")
        if not is_mate:
            print(f"    2-й: {format_move_for_print(second_move)}, оценка: {second_score:.1f}")
        return best_move


def play_self_game(depth: int = 6, exploration_rate: float = 0.2, max_moves: int = 200):
    """
    Проводит одну игру AI против себя
    
    Args:
        depth: Глубина поиска AI
        exploration_rate: Вероятность выбора 2-го лучшего хода
        max_moves: Максимальное количество ходов в партии
    
    Returns:
        dict с результатами игры
    """
    global shutdown_requested
    
    gamestate = GameState()
    gamestate.setup_initial_board()
    
    game_start = time.time()
    move_count = 0
    move_times = []
    
    print("\n" + "="*60)
    print(f"Начинаем новую партию (глубина: {depth}, исследование: {exploration_rate*100:.0f}%)")
    print("="*60 + "\n")
    
    while not shutdown_requested:
        move_count += 1
        current_player = "Белые" if gamestate.current_turn == 'w' else "Черные"
        
        print(f"\n--- Ход {move_count} ({current_player}) ---")
        
        # Проверяем терминальное состояние
        if gamestate.checkmate:
            winner = "Черные" if gamestate.current_turn == 'w' else "Белые"
            print(f"\nМАТ! {winner} победили!")
            return {
                'result': 'checkmate',
                'winner': winner,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        if gamestate.stalemate:
            print("\nПАТ! Ничья.")
            return {
                'result': 'stalemate',
                'winner': None,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        # Проверяем лимит ходов
        if move_count > max_moves:
            print(f"\nДостигнут лимит ходов ({max_moves}). Ничья.")
            return {
                'result': 'max_moves',
                'winner': None,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        # Выбираем и делаем ход
        move_start = time.time()
        move = choose_move_with_exploration(gamestate, depth, exploration_rate)
        move_time = time.time() - move_start
        move_times.append(move_time)
        
        if move is None:
            print("Ошибка: нет доступных ходов!")
            return {
                'result': 'error',
                'winner': None,
                'moves': move_count - 1,
                'duration': time.time() - game_start,
                'avg_move_time': sum(move_times) / len(move_times) if move_times else 0
            }
        
        print(f"  Время расчета: {move_time:.1f}с")
        
        # Делаем ход
        if not gamestate.make_move(move):
            print(f"Ошибка: невозможно сделать ход {format_move_for_print(move)}")
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


def run_self_play_training(num_games: int = None, depth: int = 6, exploration_rate: float = 0.2):
    """
    Запускает режим самообучения
    
    Args:
        num_games: Количество игр для проведения (None = бесконечно)
        depth: Глубина поиска AI
        exploration_rate: Вероятность выбора 2-го лучшего хода
    """
    global shutdown_requested
    
    print("\n" + "="*60)
    print("РЕЖИМ САМООБУЧЕНИЯ")
    print("="*60)
    print(f"Параметры:")
    print(f"  - Глубина поиска: {depth}")
    print(f"  - Вероятность исследования: {exploration_rate*100:.0f}%")
    print(f"  - Количество игр: {'∞' if num_games is None else num_games}")
    print(f"\nДля остановки нажмите Ctrl+C")
    print("="*60)
    
    # Загружаем кэш из БД
    print("\nЗагрузка кэша ходов из базы данных...")
    ai.load_move_cache_from_db()
    
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
                print(f"\nВыполнено {num_games} игр. Завершаем...")
                break
            
            game_num += 1
            print(f"\n{'='*60}")
            print(f"ПАРТИЯ {game_num}" + (f" / {num_games}" if num_games else ""))
            print(f"{'='*60}")
            
            result = play_self_game(depth, exploration_rate)
            
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
            print("\n" + "-"*60)
            print("Статистика текущей партии:")
            print(f"  Результат: {result['result']}")
            if result.get('winner'):
                print(f"  Победитель: {result['winner']}")
            print(f"  Ходов: {result['moves']}")
            print(f"  Длительность: {result['duration']:.1f}с")
            print(f"  Среднее время хода: {result['avg_move_time']:.1f}с")
            
            print("\nОбщая статистика:")
            print(f"  Всего игр: {stats['total_games']}")
            print(f"  Мат: {stats['checkmate']} ({stats['checkmate']/stats['total_games']*100:.1f}%)")
            print(f"    - Победы белых: {stats['white_wins']}")
            print(f"    - Победы черных: {stats['black_wins']}")
            print(f"  Пат: {stats['stalemate']} ({stats['stalemate']/stats['total_games']*100:.1f}%)")
            print(f"  Лимит ходов: {stats['max_moves']}")
            print(f"  Среднее ходов в партии: {stats['total_moves']/stats['total_games']:.1f}")
            print(f"  Среднее время партии: {stats['total_time']/stats['total_games']:.1f}с")
            print(f"  Размер кэша: {len(ai.move_cache)} позиций")
            print("-"*60)
            
            if result['result'] == 'interrupted':
                break
    
    except KeyboardInterrupt:
        print("\n\nПолучен сигнал прерывания...")
    
    finally:
        # Финальное сохранение кэша
        print("\n" + "="*60)
        print("Сохранение кэша в базу данных...")
        ai.save_move_cache_to_db(ai.move_cache)
        
        training_duration = time.time() - training_start
        
        print("\n" + "="*60)
        print("ФИНАЛЬНАЯ СТАТИСТИКА")
        print("="*60)
        print(f"Всего игр: {stats['total_games']}")
        print(f"Время обучения: {training_duration/60:.1f} минут")
        if stats['total_games'] > 0:
            print(f"\nРезультаты:")
            print(f"  Мат: {stats['checkmate']} ({stats['checkmate']/stats['total_games']*100:.1f}%)")
            print(f"    - Победы белых: {stats['white_wins']}")
            print(f"    - Победы черных: {stats['black_wins']}")
            print(f"  Пат: {stats['stalemate']} ({stats['stalemate']/stats['total_games']*100:.1f}%)")
            print(f"  Лимит ходов: {stats['max_moves']}")
            print(f"  Ошибки: {stats['errors']}")
            print(f"  Прервано: {stats['interrupted']}")
            print(f"\nСтатистика игры:")
            print(f"  Среднее ходов: {stats['total_moves']/stats['total_games']:.1f}")
            print(f"  Среднее время партии: {stats['total_time']/stats['total_games']:.1f}с")
            print(f"  Всего ходов: {stats['total_moves']}")
        print(f"\nРазмер кэша: {len(ai.move_cache)} позиций")
        print("="*60)


def main():
    """Точка входа"""
    setup_signal_handlers()
    
    # Параметры самообучения
    num_games = None  # None = бесконечно, или укажите число
    depth = 6         # Глубина поиска (можно уменьшить если очень долго)
    exploration_rate = 0.2  # 20% вероятность выбора 2-го лучшего хода
    
    run_self_play_training(num_games, depth, exploration_rate)


if __name__ == "__main__":
    main()
