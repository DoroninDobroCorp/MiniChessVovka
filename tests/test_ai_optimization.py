
import sys
import os
import time
import copy
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from gamestate import GameState
import ai
from pieces import EMPTY_SQUARE

def test_undo_reliability():
    print("Testing make_ai_move / undo_ai_move reliability...")
    gs = GameState()
    gs.setup_initial_board()
    
    original_board = copy.deepcopy(gs.board)
    original_hands = copy.deepcopy(gs.hands)
    original_turn = gs.current_turn
    
    # Get a move
    moves = gs.get_all_legal_moves()
    if not moves:
        print("No moves to test!")
        return False
        
    move = moves[0]
    print(f"Applying move: {move}")
    
    # Apply
    gs.make_ai_move(move)
    
    # Check something changed
    if gs.current_turn == original_turn:
        print("FAIL: Turn did not switch after make_ai_move")
        return False
        
    # Undo
    print("Undoing move...")
    gs.undo_ai_move()
    
    # Verify restoration
    if gs.current_turn != original_turn:
        print(f"FAIL: Turn not restored. Expected {original_turn}, got {gs.current_turn}")
        return False
        
    if gs.board != original_board:
        print("FAIL: Board not restored correctly")
        # print(f"Original: {original_board}")
        # print(f"Current:  {gs.board}")
        return False
        
    if gs.hands != original_hands:
        print("FAIL: Hands not restored correctly")
        return False
        
    print("PASS: Undo reliability test passed.")
    return True

def test_ai_search():
    print("\nTesting AI search (find_best_move)...")
    gs = GameState()
    gs.setup_initial_board()
    
    start_time = time.time()
    # Depth 2 should be fast but exercise the recursion and parallel logic
    best_move = ai.find_best_move(gs, depth=2)
    duration = time.time() - start_time
    
    print(f"AI returned move: {best_move}")
    print(f"Time taken: {duration:.4f}s")
    
    assert best_move is not None, "AI did not return a move"
    print("PASS: AI found a move.")


def test_ai_vs_ai_game():
    """Regression test: play 10 moves of AI vs AI and verify correctness."""
    print("\nTesting AI vs AI game (10 moves, depth 4)...")
    gs = GameState()
    gs.setup_initial_board()
    
    original_board = copy.deepcopy(gs.board)
    
    for move_num in range(10):
        is_max = gs.current_turn == 'w'
        score, best_move = ai.minimax_alpha_beta(
            gs, 4, -float('inf'), float('inf'), is_max)
        
        if not best_move:
            # Game may be over
            break
        
        # Verify move is legal
        legal_moves = gs.get_all_legal_moves()
        assert best_move in legal_moves, f"Move {best_move} not in legal moves"
        
        gs.make_ai_move(best_move)
        gs._all_legal_moves_cache = None
        gs.check_game_over()
        
        if gs.checkmate or gs.stalemate:
            break
    
    # Verify game state is consistent
    assert gs.king_pos['w'] is not None, "White king missing"
    assert gs.king_pos['b'] is not None or gs.checkmate, "Black king missing without checkmate"
    
    # Verify board is different from start (game progressed)
    assert gs.board != original_board, "Board unchanged after 10 moves"
    print("PASS: AI vs AI game completed correctly.")


def test_search_speed():
    """Test that depth 6 completes in reasonable time after optimizations."""
    print("\nTesting search speed at depth 6...")
    gs = GameState()
    gs.setup_initial_board()
    
    ai.tt.clear()
    start = time.time()
    score, best_move = ai.minimax_alpha_beta(
        gs, 6, -float('inf'), float('inf'), True)
    elapsed = time.time() - start
    
    print(f"Depth 6: move={best_move}, score={score}, time={elapsed:.2f}s")
    assert best_move is not None, "No move found at depth 6"
    assert elapsed < 30, f"Depth 6 took {elapsed:.2f}s, expected <30s"
    print(f"PASS: Depth 6 completed in {elapsed:.2f}s.")

if __name__ == "__main__":
    test_undo_reliability()
    test_ai_search()
    test_ai_vs_ai_game()
    test_search_speed()
