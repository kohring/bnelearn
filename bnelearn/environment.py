## false positive on torch.tensor
#pylint: disable=E1102
#pylint: disable=E0611
from collections import Iterable, deque
#pylint: enable=E0611

from abc import ABC, abstractmethod
from typing import Callable

import torch

from bnelearn.bidder import Player, Bidder, MatrixGamePlayer
from bnelearn.mechanism import Mechanism, MatrixGame
from bnelearn.strategy import Strategy

dynamic = object()


class Environment(ABC):
    def __init__(self,
                 agents: Iterable,
                 n_players=2,
                 batch_size=1,
                 strategy_to_player_closure: Callable or None=None,
                 **kwargs
                 ):
        assert isinstance(agents, Iterable), "iterable of agents must be supplied"

        self._strategy_to_player = strategy_to_player_closure
        self.batch_size = batch_size
        self.n_players = n_players

        # transform agents into players, if specified as Strategies:
        agents = [
            self._strategy_to_player(agent, batch_size, player_position) if isinstance(agent, Strategy) else agent
            for player_position, agent in enumerate(agents)
        ]
        self.agents: Iterable[Player] = agents

    @abstractmethod
    def get_reward(self, agent: Player or Strategy, **kwargs):
        pass
    
    def _generate_agent_actions(self, **kwargs):
        for agent in self.agents:
            yield agent.get_action()

    def prepare_iteration(self):
        """Prepares the interim-stage of a Bayesian game,
            (e.g. in an Auction, draw bidders' valuations)
        """
        pass

    def size(self):
        """Returns the number of agents/opponent setups in the environment.""" 
        return len(self.agents)
    
    def is_empty(self):
        """True if no agents in the environment"""
        return len(self.agents) == 0


class MatrixGameEnvironment(Environment):
    """ An environment for matrix games.
    
        Important features of matrix games for implementation:
        - not necessarily symmetric, i.e. each player has a fixed position
        - agents strategies do not take any input, the actions only depend
           on the game itself (no Bayesian Game)
    """

    def __init__(self,
                 game: MatrixGame,
                 agents,
                 n_players=2,
                 batch_size=1, 
                 strategy_to_player_closure=None,
                 **kwargs):

        super().__init__(agents, n_players=n_players, batch_size=batch_size,
                         strategy_to_player_closure=strategy_to_player_closure)
        
        self.game = game

    def _generate_agent_actions(self, exclude=set(), **kwargs):
        """
            Method for generating actions of all players in the environment

            args:
                exclude: A set of player positions to exclude.
        """
        for agent in (a for a in self.agents if a.player_position not in exclude):
            yield (agent.player_position, agent.get_action())


    def get_reward(self, agent, player_position, **kwargs):
        """
            What should be the dimension of reward?
        """


        if isinstance(agent, Strategy):
            agent: MatrixGamePlayer = self._strategy_to_player(
                    agent,
                    batch_size=self.batch_size,
                    player_position=player_position
                    )
        
        #redundant, since matrix game doesn't need any preparation
        agent.prepare_iteration()

        action_profile = torch.zeros(self.batch_size, self.game.n_players,
                                     dtype=torch.long, device=agent.device)
        
        action_profile[:, player_position] = agent.get_action().view(self.batch_size)
        
        for opponent_action in self._generate_agent_actions(exclude = set([player_position])):
            position, action = opponent_action
            action_profile[:, position] = action.view(self.batch_size)
        
        allocation, payments = self.game.play(action_profile.view(self.batch_size, self.n_players, -1))
        
        utilities =  agent.get_utility(allocation[:,player_position,:], payments[:,player_position])

        return utilities.mean()
        


class AuctionEnvironment(Environment):
    """
        An environment of agents to play against and evaluate strategies.

        In particular this means:
            - an iterable of sets of -i players that a strategy of a single player can be tested against
            - accept strategy as argument, then play batch_size rounds and return the reward
        
        Args:
        ... (TODO: document)

        strategy_to_bidder_closure: A closure (strategy, batch_size) -> Bidder to
            transform strategies into a Bidder compatible with the environment
    """

    def __init__(self, mechanism: Mechanism, agents: Iterable, max_env_size=None,
                 batch_size=100, n_players=2, strategy_to_bidder_closure: Callable=None):

        super().__init__(
            agents=agents,
            n_players=n_players,
            batch_size=batch_size,
            strategy_to_player_closure=strategy_to_bidder_closure
            )
        self.max_env_size = max_env_size

        # turn agents into deque TODO: might want to change this.
        self.agents = deque(self.agents, max_env_size)
        self.mechanism = mechanism

        # define alias
        self._strategy_to_bidder = self._strategy_to_player


    def get_reward(self, agent: Bidder or Strategy, draw_valuations=False, **kwargs):
        """Returns reward of a single player against the environment.
           Reward is calculated as average utility for each of the batch_size x env_size games
        """

        if isinstance(agent, Strategy):
            agent: Bidder = self._bidder_from_strategy(agent)
        
        # get a batch of bids for each player
        agent.batch_size = self.batch_size
        # draw valuations
        agent.prepare_iteration()
        agent_bid = agent.get_action()

        utility: torch.Tensor = torch.tensor(0.0, device=agent.device)

        
        if draw_valuations:
            self.draw_valuations_()

        for opponent_bid in self._generate_opponent_bids():
            # since auction mechanisms are symmetric, we'll define 'our' agent to have position 0
            allocation, payments = self.mechanism.play(
                torch.cat((agent_bid, opponent_bid), 1).view(self.batch_size, self.n_players, 1)
            )
            # average over batch against this opponent
            u = agent.get_utility(allocation[:,0,:], payments[:,0]).mean()
            utility.add_(u)

        # average over plays against all players in the environment
        utility.div_(self.size())

        return utility

    def prepare_iteration(self):
        self.draw_valuations_()

    def draw_valuations_(self):
        """
            Draws new valuations for each opponent-agent in the environment
        """
        for opponent in self.agents:            
            opponent.batch_size = self.batch_size
            if isinstance(opponent, Bidder):
                opponent.draw_valuations_()

    def push_agent(self, agent: Bidder or Strategy):
        """
            Add an agent to the environment, possibly pushing out the oldest one)
        """
        if isinstance(agent, Strategy):
            agent: Bidder = self._bidder_from_strategy(agent)

        self.agents.append(agent)


    def _bidder_from_strategy(self, strategy: Strategy):
        """ Transform a strategy into a player that plays that strategy """
        if self._strategy_to_bidder:
            return self._strategy_to_bidder(strategy, self.batch_size) 
        
        raise NotImplementedError()

    def _generate_agent_actions(self, **kwargs):
        return self._generate_agent_actions()

    def _generate_opponent_bids(self):
        """ Generator function yielding batches of bids for each player in environment agents"""
        for opponent in self.agents:
            yield opponent.get_action()


