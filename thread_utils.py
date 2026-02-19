# -*- coding: utf-8 -*-
import threading
import copy
import time
import traceback
from ai import find_best_move
from utils import format_move_for_print


class AIThread(threading.Thread):
    def __init__(self, gamestate, depth):
        threading.Thread.__init__(self)
        self.gamestate = copy.deepcopy(gamestate)
        self.depth = depth
        self.best_move = None
        self.done = False
        self.name = f"AIThread-{gamestate.current_turn}-D{depth:.0f}-Move-{time.time():.0f}"
        self.daemon = True

    def run(self):
        try:
            task_type = 'move'
            print(f"Starting AI {task_type} calculation in thread: {self.name}")

            self.best_move = find_best_move(self.gamestate, self.depth)
            move_str = format_move_for_print(self.best_move)
            print(f"AI thread {self.name} finished. Best {task_type}: {move_str}")
        except Exception as e:
            print(f"!!! EXCEPTION in AI thread {self.name}: {e}")
            traceback.print_exc()
            self.best_move = None
        finally:
            self.done = True
