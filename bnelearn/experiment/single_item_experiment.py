import os
import warnings
from abc import ABC
import torch
import numpy as np
from typing import Callable
from functools import partial

from scipy import integrate

from bnelearn.bidder import Bidder
from bnelearn.environment import  AuctionEnvironment
from bnelearn.experiment import Experiment, GPUController, Logger, LearningConfiguration, SingleItemAuctionLogger

from bnelearn.learner import ESPGLearner
from bnelearn.mechanism import FirstPriceSealedBidAuction, VickreyAuction
from bnelearn.strategy import NeuralNetStrategy, ClosureStrategy

# TODO: Move bne_utility to the proper place
# general logic and setup, plot
class SingleItemExperiment(Experiment, ABC):

    # known issue: pylint doesn't recognize this class as abstract: https://github.com/PyCQA/pylint/commit/4024949f6caf5eff5f3da7ab2b4c3cf2e296472b
    # pylint: disable=abstract-method

    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration, known_bne = False):
        # TODO: these are temporary, get rid of these
        #self.global_bne_env = None
        #self.global_bne_utility = None
        self.mechanism_type = experiment_params['payment_rule'] #TODO: Why here?
        super().__init__(gpu_config, experiment_params, logger, l_config, known_bne)

    def _setup_logger(self):
        self.logger = SingleItemAuctionLogger(self.experiment_params, self.l_config)

    def _setup_mechanism(self):
        if self.mechanism_type == 'first_price':
            self.mechanism = FirstPriceSealedBidAuction(cuda=self.gpu_config.cuda)
        elif self.mechanism_type == 'second_price':
            self.mechanism = VickreyAuction(cuda=self.gpu_config.cuda)
        else:
            raise ValueError('Invalid Mechanism type!')

    def _setup_learners(self):
        self.learners = []
        for i in range(len(self.models)):
            self.learners.append(
                ESPGLearner(model=self.models[i], #(known pylint issue for typing.Iterable) pylint: disable=unsubscriptable-object
                            environment=self.env,
                            hyperparams=self.l_config.learner_hyperparams,
                            optimizer_type=self.l_config.optimizer,
                            optimizer_hyperparams=self.l_config.optimizer_hyperparams,
                            strat_to_player_kwargs={"player_position": i}
                            )
                )

    def _setup_learning_environment(self):


        self.env = AuctionEnvironment(self.mechanism, agents=self.bidders,
                                      batch_size=self.l_config.batch_size, n_players=self.n_players,
                                      strategy_to_player_closure=self._strat_to_bidder)

class AsymmetricPriorSingleItemExperiment(SingleItemExperiment, ABC):

    # known issue: pylint doesn't recognize this class as abstract: https://github.com/PyCQA/pylint/commit/4024949f6caf5eff5f3da7ab2b4c3cf2e296472b
    # pylint: disable=abstract-method

    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        super().__init__(experiment_params, gpu_config, logger, l_config)
        assert self.model_sharing == False, "Model sharing not possible with assymetric bidders!" #TODO: this shouldn't even exist
# implementation logic, e.g. model sharing. Model sharing should also override plotting function, etc.


# Define known BNE functions top level, so they may be pickled for parallelization
# These are called millions of timex, so each implementation should be
# setting specific, i.e. there should be NO setting checks at runtime.

def _optimal_bid_single_item_FPSB_generic_prior_risk_neutral(valuation: torch.Tensor or np.ndarray or float,
                                                             n_players: int,
                                                             prior_cdf: Callable) -> torch.Tensor:
    if not isinstance(valuation, torch.Tensor):
        # For float and numpy --> convert to tensor (relevant for plotting)
        valuation = torch.tensor(valuation, dtype=torch.float)
    # For float / 0d tensors --> unsqueeze to allow list comprehension below
    if valuation.dim() == 0:
        valuation.unsqueeze_(0)
    # shorthand notation for F^(n-1)
    Fpowered = lambda v: torch.pow(prior_cdf(v), n_players - 1)
    # do the calculations
    numerator = torch.tensor(
        [integrate.quad(Fpowered, 0, v)[0] for v in valuation],
            device=valuation.device
    ).reshape(valuation.shape)
    return valuation - numerator / Fpowered(valuation)

def _optimal_bid_FPSB_UniformSymmetricPriorSingleItem(valuation: torch.Tensor, n: int, r: float, u_lo, u_hi) -> torch.Tensor:
    return u_lo + (valuation - u_lo) * (n - 1) / (n - 1.0 + r)

