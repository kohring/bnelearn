# -*- coding: utf-8 -*-

"""
This module implements games such as matrix games and auctions.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

#pylint: disable=E1102
import torch

# Type declarations
Outcome = Tuple[torch.Tensor, torch.Tensor]

class Game(ABC):
    """
    Base class for any kind of games
    """
    def __init__(self, cuda: bool=True):
        self.cuda = cuda and torch.cuda.is_available()
        self.device = 'cuda' if self.cuda else 'cpu'

    @abstractmethod
    def play(self, action_profile):
        """Play the game!"""
        # get actions from players and define outcome
        raise NotImplementedError()

class Mechanism(Game, ABC):
    """
    Auction Mechanism - Interpreted as a Bayesian game.
    A Mechanism collects bids from all players, then allocates available
    items as well as payments for each of the players.
    """

    def play(self, action_profile):
        return self.run(bids=action_profile)

    @abstractmethod
    def run(self, bids):
        """Alias for play for auction mechanisms"""
        raise NotImplementedError()

class MatrixGame(Game):
    """
    A complete information Matrix game.

    TODO: missing documentation
    """
    # pylint: disable=abstract-method
    def __init__(self, n_players: int, outcomes: torch.Tensor,
                 cuda: bool = True, names: dict = None, validate_inputs: bool = True):
        super().__init__(cuda)
        self.n_players = n_players
        self.validate_inputs = validate_inputs

        # validate and set outcomes

        self.outcomes = outcomes.float().to(self.device)
        # Outcome tensor should be [n_actions_p1, n_actions_p2, ..., n_actions_p_n, n_players]
        # n_actions_p1 is implicitly defined by outcome tensor. Other dimensions should match
        assert outcomes.dim() == n_players + 1
        assert outcomes.shape[-1] == n_players

        # TODO: validate names. i.e.
        #   * if single list, check if all players have same number of actions
        #   * otherwise, should provide list of lists (names for each player). validate that each list matches length
        self.names = names

    def get_player_name(self, player_id: int):
        """Returns readable name of player if provided."""
        if self.names and "players" in self.names.keys():
            return self.names["players"][player_id]

        return player_id

    def get_action_name(self, action_id: int):
        """Currently only works if all players have same action set!"""
        if self.names and "actions" in self.names.keys():
            return self.names["actions"][action_id]

        return action_id

    def _validate_action_input(self, action_profile: torch.Tensor) -> None:
        """Assert validity of a (pure) action profile

        An action profile should have shape of a mechanism (batch x players x items).
        In a matrix game it should therefore be (batch x players x 1).
        TODO: Each player's action should be a valid index for that player.

        Parameters
        ----------
        action_profile: torch.Tensor
        An action profile tensor to be tested.

        Returns
        -------
        (nothing)

        Raises
        ------
        AssertionError on invalid input.
        """

        assert action_profile.dim() == 3, "Bid matrix must be 3d (batch x players x items)"
        assert action_profile.dtype == torch.int64 and torch.all(action_profile >= 0), \
            "Actions must be integer indeces!"


        # pylint: disable=unused-variable
        batch_dim, player_dim, item_dim = 0, 1, 2
        batch_size, n_players, n_items = action_profile.shape

        assert n_items == 1, "only single action per player in matrix game setting"
        assert n_players == self.n_players, "one action per player must be provided"

        for i in range(n_players):
            assert torch.all(action_profile[:, i, :] < self.outcomes.shape[i]), \
                "Invalid action given for player {}".format(i)

    def play(self, action_profile):
        """Plays the game for a given action_profile.

        Parameters
        ----------
        action_profile: torch.Tensor
            Shape: (batch_size, n_players, n_items)
            n_items should be 1 for now. (This might change in the future to represent information sets!)
            Actions should be integer indices. #TODO: Ipmlement that they can also be action names!

            Mixed strategies are NOT allowed as input, sampling should happen in the player class.

        Returns
        -------
        (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
            allocation: tensor of dimension (n_batches x n_players x n_items),
                        In this setting, there's nothing to be allocated, so it will be all zeroes.
            payments:   tensor of dimension (n_batches x n_players)
                        Negative outcome/utility for each player.
        """
        if self.validate_inputs:
            self._validate_action_input(action_profile)

        # pylint: disable=unused-variable
        batch_dim, player_dim, item_dim = 0, 1, 2
        batch_size, n_players, n_items = action_profile.shape

        #move to gpu/cpu if needed
        action_profile = action_profile.to(self.device)
        action_profile = action_profile.view(batch_size, n_players)

        # allocation is a dummy and will always be 0 --> all utility is
        # represented by negative payments
        allocations = torch.zeros(batch_size, n_players, n_items, device=self.device)

        ## memory allocation and Loop replaced by equivalent vectorized version below:
        ## (keep old code as comment for readibility)
        #payments = torch.zeros(batch_size, n_players, device=self.device)
        #for batch in range(batch_size):
        #    for player in range(n_players):
        #        payments[batch, player] = -self.outcomes[action[batch, player1], ... action[batch, player_n]][player]

        # payment to "game master" is the negative outcome
        payments = -self.outcomes[
            [
                action_profile[:, i] for i in range(n_players)
            ]].view(batch_size, n_players)

        return (allocations, payments)

    def _validate_mixed_strategy_input(self, strategy_profile: List[torch.Tensor]) -> None:
        """Assert validity of strategy profile

            Parameters
            ----------
            action_profile: torch.Tensor
            An action profile tensor to be tested.

            Returns
            -------
            (nothing)

            Raises
            ------
            AssertionError on invalid input.
        """
        assert len(strategy_profile) == self.n_players, \
            "Invalid number of players in strategy profile!"

        for player, strategy in enumerate(strategy_profile):
            assert strategy.shape == torch.Size([self.outcomes.shape[player]]), \
                "Strategy contains invalid number of actions for player {}".format(player)
            # Check valid probabilities
            assert torch.equal(strategy.sum(), torch.tensor(1.0, device=self.device)), \
                "Probabilities must sum to 1 for player {}".format(player)
            assert torch.all(strategy >= 0.0), \
                "Probabilities must be positive for player {}".format(player)

    def _calculate_utilities_mixed(self, strategy_profile: List[torch.Tensor], player_position=None,
                                   validate: bool = None) -> torch.Tensor:
        """
            Internal function that is wrapped by both play_mixed and calculate_action_values.

            For a given strategy-profile and player_position, calculates that player's expected utility for
            each of their moves. (Only opponent's strategies are considered, player_i's strategy is ignored).
            If no player_position is specified, instead returns the expected utilities for all players in the complete
            strategy profile.

            # TODO: improve this documentation to make this clearer
            --------
            Args:
                strategy_profile: List of mixed strategies (i.e. probability vectors) for all players
                player_position: (optional) int
                    Position of the player of interest, or none if interested in all players

            Returns:
                if player_position (i) is given:
                    torch.Tensor of dimension n_actions_player_i of expected utilities against opponent strategy_profile
                if no player is specified:
                    torch.Tensor of dimension n_players of expected utilities in the complete strategy profile
        """

        # validate inputs if desired
        if validate is None:
            validate = self.validate_inputs
        if validate:
            self._validate_mixed_strategy_input(strategy_profile)

        # Note on implementation:
        # This is implemented via a series of tensor-vector products.
        # self.outcomes is of dim (n_a_p1, ... n_a_pn, n_players)
        # for specific player, we select that player's outcomes in the last dimension,
        #   then perform n-1 tensor-vector-products for each opponent strategy
        # for all player's, we keep the last dimension but perform n tensor-vector products
        #
        # This is implemented as follows:
        #  1  start with outcome matrix
        #  2  define (reverse) order of operations as [i, 1,2,i-1,i+1,...n]
        #  3  permute outcome matrix according to that order, as matrix-vector-matmuls always operate on last dimension
        #  4  perform the operations, starting with the last player
        #
        # For utility of all players, the procedure is the same, except that all player's utilities are kept in the
        # 1st dimension, i.e. the order is [n+1, 1, 2, ... n]

        if player_position is None:
            result = self.outcomes
            ignore_dim = self.n_players
            order = list(range(self.n_players + 1))
        else:
            result = self.outcomes.select(self.n_players, player_position)
            ignore_dim = player_position
            order = list(range(self.n_players))

        # put ignored dimension in the beginning, rest lexicographical
        order = order.pop(ignore_dim), *order
        result = result.permute(order)

        # repeatedly mutliply from the last dimension to the first
        for j in reversed(order):
            if j != ignore_dim:
                result = result.matmul(strategy_profile[j])

        return result

    def calculate_expected_action_payoffs(self, strategy_profile, player_position):
        """
        Calculates the expected utility for a player under a mixed opponent strategy
        ----------
        Args:
            strategy_profile: List of action-probability-vectors for each player. player i's strategy must be supplied
                          but is ignored.
            player_position: player of interest

        Returns:
            expected payoff per action of player i (tensor of dimension (1 x n_actions[i])
        """
        return self._calculate_utilities_mixed(strategy_profile, player_position, validate = False)

    def play_mixed(self, strategy_profile: List[torch.Tensor], validate: bool = None):
        """Plays the game with mixed strategies, returning expectation of outcomes.

        This version does NOT support batches or multiple items, as (1) batches do not make
        sense in this setting since we are already returning expectations.

        Parameters
        ----------
        strategy_profile: List[torch.Tensor]
            A list of strategies for each player. Each element i should be a 1-dimensional
            torch tensor of length n_actions_pi with entries j = P(player i plays action j)

        validate: bool
            Whether to validate inputs. Defaults to setting in game class.
            (Validation overhead is ~100%, so you might want to turn this off in settings with many many iterations)

        Returns
        -------
        (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
            allocation: empty tensor of dimension (0) --> not used in this game
            payments:   tensor of dimension (n_players)
                        Negative expected outcome/utility for each player.
        """
        # move inputs to device if necessary
        for i, strat in enumerate(strategy_profile):
            strategy_profile[i] = strat.to(self.device)

        # validate inputs if desired
        if validate is None:
            validate = self.validate_inputs

        payoffs_per_player = self._calculate_utilities_mixed(strategy_profile, validate=validate)

        return torch.tensor([], device=self.device), -payoffs_per_player

###############################################################################
# Implementations of specific games ###########################################
##############################################################################

class RockPaperScissors(MatrixGame):
    """2 player, 3 action game rock paper scissors"""
    def __init__(self, **kwargs):

        outcomes = torch.tensor([
        # pylint:disable=bad-continuation
        #Col-p: Rock       Paper     Scissors     /  Row-p
            [   [ 0., 0],  [-1, 1],  [ 1,-1]   ], #  Rock
            [   [ 1.,-1],  [ 0, 0],  [-1, 1]   ], #  Paper
            [   [-1., 1],  [ 1,-1],  [ 0, 0]   ] #  Scissors
            ])

        names = {
            "player_names": ["RowPlayer", "ColPlayer"],
            "action_names": ["Rock", "Paper", "Scissors"]
            }

        super().__init__(2, outcomes, names=names, **kwargs)

class JordanGame(MatrixGame):
    """Jordan Anticoordination game (1993), FP does not converge. 3P version of Shapley fashion game:
        Player Actions: (Left, Right)
        P1 wants to be different from P2
        P2 wants to be different from P3
        P3 wants to be different from P1
    """
    def __init__(self,  **kwargs):
        #pylint:disable=bad-continuation
        outcomes = torch.tensor([
            [   [   #LL
                    [0.0,0,0], # LLL
                    [0,1,1]    # LLR
                ], [#LR
                    [1,1,0],   # LRL
                    [1,0,1]    # LRR
            ]], [[  #RL
                    [1,0,1],   # RLL
                    [1,1,0]    # RLR
                ], [#RR
                    [0,1,1],   # RRL
                    [0,0,0]    # RRR
            ]]])

        super().__init__(n_players=3, outcomes=outcomes, **kwargs)

class PaulTestGame(MatrixGame):
    """A 3-p game without many symmetries used for testing n-player tensor implementations.
    Payoff: [M,R,C]
    """
    def __init__(self, **kwargs):
        # pylint: disable=bad-continuation
        outcomes = torch.tensor([
            [   [   #LL
                    [2., 2, 2],  # LLL
                    [-1,1,9]    # LLR
                ], [#LR
                    [-1, 9,1],   # LRL
                    [4, 3, 3]    # LRR
            ]], [[  #RL
                    [1, 2, 2],   # RLL
                    [-2, 1,7]    # RLR
                ], [#RR
                    [-2, 7,1],   # RRL
                    [3, 4, 4]    # RRR
            ]]])

        super().__init__(n_players=3, outcomes=outcomes, **kwargs)

class PrisonersDilemma(MatrixGame):
    """Two player, two action Prisoner's Dilemma game.
       Has a unique pure Nash equilibrium in ap [1,1]
    """
    def __init__(self, **kwargs):
        super().__init__(
            n_players=2,
            outcomes = torch.tensor([[[-1, -1],[-3, 0]], [[ 0, -3],[-2,-2]]]),
            names = {
                "player_names": ["RowPlayer", "ColPlayer"],
                "action_names": ["Cooperate", "Defect"]
            },
            **kwargs
        )

class BattleOfTheSexes(MatrixGame):
    """Two player, two action Battle of the Sexes game"""
    def __init__(self, **kwargs):
        super().__init__(
            n_players=2,
            outcomes=torch.tensor([[[3, 2],[0,0]], [[0,0],[2,3]]]),
            names = {
                "player_names": ["Boy", "Girl"],
                "action_names": ["Action", "Romance"]
            },
            **kwargs
        )

class BattleOfTheSexes_Mod(MatrixGame):
    """Modified Battle of the Sexes game"""
    def __init__(self, **kwargs):
        super().__init__(
            n_players=2,
            outcomes=torch.tensor([
                [# Him: Stadium
                    [3,2],  # Her: Stadium
                    [0,0]], # Her: Theater
                [# Him: Theater
                    [0,0],  # Her: Stadium
                    [2,3]], # Her: Theater
                [# Him: Stadium with friend
                    [-1,1],  # Her: Stadium
                    [4,0]], # Her: Theater
                ]),
            **kwargs
        )

class MatchingPennies(MatrixGame):
    """Two Player, two action Matching Pennies / anticoordination game"""
    def __init__(self, **kwargs):
        super().__init__(
            n_players=2,
            outcomes=torch.tensor([[[1, -1],[-1, 1,]], [[-1, 1], [1, -1]]]),
            names = {
                "player_names": ["Even", "Odd"],
                "action_names": ["Heads", "Tails"]
            },
            **kwargs
        )

class VickreyAuction(Mechanism):
    "Vickrey / Second Price Sealed Bid Auctions"

    def run(self, bids: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs a (batch of) Vickrey/Second Price Sealed Bid Auctions.

        This function is meant for single-item auctions.
        If a bid tensor for multiple items is submitted, each item is auctioned
        independently of one another.

        Parameters
        ----------
        bids: torch.Tensor
            of bids with dimensions (batch_size, n_players, n_items)

        Returns
        -------
        (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
            allocation: tensor of dimension (n_batches x n_players x n_items),
                        1 indicating item is allocated to corresponding player
                        in that batch, 0 otherwise
            payments:   tensor of dimension (n_batches x n_players)
                        Total payment from player to auctioneer for her
                        allocation in that batch.
        """

        assert bids.dim() == 3, "Bid tensor must be 3d (batch x players x items)"
        assert (bids >= 0).all().item(), "All bids must be nonnegative."

        # move bids to gpu/cpu if necessary
        bids = bids.to(self.device)

        # name dimensions for readibility
        # pylint: disable=unused-variable
        batch_dim, player_dim, item_dim = 0, 1, 2
        batch_size, n_players, n_items = bids.shape

        # allocate return variables
        payments_per_item = torch.zeros(batch_size, n_players, n_items, device = self.device)
        allocations = torch.zeros(batch_size, n_players, n_items, device = self.device)

        highest_bids, winning_bidders = bids.max(dim=player_dim, keepdim=True) # shape of each: [batch_size, 1, n_items]

        # getting the second prices --> price is the lowest of the two highest bids
        top2_bids, _ = bids.topk(2, dim = player_dim, sorted=False)
        second_prices, _ = top2_bids.min(player_dim, keepdim=True)

        payments_per_item.scatter_(player_dim, winning_bidders, second_prices)
        payments = payments_per_item.sum(item_dim)
        allocations.scatter_(player_dim, winning_bidders, 1)
        # Don't allocate items that have a winnign bid of zero.
        allocations.masked_fill_(mask=payments_per_item == 0, value=0)

        return (allocations, payments) # payments: batches x players, allocation: batch x players x items

class FirstPriceSealedBidAuction(Mechanism):
    """First Price Sealed Bid auction"""

    # TODO: If multiple players submit the highest bid, the implementation chooses the first rather than at random
    def run(self, bids: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs a (batch of) First Price Sealed Bid Auction.

        This function is meant for single-item auctions.
        If a bid tensor for multiple items is submitted, each item is auctioned
        independently of one another.

        Parameters
        ----------
        bids: torch.Tensor
            of bids with dimensions (batch_size, n_players, n_items)

        Returns
        -------
        (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
            allocation: tensor of dimension (n_batches x n_players x n_items),
                        1 indicating item is allocated to corresponding player
                        in that batch, 0 otherwise
            payments:   tensor of dimension (n_batches x n_players)
                        Total payment from player to auctioneer for her
                        allocation in that batch.
        """
        assert bids.dim() == 3, "Bid tensor must be 3d (batch x players x items)"
        assert (bids >= 0).all().item(), "All bids must be nonnegative."

        # move bids to gpu/cpu if necessary
        bids = bids.to(self.device)

        # name dimensions for readibility
        batch_dim, player_dim, item_dim = 0, 1, 2 #pylint: disable=unused-variable
        batch_size, n_players, n_items = bids.shape

        # allocate return variables
        payments_per_item = torch.zeros(batch_size, n_players, n_items, device = self.device)
        allocations = torch.zeros(batch_size, n_players, n_items, device = self.device)

        highest_bids, winning_bidders = bids.max(dim = player_dim, keepdim=True) # both shapes: [batch_size, 1, n_items]

        # replaced by equivalent, faster torch.scatter operation, see below,
        # but keeping nested-loop code for readability
        # note: code in comment references bids.max with keepdim=False.
        ##for batch in range(batch_size):
        ##    for j in range(n_items):
        ##        hb = highest_bidders[batch, j]
        ##        payments_per_item[batch][ highest_bidders[batch, j] ][j] = highest_bids[batch, j]
        ##        allocation[batch][ highest_bidders[batch, j] ][j] = 1
        # The above can be written as the following one-liner:
        payments_per_item.scatter_(player_dim, winning_bidders, highest_bids)
        payments = payments_per_item.sum(item_dim)
        allocations.scatter_(player_dim, winning_bidders, 1)
        # Don't allocate items that have a winnign bid of zero.
        allocations.masked_fill_(mask=payments_per_item == 0, value=0)

        return (allocations, payments) # payments: batches x players, allocation: batch x players x items

class StaticMechanism(Mechanism):
    """ A static mechanism that can be used for testing purposes,
        in order to test functionality/efficiency of optimizers without introducing
        additional stochasticity from multi-player learning dynamics.

        In this 'single-player single-item' setting, items are allocated with probability bid/10,
        payments are always given by b²/20, even when the item is not allocated.
        The expected payoff from this mechanism is thus
        b/10 * v - 0.05b²,
        The optimal strategy fo an agent with quasilinear utility is given by bidding truthfully.
    """

    def __init__(self, cuda: bool = True):
        super().__init__(cuda)

    def run(self, bids):
        assert bids.dim() == 3, "Bid tensor must be 3d (batch x players x items)"
        assert (bids >= 0).all().item(), "All bids must be nonnegative."
        batch_dim, player_dim, item_dim = 0, 1, 2 #pylint: disable=unused-variable

        bids = bids.to(self.device)

        payments = torch.mul(bids,bids).mul_(0.05).sum(item_dim)
        allocations = (bids >= torch.rand_like(bids).mul_(10)).float()

        return (allocations, payments)

class LLGAuction(Mechanism):
    """
        Implements simple auctions in the LLG setting with 3 bidders and
        2 goods.
        Notably, this is not an implementation of a general Combinatorial auction
        and bidders do not submit full bundle (XOR) bids: Rather, it's assumed
        a priori that each bidder bids on a specific bundle:
        The first bidder will only bid on the bundle {1}, the second on {2},
        the third on {1,2}, thus actions are scalar for each bidder.

        For the LLG Domain see e.g. Ausubel & Milgrom 2006 or Bosshard et al 2017
    """

    def __init__(self, rule = 'first_price', cuda: bool = True):
        super().__init__(cuda)

        if rule not in ['first_price', 'vcg', 'nearest_bid', 'nearest_zero', 'proxy', 'nearest_vcg']:
            raise ValueError('Invalid Pricing rule!')
        # 'nearest_zero' and 'proxy' are aliases
        if rule == 'proxy':
            rule = 'nearest_zero'
        self.rule = rule

def run(self, bids: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Runs a (batch of) LLG Combinatorial auction(s).

    We assume n_players == 3 with 0,1 being local bidders and 3 being the global bidder.

    Parameters
    ----------
    bids: torch.Tensor
        of bids with dimensions (batch_size, n_players, 1)

    Returns
    -------
    (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
        allocation: tensor of dimension (n_batches x n_players x 1),
                    1 indicating the desired bundle is allocated to corresponding player
                    in that batch, 0 otherwise.
                    (i.e. 1 for player0 means {1} allocated, for player2 means {2} allocated,
                    for player3 means {1,2} allocated.)
        payments:   tensor of dimension (n_batches x n_players)
                    Total payment from player to auctioneer for her
                    allocation in that batch.
    """
    assert bids.dim() == 3, "Bid tensor must be 3d (batch x players x 1)"
    assert (bids >= 0).all().item(), "All bids must be nonnegative."
    # name dimensions for readibility
    batch_dim, player_dim, item_dim = 0, 1, 2 #pylint: disable=unused-variable
    batch_size, n_players, n_items = bids.shape

    assert n_players == 3, "invalid n_players in LLG setting"
    assert n_items == 1, "invalid bid_dimensionality in LLG setting" # dummy item is desired bundle for each player

    # move bids to gpu/cpu if necessary, get rid of unused item_dim
    bids = bids.squeeze(item_dim).to(self.device) # batch_size x n_players
    # individual bids as batch_size x 1 tensors:
    b1, b2, bg = bids.split(1, dim=1)

    # allocate return variables
    payments = torch.zeros(batch_size, n_players, device = self.device)
    allocations = torch.zeros(batch_size, n_players, n_items, device = self.device)

    # 1. Determine efficient allocation
    locals_win = (b1 + b2 > bg).float() # batch_size x 1
    allocations = locals_win * torch.tensor([[1.,1.,0.]], device=self.device) + \
                    (1-locals_win) * torch.tensor([[0.,0.,1.]], device=self.device) # batch x players

    if self.rule == 'first_price':
        payments = allocations * bids # batch x players
    else: # calculate local and global winner prices separately
        payments = torch.zeros(batch_size, n_players, device = self.device)
        global_winner_prices = b1 + b2 # batch_size x 1
        payments[:, [2]] = (1-locals_win) * global_winner_prices

        local_winner_prices = torch.zeros(batch_size, 2, device = self.device)

        if self.rule in ['vcg', 'nearest_vcg']:
            # vcg prices are needed for vcg, nearest_vcg
            local_vcg_prices = (bg - bids[:,[1,0]]).relu()

            if self.rule == 'vcg':
                local_winner_prices = local_vcg_prices
            else: #nearest_vcg
                delta = 0.5 * (bg - local_vcg_prices[:,[0]] - local_vcg_prices[:,[1]]) # batch_size x 1
                local_winner_prices = local_vcg_prices + delta # batch_size x 2
        elif self.rule in ['proxy', 'nearest_zero']:
            # two cases: global bidder bids less than twice as much as second local or not
            global_less_than_twice_local = (bg <= 2*b2).float() # batch_size x 1
            local_prices_case_yes = 0.5 * torch.cat(2*[bg], dim=player_dim)
            local_prices_case_no = torch.cat([bg-b2,  b2] , dim=player_dim)

            local_winner_prices = global_less_than_twice_local * local_prices_case_yes + \
                                    (1-global_less_than_twice_local) * local_prices_case_no
        elif self.rule == 'nearest_bid':
            case_yes = (bg < b1 - b2).float() # batch_size x 1

            local_prices_case_yes = torch.cat([bg, torch.zeros_like(bg)], dim=player_dim)

            delta = 0.5*(b1 + b2 - bg)
            local_prices_case_no = bids[:, [0,1]] - delta

            local_winner_prices = case_yes * local_prices_case_yes + (1-case_yes) * local_prices_case_no

        else:
            raise ValueError("invalid bid rule")

        payments[:, [0,1]] = locals_win * local_winner_prices

    return (allocations.unsqueeze(-1), payments) # payments: batches x players, allocation: batch x players x items


def remove_invalid_bids(bids: torch.Tensor) -> torch.Tensor:
    """
    For multi-unit actions, bids must be in decreasing order. If agents´ bids fail
    to fulfill this property, this method is responsible for allocating no units at
    all to those agents (setting bids to zero).
    """
    diff = bids.sort(dim=2, descending=True)[0] - bids
    diff = torch.abs_(diff).sum(dim=2) != 0
    bids[diff] = 0.0
    return bids

class MultiItemDiscriminatoryAuction(Mechanism):
    """Multi item discriminatory auction"""

    def __init__(self, cuda: bool=True):
        self.cuda = cuda and torch.cuda.is_available()
        self.device = 'cuda' if self.cuda else 'cpu'

    def run(self, bids: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs a (batch of) multi item discriminatory auction(s).

        Parameters
        ----------
        bids: torch.Tensor
            of bids with dimensions (batch_size, n_players, n_items); first entry of
            n_items dim corrsponds to bid of first unit, second entry to bid of second
            unit, etc. (how much one add. unit is ´valued´)

        Returns
        -------
        (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
            allocation: tensor of dimension (n_batches x n_players x n_items),
                1 indicating item is allocated to corresponding player
                in that batch, 0 otherwise
            payments: tensor of dimension (n_batches x n_players);
                total payment from player to auctioneer for her
                allocation in that batch.
        """
        assert bids.dim() == 3, "Bid tensor must be 3d (batch x players x items)"
        assert (bids >= 0).all().item(), "All bids must be nonnegative."

        # name dimensions for readibility
        batch_dim, player_dim, item_dim = 0, 1, 2 #pylint: disable=unused-variable
        batch_size, n_players, n_items = bids.shape

        # move bids to gpu/cpu if necessary
        bids = bids.to(self.device)

        # only accept decreasing bids
        # assert torch.equal(bids.sort(dim=item_dim, descending=True)[0], bids), \
        #     "Bids must be in decreasing order"
        bids = remove_invalid_bids(bids)

        # Alternative w/o loops
        allocations = torch.zeros(batch_size, n_players*n_items, device=self.device)
        bids_flat = bids.reshape(batch_size, n_players*n_items)
        _, sorted_idx = torch.sort(bids_flat, descending=True)
        allocations.scatter_(1, sorted_idx[:,:n_items], 1)
        allocations = allocations.reshape_as(bids)
        allocations.masked_fill_(mask=bids==0, value=0)

        # Simple but slow: for loops
        # # add fictitious negative bids (for case in which one bidder wins all items -> IndexError)
        # allocations = torch.zeros(batch_size, n_players, n_items, device=self.device)
        # bids_extend = -1 * torch.ones(batch_size, n_players, n_items+1, device=self.device)
        # bids_extend[:,:,:-1] = bids
        # for batch in range(batch_size):
        #     current_bids = bids_extend.clone().detach()[batch,:,0]
        #     current_bids_indices = [0] * n_players
        #     for _ in range(n_items):
        #         winner = current_bids.argmax()
        #         allocations[batch,winner,current_bids_indices[winner]] = 1
        #         current_bids_indices[winner] += 1
        #         current_bids[winner] = bids_extend.clone().detach()[batch,winner,current_bids_indices[winner]]

        payments = torch.sum(allocations * bids, dim=item_dim)

        return (allocations, payments) # payments: batches x players, allocation: batch x players x items

class MultiItemUniformPriceAuction(Mechanism):
    """ In a uniform-price auction, all units are sold at a “market-clearing” price
        such that the total amount demanded is equal to the total amount supplied.
        We adopt the rule that the market-clearing price is the same as the highest
        losing bid.
    """

    def __init__(self, cuda: bool = True):
        self.cuda = cuda and torch.cuda.is_available()
        self.device = 'cuda' if self.cuda else 'cpu'

    def run(self, bids: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs a (batch of) Multi Item Uniform-Price Auction(s).
    
        (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
            allocation: tensor of dimension (n_batches x n_players x n_items),
                1 indicating item is allocated to corresponding player
                in that batch, 0 otherwise
            payments: tensor of dimension (n_batches x n_players),
                total payment from player to auctioneer for her
                allocation in that batch.
        """
        assert bids.dim() == 3, "Bid tensor must be 3d (batch x players x items)"
        assert (bids >= 0).all().item(), "All bids must be nonnegative."

        # name dimensions for readibility
        batch_dim, player_dim, item_dim = 0, 1, 2 #pylint: disable=unused-variable
        batch_size, n_players, n_items = bids.shape

        # move bids to gpu/cpu if necessary
        bids = bids.to(self.device)

        # only accept decreasing bids # TODO: too time consuming?
        # assert torch.equal(bids.sort(dim=item_dim, descending=True)[0], bids), \
        #     "Bids must be in decreasing order"
        bids = remove_invalid_bids(bids)

        # allocate return variables (flat at this stage)
        allocations = torch.zeros(batch_size, n_players*n_items, device=self.device)
        payments = torch.zeros(batch_size, n_players*n_items, device=self.device)

        # allocation
        bids_flat = bids.reshape(batch_size, n_players*n_items)
        _, sorted_idx = torch.sort(bids_flat, descending=True)
        allocations.scatter_(1, sorted_idx[:,:n_items], 1)
        allocations = allocations.reshape_as(bids)
        allocations.masked_fill_(mask=bids==0, value=0)

        # priceing
        payments.scatter_(1, sorted_idx[:,n_items:n_items+1], 1)
        payments = torch.t(bids_flat[payments.bool()].repeat(n_players, 1)) \
            * torch.sum(allocations, dim=item_dim)

        # Simple but slow: for loops
        # # add fictitious negative bids (for case in which one bidder wins all items -> IndexError)
        # bids_extend = -1 * torch.ones(batch_size, n_players, n_items+1, device=self.device)
        # bids_extend[:,:,:-1] = bids
        # # allocate return variables
        # allocations = torch.zeros(batch_size, n_players, n_items, device=self.device)
        # payments = torch.zeros(batch_size, n_players, device=self.device)
        # for batch in range(batch_size):
        #     current_bids = bids_extend.clone().detach()[batch,:,0]
        #     current_bids_indices = [0] * n_players
        #     for _ in range(n_items):
        #         winner = current_bids.argmax()
        #         allocations[batch,winner,current_bids_indices[winner]] = 1
        #         current_bids_indices[winner] += 1
        #         current_bids[winner] = bids_extend.clone().detach()[batch,winner,current_bids_indices[winner]]
        #     market_clearing_price = current_bids.max()
        #     payments[batch,:] = market_clearing_price * torch.sum(allocations[batch,::], dim=item_dim-1)

        return (allocations, payments) # payments: batches x players, allocation: batch x players x items

class MultiItemVickreyAuction(Mechanism):
    """ In a Vickrey auction, a bidder who wins k units pays the k highest
        losing bids of the other bidders.
    """

    def __init__(self, cuda: bool = True):
        self.cuda = cuda and torch.cuda.is_available()
        self.device = 'cuda' if self.cuda else 'cpu'

    def run(self, bids: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs a (batch of) Multi Item Vickrey Auction(s).

        Parameters
        ----------
        bids: torch.Tensor
            of bids with dimensions (batch_size, n_players, n_items)

        Returns
        -------
        (allocation, payments): Tuple[torch.Tensor, torch.Tensor]
            allocation: tensor of dimension (n_batches x n_players x n_items),
                1 indicating item is allocated to corresponding player
                in that batch, 0 otherwise
            payments: tensor of dimension (n_batches x n_players),
                total payment from player to auctioneer for her
                allocation in that batch.
        """
        assert bids.dim() == 3, "Bid tensor must be 3d (batch x players x items)"
        assert (bids >= 0).all().item(), "All bids must be nonnegative."

        # name dimensions for readibility
        batch_dim, player_dim, item_dim = 0, 1, 2 #pylint: disable=unused-variable
        batch_size, n_players, n_items = bids.shape

        # move bids to gpu/cpu if necessary
        bids = bids.to(self.device)

        # only accept decreasing bids
        # assert torch.equal(bids.sort(dim=item_dim, descending=True)[0], bids), \
        #     "Bids must be in decreasing order"
        bids = remove_invalid_bids(bids)

        # allocate return variables
        allocations = torch.zeros(batch_size, n_players*n_items, device=self.device)

        # allocations
        bids_flat = bids.reshape(batch_size, n_players*n_items)
        sorted_bids, sorted_idx = torch.sort(bids_flat, descending=True)
        allocations.scatter_(1, sorted_idx[:,:n_items], 1)
        allocations = allocations.reshape_as(bids)
        allocations.masked_fill_(mask=bids==0, value=0)

        # priceing TODO: less reshaping?:-D
        agent_ids = torch.arange(0, n_players, device=self.device). \
                        repeat(batch_size, n_items, 1).transpose_(1, 2)
        highest_loosing_player = agent_ids.reshape(batch_size, n_players*n_items). \
                        gather(dim=1, index=sorted_idx)[:,n_items:2*n_items]. \
                        repeat_interleave(n_players*torch.ones(batch_size, device=self.device).long(), dim=0). \
                        reshape((batch_size, n_players, n_items))
        highest_loosing_prices = sorted_bids[:,n_items:2*n_items]. \
                        repeat_interleave(n_players*torch.ones(batch_size, device=self.device).long(), dim=0). \
                        reshape_as(bids).masked_fill_((highest_loosing_player == agent_ids). \
                        reshape_as(bids), 0).sort(descending=True)[0]
        payments = (allocations * highest_loosing_prices).sum(item_dim)

        # # free memory?
        # del highest_loosing_prices, valid_prices_idx, highest_loosing_player, temp, agent_ids

        # # add fictitious negative bids (for case in which one bidder wins all items -> IndexError)
        # bids_extend = -1 * torch.ones(batch_size, n_players, n_items+1, device=self.device)
        # bids_extend[:,:,:-1] = bids
        # payments = torch.zeros(batch_size, n_players, device=self.device)
        # for batch in range(batch_size):
        #     current_bids = bids_extend.clone().detach()[batch,:,0]
        #     current_bids_indices = torch.tensor([0] * n_players, device=self.device)
        #     for _ in range(n_items):
        #         winner = current_bids.argmax()
        #         allocations[batch,winner,current_bids_indices[winner]] = 1
        #         current_bids_indices[winner] += 1
        #         current_bids[winner] = bids_extend.clone().detach()[batch,winner,current_bids_indices[winner]]
        #     won_items_per_agent = torch.sum(allocations[batch,::], dim=item_dim-1)
        #     for agent in range(n_players):
        #         mask = [True] * n_players
        #         mask[agent] = False
        #         highest_losing_prices_indices = current_bids_indices.clone().detach()[mask]
        #         highest_losing_prices = current_bids.clone().detach()[mask]
        #         for _ in range(int(won_items_per_agent[agent])):
        #             highest_losing_price_agent = int(highest_losing_prices.argmax())
        #             payments[batch,agent] += highest_losing_prices[highest_losing_price_agent]
        #             highest_losing_prices_indices[highest_losing_price_agent] += 1
        #             highest_losing_prices = \
        #                 bids_extend.clone().detach()[batch,mask,highest_losing_prices_indices]

        return (allocations, payments) # payments: batches x players, allocation: batch x players x items
