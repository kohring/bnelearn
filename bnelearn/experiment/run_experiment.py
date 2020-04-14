import sys
sys.path.append('..')
import torch
import torch.nn as nn
import fire

from bnelearn.experiment.gpu_controller import GPUController
from bnelearn.experiment.learning_configuration import LearningConfiguration
from bnelearn.experiment.logger import LLGAuctionLogger, LLLLGGAuctionLogger, SingleItemAuctionLogger
from bnelearn.experiment.single_item_experiment import UniformSymmetricPriorSingleItemExperiment, \
    GaussianSymmetricPriorSingleItemExperiment

from bnelearn.experiment.combinatorial_experiment import LLGExperiment, LLLLGGExperiment
import warnings

#TODO: Using locals() to directly create the dict 
# (https://stackoverflow.com/questions/2521901/get-a-list-tuple-dict-of-the-arguments-passed-to-a-function)
# fine with you? 
def run_single_item_uniform_symmetric(n_runs, n_epochs, 
                                      n_players: [int], model_sharing=True, u_lo=0, u_hi=1, 
                                      payment_rule='first_price', risk=1.0, regret_batch_size=2**8, regret_grid_size=2**8,
                                      specific_gpu=1):
    experiment_params = locals()
    input_length = 1
    experiment_class = UniformSymmetricPriorSingleItemExperiment
    return n_runs, n_epochs, n_players, specific_gpu, input_length, experiment_class, experiment_params

def run_single_item_gaussian_symmetric(n_runs, n_epochs, 
                                       n_players: [int], model_sharing=True, valuation_mean=15, valuation_std=10, 
                                       payment_rule='first_price', risk=1.0, regret_batch_size=2**8, regret_grid_size=2**8,
                                       specific_gpu=1):
    experiment_params = locals()
    input_length = 1
    experiment_class = GaussianSymmetricPriorSingleItemExperiment
    return n_runs, n_epochs, n_players, specific_gpu, input_length, experiment_class, experiment_params
                            


if __name__ == '__main__':
    #n_runs, n_epochs, n_players, specific_gpu, input_length, experiment_class, experiment_params = run_single_item_gaussian_symmetric(1,20,[2,3])
    n_runs, n_epochs, n_players, specific_gpu, input_length, experiment_class, experiment_params = fire.Fire()

    gpu_config = GPUController(specific_gpu=specific_gpu)

    # Learner Config
    hidden_nodes = [5, 5, 5]
    hidden_activations = [nn.SELU(), nn.SELU(), nn.SELU()]

    learner_hyperparams = {
        'population_size': 128,
        'sigma': 1.,
        'scale_sigma_by_model_size': True
    }
    optimizer_hyperparams = {
        'lr': 3e-3
    }
    #TODO: input length must result from experiment
    l_config = LearningConfiguration(learner_hyperparams=learner_hyperparams,
                                    optimizer_type='adam',
                                    optimizer_hyperparams=optimizer_hyperparams,
                                    input_length=input_length,
                                    hidden_nodes=hidden_nodes,
                                    hidden_activations=hidden_activations,
                                    pretrain_iters=300, batch_size=2 ** 18,
                                    eval_batch_size=2 ** 15,
                                    cache_eval_actions=True)

    for i in n_players:
        experiment_params['n_players'] = i
        experiment = experiment_class(experiment_params, gpu_config, l_config)
        experiment.run(epochs=n_epochs, n_runs=n_runs)
