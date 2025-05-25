# -*- coding: utf-8 -*-
import threading
import copy
import time
import traceback
from ai import find_best_move # Import the AI function
from utils import format_move_for_print # For logging


# Class for running AI calculations in a separate thread
class AIThread(threading.Thread):
    def __init__(self, gamestate, depth):
        threading.Thread.__init__(self)
        self.gamestate = copy.deepcopy(gamestate)  # Use a deep copy of the state
        self.depth = depth
        self.best_move = None
        self.done = False
        self.name = f"AIThread-{gamestate.current_turn}-D{depth}-Move-{time.time():.0f}"
        self.daemon = True  # Allows program to exit even if thread is running

    def run(self):
        """The main logic executed by the thread."""
        try:
            task_type = "move"
            print(f"Starting AI {task_type} calculation in thread: {self.name}")
            # Call the AI function (imported from ai.py)
            self.best_move = find_best_move(self.gamestate, self.depth)
            move_str = format_move_for_print(self.best_move)
            print(f"AI thread {self.name} finished. Best {task_type}: {move_str}")
        except Exception as e:
            print(f"!!! EXCEPTION in AI thread {self.name}: {e}")
            traceback.print_exc()
            self.best_move = None # Ensure best_move is None on error
        finally:
            self.done = True # Signal that the thread has completed