def _truthful_bid(valuation: torch.Tensor) -> torch.Tensor:
    return valuation

class SymmetricPriorSingleItemExperiment(SingleItemExperiment, ABC):

    # TODO: this class should not be abstract, SymmetricSingleItemExperiment is implemented and has known bne for arbitrary prior!

    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration, known_bne = False):



        self.risk = float(experiment_params['risk'])
        self.risk_profile = Experiment.get_risk_profile(self.risk)
        # TODO: This probably shouldnt be here --> will come from subclass and/or builder.
        #if 'valuation_prior' in experiment_params.keys():
        #    self.valuation_prior = experiment_params['valuation_prior']
        self.model_sharing = experiment_params['model_sharing']

        # if not given by subclass, implement generic optimal_bid if known
        known_bne = known_bne or \
            experiment_params['payment_rule'] == 'second_price' or \
            (experiment_params['payment_rule'] == 'first price' and self.risk == 1.0)

        super().__init__(experiment_params, gpu_config, logger, l_config, known_bne=known_bne)



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

    def _set_symmetric_bne_closure(self):
        # set optimal_bid here, possibly overwritten by subclasses if more specific form is known
        if self.mechanism_type == 'first price' and  self.risk == 1:
            self._optimal_bid = partial(_optimal_bid_single_item_FPSB_generic_prior_risk_neutral,
                                    n_players = self.n_players, prior_cdf = self.common_prior.cdf)
        if self.mechanism_type == 'second_price':
            self._optimal_bid = _truthful_bid

    def _setup_eval_environment(self):

        self._set_symmetric_bne_closure()

        # TODO: parallelism should be taken from elsewhere
        n_processes_optimal_strategy = 44 if self.valuation_prior != 'uniform' and \
                                             self.mechanism_type != 'second_price' else 0
        bne_strategy = ClosureStrategy(self._optimal_bid, parallel=n_processes_optimal_strategy)

        # define bne agents once then use them in all runs
        self.bne_env = AuctionEnvironment(
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
        self.bne_utility_sampled = self.bne_env.get_reward(self.bne_env.agents[0], draw_valuations=True)
        print('Utility in BNE (sampled): \t{:.5f}'.format(self.bne_utility_sampled))

        self.bne_utility = self.bne_utility_sampled

    def _setup_name(self):
        name = ['single_item', self.mechanism_type, self.valuation_prior,
                'symmetric', self.risk_profile, str(self.n_players) + 'p']
        self.logger.base_dir = os.path.join(*name)

    def _training_loop(self, epoch):
        # do in every iteration
        # save current params to calculate update norm
        #TODO: Doesn't make sense to track for bidders instead of models but for consistency in logging for now. Change later
        prev_params = [torch.nn.utils.parameters_to_vector(model.parameters())
                       for model in self.models]
        # update model
        utilities = torch.tensor([
            learner.update_strategy_and_evaluate_utility()
            for learner in self.learners
        ])

        # everything after this is logging --> measure overhead
        log_params = {} # TODO Stefan: what does this do?
        self.logger.log_training_iteration(prev_params=prev_params, epoch=epoch, bne_env=self.bne_env,
                                           strat_to_bidder=self._strat_to_bidder,
                                           eval_batch_size=self.l_config.eval_batch_size, bne_utilities=self.bne_utilities,
                                           utilities=utilities, log_params=log_params)
        # TODO Stefan: this should be part of logger, not be called here explicitly!
        if epoch%10 == 0:
            self.logger.log_ex_interim_regret(epoch=epoch, mechanism=self.mechanism, env=self.env, learners=self.learners,
                                          u_lo=self.u_lo, u_hi=self.u_hi, regret_batch_size=self.regret_batch_size, regret_grid_size=self.regret_grid_size)




# implementation differences to symmetric case?
# known BNE
class UniformSymmetricPriorSingleItemExperiment(SymmetricPriorSingleItemExperiment):

    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):

        known_bne = experiment_params['payment_rule'] in ('first_price', 'second_price')
        # TODO: shouldn't be here probably
        self.valuation_prior = 'uniform'
        self.u_lo = float(experiment_params['u_lo'])
        self.u_hi = float(experiment_params['u_hi'])

        super().__init__(experiment_params, gpu_config, logger, l_config, known_bne=known_bne)

        self.plot_xmin = self.u_lo
        self.plot_xmax = self.u_hi 
        self.plot_ymin = 0
        self.plot_ymax = self.u_hi * 1.05

    def _strat_to_bidder(self, strategy, batch_size, player_position=0, cache_actions=False):
        strategy.connected_bidders.append(player_position)
        return Bidder.uniform(self.u_lo, self.u_hi, strategy, batch_size=batch_size,
                              player_position=player_position, cache_actions=cache_actions, risk=self.risk)

    def _setup_bidders(self):
        # setup_experiment_domain
        self.common_prior = torch.distributions.uniform.Uniform(low=self.u_lo, high=self.u_hi)

        self.positive_output_point = self.u_hi  # is required  to set up bidders

        super()._setup_bidders()

    def _set_symmetric_bne_closure(self):
        # set optimal_bid here, possibly overwritten by subclasses if more specific form is known
        if self.mechanism_type == 'first_price':
            self._optimal_bid = partial(_optimal_bid_FPSB_UniformSymmetricPriorSingleItem,
                                        n=self.n_players, r=self.risk, u_lo = self.u_lo, u_hi = self.u_hi)
        elif self.mechanism_type == 'second_price':
            self._optimal_bid = _truthful_bid
        else:
            raise ValueError('unknown mechanistm_type')

    def _setup_eval_environment(self):
        
        # setup environment and learners
        super()._setup_eval_environment()

        # calculate utilities in bne
        if self.mechanism_type == 'first_price':
            self.bne_utility_analytical = torch.tensor(
                (self.risk * (self.u_hi - self.u_lo) / (self.n_players - 1 + self.risk)) ** 
                    self.risk / (self.n_players + self.risk),
                device = self.gpu_config.device
                )
        elif self.mechanism_type == 'second_price':
            F = self.common_prior.cdf
            f = lambda x: self.common_prior.log_prob(torch.tensor(x)).exp()
            f1n = lambda x, n: n * F(x) ** (n - 1) * f(x)

            self.bne_utility_analytical, error_estimate = integrate.dblquad(
                lambda x, v: (v - x) * f1n(x, self.n_players - 1) * f(v),
                0, float('inf'),  # outer boundaries
                lambda v: 0, lambda v: v)  # inner boundaries

            self.bne_utility_analytical = torch.tensor(self.bne_utility_analytical, device=self.gpu_config.device)
            if error_estimate > 1e-6:
                warnings.warn('Error bound on analytical bne utility is not negligible!')
        else:
            raise ValueError("Invalid auction mechanism.")

        print('Utility in BNE (analytic): \t{:.5f}'.format(self.bne_utility_analytical))
        assert torch.allclose(self.bne_utility_analytical, self.bne_utility_sampled, atol=1e-4), \
            "Analytical BNE Utility does not match sampled utility from parent class! \n\t sampled {}, analytic {}".format(self.bne_utility_sampled, self.bne_utility_analytical)
        print('Using analytical BNE utility.')
        self.bne_utility = self.bne_utility_analytical

        


