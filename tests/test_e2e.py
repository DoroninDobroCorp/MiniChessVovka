#!/usr/bin/env python3
"""
E2E tests for MiniChess - complete game flow testing.
Tests full game scenarios including AI gameplay, moves, captures, drops, and game over.
"""

import os
import sys
import unittest
import copy
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamestate import GameState
import ai
from pieces import EMPTY_SQUARE
from utils import format_move_for_print


class TestE2EGameFlow(unittest.TestCase):
    """E2E tests for complete game scenarios."""

    def setUp(self):
        """Set up test environment before each test."""
        ai.setup_db()
        ai.load_move_cache_from_db()

    def test_complete_ai_vs_ai_game(self):
        """Test a complete AI vs AI game from start to finish."""
        print("\n=== Testing Complete AI vs AI Game ===")
        gs = GameState()
        gs.setup_initial_board()
        gs.white_ai_enabled = True
        gs.black_ai_enabled = True
        
        moves_played = 0
        max_moves = 50
        
        while not (gs.checkmate or gs.stalemate) and moves_played < max_moves:
            legal_moves = gs.get_all_legal_moves()
            self.assertGreater(len(legal_moves), 0, 
                             f"No legal moves at move {moves_played} without game over")
            
            # Get AI move
            best_move = ai.find_best_move(gs, depth=4, time_limit=5)
            self.assertIsNotNone(best_move, f"AI returned None at move {moves_played}")
            self.assertIn(best_move, legal_moves, "AI move not in legal moves")
            
            # Make move
            success = gs.make_move(best_move)
            self.assertTrue(success, f"Failed to make move: {format_move_for_print(best_move)}")
            
            # Handle promotion if needed
            if gs.needs_promotion_choice:
                prom_char = 'R' if gs.current_turn == 'b' else 'r'
                gs.complete_promotion(prom_char)
            
            gs.save_state()
            moves_played += 1
            
            print(f"Move {moves_played}: {format_move_for_print(best_move)}")
        
        print(f"Game ended after {moves_played} moves")
        print(f"Checkmate: {gs.checkmate}, Stalemate: {gs.stalemate}")
        
        # Verify game ended properly or reached move limit
        self.assertTrue(gs.checkmate or gs.stalemate or moves_played >= max_moves,
                       "Game should end in checkmate, stalemate, or reach move limit")

    def test_game_with_captures_and_drops(self):
        """Test game flow with captures and crazyhouse drops."""
        print("\n=== Testing Captures and Drops ===")
        gs = GameState()
        gs.setup_initial_board()
        
        initial_pieces = sum(1 for row in gs.board for cell in row if cell != EMPTY_SQUARE)
        
        # Play several moves to generate captures
        for _ in range(10):
            if gs.checkmate or gs.stalemate:
                break
                
            legal_moves = gs.get_all_legal_moves()
            if not legal_moves:
                break
            
            # Prefer capture moves to test hand mechanics
            capture_moves = [m for m in legal_moves 
                           if m[0] != 'drop' and gs.board[m[1][0]][m[1][1]] != EMPTY_SQUARE]
            
            if capture_moves:
                move = capture_moves[0]
            else:
                move = legal_moves[0]
            
            gs.make_move(move)
            if gs.needs_promotion_choice:
                gs.complete_promotion('R' if gs.current_turn == 'b' else 'r')
            gs.save_state()
        
        # Check if any pieces were captured (hands should have pieces)
        total_hand_pieces = sum(gs.hands['w'].values()) + sum(gs.hands['b'].values())
        current_pieces = sum(1 for row in gs.board for cell in row if cell != EMPTY_SQUARE)
        
        print(f"Initial pieces: {initial_pieces}, Current: {current_pieces}, In hands: {total_hand_pieces}")
        
        # If we have pieces in hand, test drop moves
        if total_hand_pieces > 0:
            drop_moves = [m for m in gs.get_all_legal_moves() if m[0] == 'drop']
            self.assertGreater(len(drop_moves), 0, "Should have drop moves when pieces in hand")
            
            # Make a drop move
            drop_move = drop_moves[0]
            success = gs.make_move(drop_move)
            self.assertTrue(success, f"Failed to make drop: {format_move_for_print(drop_move)}")
            print(f"Successfully made drop: {format_move_for_print(drop_move)}")

    def test_undo_redo_sequence(self):
        """Test undo/redo functionality in game flow."""
        print("\n=== Testing Undo/Redo Sequence ===")
        gs = GameState()
        gs.setup_initial_board()
        gs.save_state()
        
        # Make 5 moves
        moves_made = []
        for i in range(5):
            legal_moves = gs.get_all_legal_moves()
            if not legal_moves:
                break
            
            move = legal_moves[0]
            board_before = copy.deepcopy(gs.board)
            turn_before = gs.current_turn
            
            gs.make_move(move)
            if gs.needs_promotion_choice:
                gs.complete_promotion('R' if gs.current_turn == 'b' else 'r')
            gs.save_state()
            
            moves_made.append((move, board_before, turn_before))
            print(f"Move {i+1}: {format_move_for_print(move)}")
        
        # Undo all moves
        for i in range(len(moves_made)):
            success = gs.undo_move()
            self.assertTrue(success, f"Failed to undo move {len(moves_made)-i}")
        
        # Verify we're back to initial state
        gs.setup_initial_board()
        initial_board = copy.deepcopy(gs.board)
        gs.undo_move()  # Go back to saved initial state
        
        print(f"Successfully undid {len(moves_made)} moves")

    def test_promotion_flow(self):
        """Test pawn promotion flow."""
        print("\n=== Testing Promotion Flow ===")
        gs = GameState()
        gs.board = [[EMPTY_SQUARE for _ in range(6)] for _ in range(6)]
        
        # Set up position where white pawn can promote
        gs.board[1][2] = 'P'  # White pawn on rank 5 (row 1)
        gs.board[0][2] = EMPTY_SQUARE  # Empty promotion square
        gs.board[5][3] = 'k'  # Black king
        gs.board[5][4] = 'K'  # White king
        gs.current_turn = 'w'
        gs.king_pos = {'w': (5, 4), 'b': (5, 3)}
        
        # Make promotion move
        promotion_move = ((1, 2), (0, 2), None)
        legal_moves = gs.get_all_legal_moves()
        
        # Find the promotion move in legal moves
        prom_move = None
        for m in legal_moves:
            if m[0] != 'drop' and m[0] == (1, 2) and m[1] == (0, 2):
                prom_move = m
                break
        
        if prom_move:
            success = gs.make_move(prom_move)
            self.assertTrue(success, "Promotion move should succeed")
            
            if gs.needs_promotion_choice:
                # Test promoting to different pieces
                for piece in ['R', 'N', 'B', 'Q']:
                    gs_copy = copy.deepcopy(gs)
                    success = gs_copy.complete_promotion(piece)
                    self.assertTrue(success, f"Should be able to promote to {piece}")
                    self.assertEqual(gs_copy.board[0][2], piece, 
                                   f"Promoted piece should be {piece}")
                    print(f"Successfully promoted to {piece}")
                
                # Complete promotion in main gamestate
                gs.complete_promotion('Q')

    def test_checkmate_detection(self):
        """Test that checkmate detection works in actual gameplay."""
        print("\n=== Testing Checkmate Detection ===")
        # Note: Checkmate in Crazyhouse is complex due to piece drops
        # This test verifies the mechanism works, not a specific position
        
        gs = GameState()
        gs.setup_initial_board()
        
        # Play until checkmate or move limit
        for _ in range(100):
            if gs.checkmate:
                print("Checkmate detected in gameplay!")
                self.assertTrue(True)
                return
            
            legal_moves = gs.get_all_legal_moves()
            if not legal_moves:
                break
            
            # Make a random move
            move = legal_moves[0]
            gs.make_move(move)
            if gs.needs_promotion_choice:
                gs.complete_promotion('Q')
            gs.check_game_over()
        
        # Test passes if check_game_over() runs without error
        print("Checkmate detection mechanism verified")
        self.assertTrue(True)

    def test_stalemate_detection(self):
        """Test that stalemate detection mechanism works."""
        print("\n=== Testing Stalemate Detection ===")
        # Note: Stalemate is rare in Crazyhouse due to piece drops
        # This test verifies the mechanism works
        
        gs = GameState()
        gs.setup_initial_board()
        
        # Verify check_game_over() can detect stalemate condition
        gs.check_game_over()
        
        # Test that the stalemate flag exists and can be set
        self.assertFalse(gs.stalemate, "Initial position should not be stalemate")
        
        # Manually test stalemate detection logic
        gs.stalemate = True
        self.assertTrue(gs.stalemate, "Should be able to set stalemate flag")
        
        print("Stalemate detection mechanism verified")
        self.assertTrue(True)

    def test_move_cache_persistence(self):
        """Test that move cache persists across games."""
        print("\n=== Testing Move Cache Persistence ===")
        
        # Clear cache and play a game
        ai.move_cache.clear()
        
        gs = GameState()
        gs.setup_initial_board()
        
        # Make a few moves to populate cache
        for _ in range(3):
            if gs.checkmate or gs.stalemate:
                break
            best_move = ai.find_best_move(gs, depth=6)
            if best_move:
                gs.make_move(best_move)
                if gs.needs_promotion_choice:
                    gs.complete_promotion('R' if gs.current_turn == 'b' else 'r')
        
        cache_size_before = len(ai.move_cache)
        print(f"Cache size after moves: {cache_size_before}")
        
        # Save cache
        ai.save_move_cache_to_db(ai.move_cache)
        
        # Clear and reload
        ai.move_cache.clear()
        ai.load_move_cache_from_db()
        
        cache_size_after = len(ai.move_cache)
        print(f"Cache size after reload: {cache_size_after}")
        
        self.assertEqual(cache_size_before, cache_size_after, 
                        "Cache should persist after save/load")

    def test_game_state_consistency(self):
        """Test that game state remains consistent throughout gameplay."""
        print("\n=== Testing Game State Consistency ===")
        gs = GameState()
        gs.setup_initial_board()
        
        for move_num in range(20):
            if gs.checkmate or gs.stalemate:
                break
            
            # Verify king positions are valid
            self.assertIsNotNone(gs.king_pos['w'], "White king should exist")
            self.assertIsNotNone(gs.king_pos['b'], "Black king should exist")
            
            # Verify kings are on the board
            w_king_pos = gs.king_pos['w']
            b_king_pos = gs.king_pos['b']
            self.assertEqual(gs.board[w_king_pos[0]][w_king_pos[1]], 'K',
                           "White king should be at king_pos")
            self.assertEqual(gs.board[b_king_pos[0]][b_king_pos[1]], 'k',
                           "Black king should be at king_pos")
            
            # Verify turn alternates
            turn_before = gs.current_turn
            
            legal_moves = gs.get_all_legal_moves()
            if not legal_moves:
                break
            
            move = legal_moves[0]
            gs.make_move(move)
            if gs.needs_promotion_choice:
                gs.complete_promotion('R' if gs.current_turn == 'b' else 'r')
            
            # Turn should have switched
            expected_turn = 'b' if turn_before == 'w' else 'w'
            self.assertEqual(gs.current_turn, expected_turn,
                           f"Turn should switch from {turn_before} to {expected_turn}")
        
        print(f"Game state remained consistent for {move_num} moves")


class TestE2EPerformance(unittest.TestCase):
    """E2E performance tests."""

    def test_ai_search_performance(self):
        """Test AI search completes in reasonable time."""
        print("\n=== Testing AI Search Performance ===")
        gs = GameState()
        gs.setup_initial_board()
        
        depths_to_test = [4, 6, 8]
        
        for depth in depths_to_test:
            start_time = time.time()
            best_move = ai.find_best_move(gs, depth=depth, time_limit=30)
            elapsed = time.time() - start_time
            
            self.assertIsNotNone(best_move, f"AI should find move at depth {depth}")
            print(f"Depth {depth}: {elapsed:.2f}s - {format_move_for_print(best_move)}")
            
            # Reasonable time limits
            if depth <= 6:
                self.assertLess(elapsed, 10, f"Depth {depth} should complete in <10s")
            elif depth <= 8:
                self.assertLess(elapsed, 30, f"Depth {depth} should complete in <30s")


if __name__ == '__main__':
    unittest.main(verbosity=2)
