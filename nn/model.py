import torch
import torch.nn as nn
import torch.nn.functional as F

class PolicyValueNet(nn.Module):
    """
    Policy-Value Network for MiniChess.
    Input: tensor (batch, C, H, W)
    Outputs:
      - policy_logits: (batch, action_size)
      - value: (batch,)
    """
    def __init__(self, board_size, in_channels=13, hidden_dim=128):
        super(PolicyValueNet, self).__init__()
        self.board_size = board_size
        self.action_size = board_size**4  # from-square * to-square
        # convolutional layers
        self.conv1 = nn.Conv2d(in_channels, hidden_dim, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(hidden_dim)
        self.conv2 = nn.Conv2d(hidden_dim, hidden_dim*2, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(hidden_dim*2)
        self.conv3 = nn.Conv2d(hidden_dim*2, hidden_dim, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(hidden_dim)
        # policy head
        self.policy_fc = nn.Linear(hidden_dim * board_size * board_size, self.action_size)
        # value head
        self.value_fc1 = nn.Linear(hidden_dim * board_size * board_size, hidden_dim)
        self.value_fc2 = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        # x: (batch, C, H, W)
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        bsz = x.size(0)
        flat = x.view(bsz, -1)
        # policy logits
        policy_logits = self.policy_fc(flat)
        # value
        v = F.relu(self.value_fc1(flat))
        value = torch.tanh(self.value_fc2(v)).squeeze(-1)
        return policy_logits, value
