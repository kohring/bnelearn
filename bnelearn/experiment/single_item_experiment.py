import os
import warnings
from abc import ABC
import torch
import numpy as np

from scipy import integrate

from bnelearn.bidder import Bidder
from bnelearn.environment import Environment, AuctionEnvironment
from bnelearn.experiment import Experiment, GPUController, Logger, LearningConfiguration

from bnelearn.learner import ESPGLearner
from bnelearn.mechanism import FirstPriceSealedBidAuction, VickreyAuction
from bnelearn.strategy import Strategy, NeuralNetStrategy, ClosureStrategy

# TODO: Change global_bne_utilitiy to global_bne_utilities (as list) and all it's dependencies. (Or is this never a list?!)
# general logic and setup, plot
class SingleItemExperiment(Experiment, ABC):
    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        self.mechanism_type = experiment_params['payment_rule']
        self.global_bne_env = None
        self.global_bne_utility = None
        super().__init__(gpu_config, experiment_params, logger, l_config)
        self._run_setup()

    def _setup_learners(self):
        self.learners = []
        for i in range(len(self.models)):
            self.learners.append(ESPGLearner(model=self.models[i],
                                 environment=self.env,
                                 hyperparams=self.l_config.learner_hyperparams,
                                 optimizer_type=self.l_config.optimizer,
                                 optimizer_hyperparams=self.l_config.optimizer_hyperparams,
                                 strat_to_player_kwargs={"player_position": i}
                                 ))

    def _setup_learning_environment(self):
        if self.mechanism_type == 'first_price':
            self.mechanism = FirstPriceSealedBidAuction(cuda=self.gpu_config.cuda)
        elif self.mechanism_type == 'second_price':
            self.mechanism = VickreyAuction(cuda=self.gpu_config.cuda)

        self.env = AuctionEnvironment(self.mechanism, agents=self.bidders,
                                      batch_size=self.l_config.batch_size, n_players=self.n_players,
                                      strategy_to_player_closure=self._strat_to_bidder)

class AsymmetricPriorSingleItemExperiment(SingleItemExperiment, ABC):
    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        super().__init__(experiment_params, gpu_config, logger, l_config)
        assert self.model_sharing == False, "Model sharing not possible with assymetric bidders!"
# implementation logic, e.g. model sharing. Model sharing should also override plotting function, etc.
class SymmetricPriorSingleItemExperiment(SingleItemExperiment, ABC):
    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        super().__init__(experiment_params, gpu_config, logger, l_config)
        # Make sure all valuation priors are the same
        assert self.u_lo[1:] == self.u_lo[:-1]
        assert self.u_hi[1:] == self.u_hi[:-1]

    def _setup_bidders(self):
        print('Setting up bidders...')
        self.models = []

        if self.model_sharing:
            self.models.append(NeuralNetStrategy(
                self.l_config.input_length, hidden_nodes=self.l_config.hidden_nodes,
                hidden_activations=self.l_config.hidden_activations,
                ensure_positive_output=torch.tensor([float(self.positive_output_point)])
            ).to(self.gpu_config.device))

            self.bidders = [self._strat_to_bidder(self.models[0], self.l_config.batch_size, i)
                            for i in range(self.n_players)]
        else:
            self.bidders = []
            for i in range(self.n_players):
                self.models.append(NeuralNetStrategy(
                    self.l_config.input_length, hidden_nodes=self.l_config.hidden_nodes,
                    hidden_activations=self.l_config.hidden_activations,
                    ensure_positive_output=torch.tensor([float(self.positive_output_point)])
                ).to(self.gpu_config.device))
                self.bidders.append(self._strat_to_bidder(self.models[i], self.l_config.batch_size, i))

        if self.l_config.pretrain_iters > 0:
            print('\tpretraining...')
            for i in range(len(self.models)):
                self.models[i].pretrain(self.bidders[i].valuations, self.l_config.pretrain_iters)

    def _setup_eval_environment(self):
        n_processes_optimal_strategy = 44 if self.valuation_prior != 'uniform' and \
                                             self.mechanism_type != 'second_price' else 0
        bne_strategy = ClosureStrategy(self._optimal_bid, parallel=n_processes_optimal_strategy)

        # define bne agents once then use them in all runs
        self.global_bne_env = AuctionEnvironment(
            self.mechanism,
            agents=[self._strat_to_bidder(bne_strategy,
                                          player_position=i,
                                          batch_size=self.l_config.eval_batch_size,
                                          cache_actions=self.l_config.cache_eval_actions)
                    for i in range(self.n_players)],
            batch_size=self.l_config.eval_batch_size,
            n_players=self.n_players,
            strategy_to_player_closure=self._strat_to_bidder
        )
        #TODO: This is not very precise. Instead we should consider taking the mean over all agents
        global_bne_utility_sampled = self.global_bne_env.get_reward(self.global_bne_env.agents[0], draw_valuations=True)

        print("Utility in BNE (analytical): \t{:.5f}".format(self.global_bne_utility))
        print('Utility in BNE (sampled): \t{:.5f}'.format(global_bne_utility_sampled))

        # environment filled with optimal players for logging
        # use higher batch size for calculating optimum
        self.bne_env = self.global_bne_env
        # Each bidder has the same bne utility
        self.bne_utilities = [self.global_bne_utility] * self.n_players

    def _setup_name(self):
        name = ['single_item', self.mechanism_type, self.valuation_prior,
                'symmetric', self.risk_profile, str(self.n_players) + 'p']
        self.logger.base_dir = os.path.join(*name)

    def _training_loop(self, epoch):
        # do in every iteration
        # save current params to calculate update norm
        prev_params = [torch.nn.utils.parameters_to_vector(model.parameters())
                       for model in self.models]
        # update model
        utilities = torch.tensor([
            learner.update_strategy_and_evaluate_utility()
            for learner in self.learners
        ])

        # everything after this is logging --> measure overhead
        log_params = {}
        self.logger.log_training_iteration(prev_params=prev_params, epoch=epoch, bne_env=self.bne_env,
                                           strat_to_bidder=self._strat_to_bidder,
                                           eval_batch_size=self.l_config.eval_batch_size, bne_utilities=self.bne_utilities,
                                           bidders=self.bidders, utilities=utilities, log_params=log_params)

        if epoch%10 == 0:
            self.logger.log_ex_interim_regret(epoch=epoch, mechanism=self.mechanism, env=self.env, learners=self.learners, 
                                          u_lo=self.u_lo, u_hi=self.u_hi, regret_batch_size=self.regret_batch_size, regret_grid_size=self.regret_grid_size)


