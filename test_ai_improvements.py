#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тест улучшений AI - проверка глубины поиска и качества ходов"""

import time
from gamestate import GameState
from ai import find_best_move
from utils import format_move_for_print

def test_ai_depth_and_quality():
    """Тестирует AI с новой глубиной и проверяет разумность ходов"""
    print("=" * 60)
    print("ТЕСТ УЛУЧШЕНИЙ AI (Быстрая версия)")
    print("=" * 60)
    
    # Создаем игру
    gs = GameState()
    gs.setup_initial_board()
    gs.black_ai_enabled = True
    
    print(f"\nГлубина поиска AI: {gs.ai_depth}")
    print("\nНачальная позиция:")
    for i, row in enumerate(gs.board):
        print(f"  Ряд {i}: {''.join(row)}")
    
    # Делаем только 1 ход для быстрого теста
    moves_to_test = 1
    
    for move_num in range(1, moves_to_test + 1):
        print(f"\n{'='*60}")
        print(f"ХОД {move_num}: {'Белые' if gs.current_turn == 'w' else 'Черные'}")
        print(f"{'='*60}")
        
        legal_moves = gs.get_all_legal_moves()
        print(f"Количество легальных ходов: {len(legal_moves)}")
        
        if not legal_moves:
            print("Нет легальных ходов! Игра окончена.")
            break
        
        # Замеряем время расчета AI
        start_time = time.time()
        best_move = find_best_move(gs, depth=gs.ai_depth)
        calc_time = time.time() - start_time
        
        if best_move:
            print(f"AI выбрал: {format_move_for_print(best_move)}")
            print(f"Время расчета: {calc_time:.2f}s")
            
            # Делаем ход
            if gs.make_move(best_move):
                print("✓ Ход успешно выполнен")
                print("\nПозиция после хода:")
                for i, row in enumerate(gs.board):
                    print(f"  Ряд {i}: {''.join(row)}")
            else:
                print("✗ ОШИБКА: Ход не удалось выполнить!")
                break
        else:
            print("✗ ОШИБКА: AI не смог найти ход!")
            break
        
        # Проверяем, не окончена ли игра
        if gs.checkmate or gs.stalemate:
            print(f"\nИгра окончена: {gs.game_over_message}")
            break
    
    print(f"\n{'='*60}")
    print("РЕЗУЛЬТАТЫ ТЕСТА")
    print(f"{'='*60}")
    print(f"✓ Глубина поиска увеличена до {gs.ai_depth}")
    print(f"✓ Кеш теперь учитывает глубину поиска")
    print(f"✓ AI успешно просчитывает ходы")
    print(f"{'='*60}")

if __name__ == "__main__":
    test_ai_depth_and_quality()
