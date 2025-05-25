from engine.env import MiniChessEnv
from pieces import EMPTY_SQUARE

FILES = 'abcdefgh'

class TextEnv(MiniChessEnv):
    """
    Headless text-based environment for mini-chess.
    Inherits game logic from GameState and allows text I/O.
    """
    def render(self):
        """Print board and current turn."""
        for row in self.state.board:
            print(' '.join(row))
        print(f"Turn: {self.state.current_turn}")

    @staticmethod
    def parse(move_str: str):
        """
        Parse move from algebraic coords, e.g. 'a2a4' or with promotion 'a7a8Q'.
        Returns a tuple ((r1,f1),(r2,f2),promotion_choice).
        """
        s = move_str.strip()
        if len(s) < 4:
            raise ValueError(f"Invalid move string: '{s}'")
        f1 = FILES.index(s[0])
        r1 = len(self.state.board) - int(s[1])
        f2 = FILES.index(s[2])
        r2 = len(self.state.board) - int(s[3])
        promo = None
        if len(s) == 5:
            promo = s[4].upper()
        return ((r1, f1), (r2, f2), promo)

if __name__ == '__main__':
    import argparse
    import torch
    from nn.model import PolicyValueNet
    from nn.mcts import MCTS
    from utils import format_move_for_print
    from self_play import policy_value_fn
    from config import BOARD_SIZE

    parser = argparse.ArgumentParser(description="Play against the trained AI")
    parser.add_argument('--model-path', type=str, default='model.pth')
    parser.add_argument('--mcts-iters', type=int, default=50)
    parser.add_argument('--c-puct', type=float, default=1.0)
    parser.add_argument('--human-color', choices=['w','b'], default='w')
    args = parser.parse_args()

    # Load model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = PolicyValueNet(BOARD_SIZE).to(device)
    model.load_state_dict(torch.load(args.model_path, map_location=device))
    model.eval()

    env = TextEnv()
    env.reset()
    human = args.human_color

    while True:
        env.render()
        current = env.state.current_turn
        if current == human:
            move_str = input("Your move: ")
            try:
                move = TextEnv.parse(move_str)
                _, reward, done, _ = env.step(move)
            except Exception as e:
                print("Invalid move:", e)
                continue
        else:
            mcts = MCTS(lambda s: policy_value_fn(s, model, device),
                        c_puct=args.c_puct, n_iters=args.mcts_iters)
            mcts.search(env.state)
            move = mcts.get_best_move(temperature=1e-3)
            print("AI move:", format_move_for_print(move))
            _, reward, done, _ = env.step(move)
        if done:
            env.render()
            if reward == 1.0:
                print("Game over. Winner:", "You" if current == human else "AI")
            else:
                print("Game over. Draw")
            break
