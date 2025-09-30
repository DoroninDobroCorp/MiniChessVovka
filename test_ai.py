#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования AI без GUI
"""
import sys
import time
from gamestate import GameState
import ai

def test_ai_performance():
    """Тестирует производительность и силу AI"""
    print("=" * 60)
    print("Тест AI для Mini Chess 6x6 Crazyhouse")
    print("=" * 60)
    
    # Загружаем кэш
    ai.load_move_cache_from_db()
    
    # Создаём игру
    gs = GameState()
    gs.setup_initial_board()
    gs.black_ai_enabled = True
    gs.white_ai_enabled = True
    
    print(f"\nНачальная позиция:")
    print_board(gs)
    
    move_count = 0
    max_moves = 50  # Ограничение на количество ходов
    
    print(f"\nЗапуск AI vs AI игры (максимум {max_moves} ходов)...")
    print("-" * 60)
    
    start_time = time.time()
    
    while not gs.checkmate and not gs.stalemate and move_count < max_moves:
        move_count += 1
        current_player = "White" if gs.current_turn == 'w' else "Black"
        
        print(f"\nХод {move_count}: {current_player} думает...")
        
        move_start = time.time()
        best_move = ai.find_best_move(gs, depth=gs.ai_depth)
        move_time = time.time() - move_start
        
        if not best_move:
            print(f"AI не нашёл хода! Игра окончена.")
            break
        
        print(f"  Время на ход: {move_time:.2f}с")
        print(f"  Выбранный ход: {best_move}")
        
        if not gs.make_move(best_move):
            print(f"Ошибка выполнения хода! Игра окончена.")
            break
        
        # Автоматическое превращение пешки если нужно
        if gs.needs_promotion_choice:
            promo_piece = 'Q' if gs.current_turn == 'b' else 'q'  # Противоположный цвет, так как ход уже сделан
            gs.complete_promotion(promo_piece)
        
        gs.save_state()
        
        # Периодически показываем позицию
        if move_count % 10 == 0:
            print(f"\nПозиция после {move_count} ходов:")
            print_board(gs)
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("Результат игры")
    print("=" * 60)
    print(f"Всего ходов: {move_count}")
    print(f"Общее время: {total_time:.2f}с")
    print(f"Среднее время на ход: {total_time/move_count:.2f}с")
    
    if gs.checkmate:
        winner = "White" if gs.current_turn == 'b' else "Black"
        print(f"Мат! Победили {winner}")
    elif gs.stalemate:
        print("Пат! Ничья")
    else:
        print(f"Игра прервана после {move_count} ходов")
    
    print("\nФинальная позиция:")
    print_board(gs)
    
    # Сохраняем кэш
    ai.save_move_cache_to_db(ai.move_cache)
    print(f"\nКэш сохранён: {len(ai.move_cache)} позиций")

def print_board(gs):
    """Выводит доску в консоль"""
    print("  ", end="")
    for f in range(6):
        print(f" {chr(ord('a')+f)}", end="")
    print()
    
    for r in range(6):
        print(f"{6-r} ", end="")
        for f in range(6):
            piece = gs.board[r][f]
            print(f" {piece if piece != '.' else '·'}", end="")
        print(f" {6-r}")
    
    print("  ", end="")
    for f in range(6):
        print(f" {chr(ord('a')+f)}", end="")
    print()
    
    # Показываем руки
    print(f"White hand: {gs.hands.get('w', {})}")
    print(f"Black hand: {gs.hands.get('b', {})}")

if __name__ == "__main__":
    try:
        test_ai_performance()
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nОшибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