# known BNE + shared setup logic across runs (calculate and cache BNE
#TODO: Adjust self.valuation_mean to lists like in Uniform?!
#TODO: Not working yet. Optimal bid doesn't look right to me. Check!
class GaussianSymmetricPriorSingleItemExperiment(SymmetricPriorSingleItemExperiment):
    def __init__(self, experiment_params: dict, gpu_config: GPUController, logger: Logger,
                 l_config: LearningConfiguration):
        self.valuation_mean = None
        self.valuation_std = None
        super().__init__(experiment_params, gpu_config, logger, l_config)

    def _strat_to_bidder(self, strategy, batch_size, player_position=None, cache_actions=False):
        strategy.connected_bidders.append(player_position)
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



    def _setup_eval_environment(self):
        if self.mechanism_type == 'first_price':
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                # don't print scipy accuracy warnings
                self.bne_utility, error_estimate = integrate.dblquad(
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

            self.bne_utility, error_estimate = integrate.dblquad(
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
        #TODO: implement optimal bid etc

        raise NotImplementedError()

    def _setup_name(self):
        pass

    def _strat_to_bidder(self, strategy, batch_size, player_position=None, cache_actions=False):
        pass

    def _setup_bidders(self):
        pass

    def _setup_eval_environment(self):
        pass



    def _training_loop(self, epoch):
        pass