# implementation differences to symmetric case?
# known BNE
class UniformSymmetricPriorSingleItemExperiment(SymmetricPriorSingleItemExperiment):

    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        super().__init__(experiment_params, gpu_config, logger, l_config)

    def _strat_to_bidder(self, strategy, batch_size, player_position=0, cache_actions=False):
        return Bidder.uniform(self.u_lo[player_position], self.u_hi[player_position], strategy, batch_size=batch_size,
                              player_position=player_position, cache_actions=cache_actions, risk=self.risk)

    def _setup_bidders(self):
        # setup_experiment_domain
        self.common_prior = torch.distributions.uniform.Uniform(low=self.u_lo[0], high=self.u_hi[0])

        self.positive_output_point = max(self.u_hi)  # is required  to set up bidders

        self.valuation_prior = 'uniform'  # for now, one of 'uniform' / 'normal', specific params defined in script

        super()._setup_bidders()

    def _optimal_bid(self, valuation, player_position=None):
        if self.mechanism_type == 'second_price':
            return valuation
        elif self.mechanism_type == 'first_price':
            return self.u_lo[0] + (valuation - self.u_lo[0]) * (self.n_players - 1) / (self.n_players - 1.0 + self.risk)
        else:
            raise ValueError('Invalid Auction Mechanism')

    def _setup_eval_environment(self):
        if self.mechanism_type == 'first_price':
            self.global_bne_utility = (self.risk * (self.u_hi[0] - self.u_lo[0]) / (self.n_players - 1 + self.risk)) ** \
                                      self.risk / (self.n_players + self.risk)
        elif self.mechanism_type == 'second_price':
            F = self.common_prior.cdf
            f = lambda x: self.common_prior.log_prob(torch.tensor(x)).exp()
            f1n = lambda x, n: n * F(x) ** (n - 1) * f(x)

            self.global_bne_utility, error_estimate = integrate.dblquad(
                lambda x, v: (v - x) * f1n(x, self.n_players - 1) * f(v),
                0, float('inf'),  # outer boundaries
                lambda v: 0, lambda v: v)  # inner boundaries

            if error_estimate > 1e-6:
                warnings.warn('Error bound on analytical bne utility is not negligible!')
        else:
            raise ValueError("Invalid auction mechanism.")

        super()._setup_eval_environment()


