# -*- coding: utf-8 -*-
import sys
import time
from gamestate import GameState
import ai
from utils import format_move_for_print


def main():
    depth = 6
    if len(sys.argv) >= 2:
        try:
            depth = int(sys.argv[1])
        except Exception:
            pass
    gs = GameState()
    gs.setup_initial_board()
    t0 = time.time()
    mv = ai.find_best_move(gs, depth=depth)
    dt = time.time() - t0
    print(f"Best move at depth {depth}: {format_move_for_print(mv)} in {dt:.2f}s")


if __name__ == "__main__":
    main()
