
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
    
    if best_move:
        print("PASS: AI found a move.")
        return True
    else:
        print("FAIL: AI did not return a move.")
        return False

if __name__ == "__main__":
    if test_undo_reliability():
        test_ai_search()
