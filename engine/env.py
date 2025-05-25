import numpy as np
import torch
from gamestate import GameState
from pieces import EMPTY_SQUARE

class MiniChessEnv:
    """
    Environment wrapper around GameState for RL training.
    Implements reset(), step(), legal_moves(), render(), observation encoding.
    """
    def __init__(self):
        self.state = GameState()
        self.state.setup_initial_board()

    def reset(self):
        """Reset the game to the initial position."""
        self.state.reset_board()
        return self._get_observation()

    def step(self, move):
        """
        Apply move.
        move: internal move representation used by GameState.make_move
        Returns: obs (tensor), reward (float), done (bool), info (dict)
        """
        success = self.state.make_move(move)
        if not success:
            raise ValueError(f"Illegal move: {move}")
        obs = self._get_observation()
        done = self.state.checkmate or self.state.stalemate
        if self.state.checkmate:
            # Winner is the player who just moved
            reward = 1.0
        elif self.state.stalemate:
            reward = 0.0
        else:
            reward = 0.0
        return obs, reward, done, {}

    def legal_moves(self):
        """Return list of legal moves in current state."""
        return self.state.get_all_legal_moves()

    def render(self):
        """Render the board (text)."""
        for row in self.state.board:
            print(' '.join(row))
        print(f"Turn: {self.state.current_turn}")

    def _get_observation(self):
        """
        Encode board to tensor of shape (C, H, W).
        Channels: 6 piece types * 2 colors + 1 turn plane.
        """
        board = self.state.board
        size = len(board)
        C = 6 * 2 + 1
        obs = np.zeros((C, size, size), dtype=np.float32)
        # piece plane mapping
        piece_map = {'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5}
        for r in range(size):
            for c in range(size):
                p = board[r][c]
                if p == EMPTY_SQUARE:
                    continue
                color = 'w' if p.isupper() else 'b'
                idx = piece_map[p.upper()]
                plane = idx + (0 if color == 'w' else 6)
                obs[plane, r, c] = 1.0
        # turn plane
        turn_plane = 12
        obs[turn_plane, :, :] = 1.0 if self.state.current_turn == 'w' else 0.0
        return torch.from_numpy(obs)
