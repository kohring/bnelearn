from abc import ABC, abstractmethod

import torch
import torch.nn as nn

class Strategy(ABC):
    
    @abstractmethod
    def play(self):
        pass

class NeuralNetStrategy(Strategy, nn.Module):
    def __init__(self, input_length, depth_hidden_layer = 10):
        nn.Module.__init__(self)
        self.fc1 = nn.Linear(input_length, depth_hidden_layer)
        self.tanh1 = nn.Tanh()
        self.fc_out = nn.Linear(depth_hidden_layer, 1)

    def forward(self, x):
        x = self.fc1(x)
        x = self.tanh1(x)
        x = self.fc_out(x)

        return x
    
    def play(self,x):
        return self.forward(x)
    
    
