import math
import copy
from collections import defaultdict

def softmax(x):
    max_x = max(x)
    exps = [math.exp(i - max_x) for i in x]
    s = sum(exps)
    return [j / s for j in exps]

class MCTSNode:
    def __init__(self, state, prior):
        self.state = state
        self.prior = prior  # P(s,a)
        self.children = {}  # move -> MCTSNode
        self.N = 0          # visits
        self.W = 0.0        # total value
        self.Q = 0.0        # mean value W/N

class MCTS:
    def __init__(self, policy_value_fn, c_puct=1.0, n_iters=1000):
        """
        policy_value_fn: function(state) -> (action_probs, value)
          action_probs: list of (move, probability)
          value: scalar in [-1,1]
        """
        self.policy_value_fn = policy_value_fn
        self.c_puct = c_puct
        self.n_iters = n_iters
        self.root = None

    def search(self, initial_state):
        """Run MCTS starting from initial_state."""
        self.root = MCTSNode(state=initial_state, prior=1.0)
        for _ in range(self.n_iters):
            node = self.root
            path = []
            # selection
            while node.children:
                move, node = max(
                    node.children.items(),
                    key=lambda item: item[1].Q + self.c_puct * item[1].prior * math.sqrt(node.N) / (1 + item[1].N)
                )
                path.append((node, move))
            # expansion
            state = node.state
            action_probs, value = self.policy_value_fn(state)
            for move, prob in action_probs:
                next_state = copy.deepcopy(state)
                next_state.make_move(move)
                node.children[move] = MCTSNode(next_state, prior=prob)
            # backpropagation
            for parent, _move in reversed(path):
                parent.N += 1
                parent.W += value
                parent.Q = parent.W / parent.N
            # update root N
            self.root.N += 1
        # return action distribution
        moves, visits = zip(*[(move, child.N) for move, child in self.root.children.items()])
        probs = softmax(visits)
        return list(zip(moves, probs))

    def get_best_move(self, temperature=1e-3):
        """Return the move with highest visit count if temperature low, else sample."""
        visits = [(move, child.N) for move, child in self.root.children.items()]
        moves, Ns = zip(*visits)
        if temperature < 1e-3:
            best = moves[Ns.index(max(Ns))]
            return best
        else:
            dist = softmax([n**(1/temperature) for n in Ns])
            # sample
            import random
            return random.choices(moves, weights=dist)[0]