# known BNE + shared setup logic across runs (calculate and cache BNE
#TODO: Adjust self.valuation_mean to lists like in Uniform?! 
#TODO: Not working yet sind no actions generated in bne samping calculation. Check!
class GaussianSymmetricPriorSingleItemExperiment(SymmetricPriorSingleItemExperiment):
    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        self.valuation_mean = None
        self.valuation_std = None
        super().__init__(experiment_params, gpu_config, logger, l_config)

    def _strat_to_bidder(self, strategy, batch_size, player_position=None, cache_actions=False):
        return Bidder.normal(self.valuation_mean, self.valuation_std, strategy,
                             batch_size=batch_size,
                             player_position=player_position,
                             cache_actions=cache_actions,
                             risk=self.risk)

    def _setup_bidders(self):
        #TODO: Probably move all this stuff to the init. ()
        self.valuation_mean = 10.0
        self.valuation_std = 5.0
        self.common_prior = torch.distributions.normal.Normal(loc=self.valuation_mean, scale=self.valuation_std)

        self.positive_output_point = self.valuation_mean

        self.plot_xmin = int(max(0, self.valuation_mean - 3 * self.valuation_std))
        self.plot_xmax = int(self.valuation_mean + 3 * self.valuation_std)
        self.plot_ymin = 0
        self.plot_ymax = 20 if self.mechanism_type == 'first_price' else self.plot_xmax

        self.valuation_prior = 'normal'

        super()._setup_bidders()

    def _optimal_bid(self, valuation: torch.Tensor or np.ndarray or float, player_position=None):
        if self.mechanism_type == 'second_price':
            return valuation
        elif self.mechanism_type == 'first_price':
            if self.risk_profile != 'risk_neutral':
                warnings.warn("Ignoring risk-aversion in optimal bid!")

                # For float and numpy --> convert to tensor
                if not isinstance(valuation, torch.Tensor):
                    valuation = torch.tensor(valuation, dtype=torch.float)
                # For float / 0d tensors --> unsqueeze to allow list comprehension below
                if valuation.dim() == 0:
                    valuation.unsqueeze_(0)

                # shorthand notation for F^(n-1)
                Fpowered = lambda v: torch.pow(self.common_prior.cdf(v), self.n_players - 1)

                # do the calculations
                numerator = torch.tensor(
                    [integrate.quad(Fpowered, 0, v)[0] for v in valuation],
                    device=valuation.device
                ).reshape(valuation.shape)
                return valuation - numerator / Fpowered(valuation)
        else:
            raise ValueError('Invalid Auction Mechanism')

    def _setup_eval_environment(self):
        if self.mechanism_type == 'first_price':
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                # don't print scipy accuracy warnings
                self.global_bne_utility, error_estimate = integrate.dblquad(
                    lambda x, v: self.common_prior.cdf(x) ** (self.n_players - 1) * self.common_prior.log_prob(
                        v).exp(),
                    0, float('inf'),  # outer boundaries
                    lambda v: 0, lambda v: v)  # inner boundaries
                if error_estimate > 1e-6:
                    warnings.warn('Error in optimal utility might not be negligible')
        elif self.mechanism_type == 'second_price':
            F = self.common_prior.cdf
            f = lambda x: self.common_prior.log_prob(torch.tensor(x)).exp()
            f1n = lambda x, n: n * F(x) ** (n - 1) * f(x)

            self.global_bne_utility, error_estimate = integrate.dblquad(
                lambda x, v: (v - x) * f1n(x, self.n_players - 1) * f(v),
                0, float('inf'),  # outer boundaries
                lambda v: 0, lambda v: v)  # inner boundaries

            if error_estimate > 1e-6:
                warnings.warn('Error bound on analytical bne utility is not negligible!')
        else:
            raise ValueError("Invalid auction mechanism.")

        super()._setup_eval_environment()


# known BNE
class TwoPlayerUniformPriorSingleItemExperiment(AsymmetricPriorSingleItemExperiment):
    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        super().__init__(experiment_params, gpu_config, logger, l_config)

    def _setup_name(self):
        pass

    def _strat_to_bidder(self, strategy, batch_size, player_position=None, cache_actions=False):
        pass

    def _setup_bidders(self):
        pass

    def _setup_eval_environment(self):
        pass

    def _optimal_bid(self, valuation, player_position=None):
        pass

    def _training_loop(self, epoch):
        pass
