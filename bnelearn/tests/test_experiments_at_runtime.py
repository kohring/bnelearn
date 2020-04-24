"""
This file tests the run of experiments at runtime, so simply whether it technically completes the run.
It chooses only 2 runs, with 3 epochs but plots and logs every period. Logging and plotting is not written to disc.
It considers each implemented experiment with each payment rule. Fo each experiment no model_sharing is tested once.
TODO:
    - Paul: Can we delete "test_experiment_runtimes" now?
"""
import pytest
import sys
import os
sys.path.append(os.path.realpath('.'))
#import torch.nn as nn
from bnelearn.experiment.run_experiment \
    import run_single_item_uniform_symmetric, run_single_item_gaussian_symmetric, \
           run_single_item_asymmetric_uniform, run_llg, run_llllgg, run_multiunit, run_splitaward
from bnelearn.experiment.configurations import LearningConfiguration
from bnelearn.experiment.gpu_controller import GPUController

ids, testdata = zip(*[
    # Single item
    ['single_item-symmetric-uniform-fp', (run_single_item_uniform_symmetric(2,3, [2], 'first_price'),1)],
    ['single_item-symmetric-uniform-vcg', (run_single_item_uniform_symmetric(2,3, [3], 'second_price'),1)],
    ['single_item-symmetric-uniform-vcg-no_model_sharing',
        (run_single_item_uniform_symmetric(2,3, [3], 'second_price',model_sharing=False),1)],
    ['single_item-symmetric-gaussian-fp', (run_single_item_gaussian_symmetric(2,3, [4], 'first_price'),1)],
    ['single_item-symmetric-gaussian-vcg', (run_single_item_gaussian_symmetric(2,3, [5], 'second_price'),1)],
    ['single_item-asymmetric-uniform-fp', (run_single_item_asymmetric_uniform(2,3, 'first_price'),1)],
    ['single_item-asymmetric-uniform-vcg', (run_single_item_asymmetric_uniform(2,3, 'second_price'),1)],
    # LLG
    ['LLG-fp', (run_llg(2,3,'first_price'),1)],
    ['LLG-fp-no_model_sharing', (run_llg(2,3,'first_price', model_sharing=False),1)],
    ['LLG-vcg', (run_llg(2,3,'vcg'),1)],
    ['LLG-nearest_bid', (run_llg(2,3,'nearest_bid'),1)],
    ['LLG-nearest_zero', (run_llg(2,3,'nearest_zero'),1)],
    ['LLG-nearest_vcg', (run_llg(2,3,'nearest_vcg'),1)],
    # LLLLGG
    ['LLLLGG-fp', (run_llllgg(2,3,'first_price'),2)],
    ['LLLLGG-fp-no_model_sharing', (run_llllgg(2,3,'first_price',model_sharing=False),2)],
    ['LLLLGG-vcg', (run_llllgg(2,3,'vcg'),2)],
    ['LLLLGG-nearest_vcg', (run_llllgg(2,3,'nearest_vcg'),2)],
    # MultiUnit
    ['MultiUnit-fp', (run_multiunit(2, 3, [2], 'first_price'),2)],
    ['MultiUnit-fp-no_model_sharing', (run_multiunit(2, 3, [2], 'first_price',model_sharing=False),2)],
    ['MultiUnit-vcg', (run_multiunit(2, 3, [2], 'second_price'),2)],
    ['SplitAward-fp', (run_splitaward(2, 3, [2]),2)],
    ['SplitAward-fp-no_model_sharing', (run_splitaward(2, 3, [2], model_sharing=False),2)]
    ])

def run_auction_test(create_auction_function, input_length, gpu_configuration):
    learning_configuration = LearningConfiguration(input_length=input_length, pretrain_iters=20)
    running_configuration, logging_configuration, experiment_configuration, experiment_class = create_auction_function
    experiment_configuration.n_players = running_configuration.n_players[0]
    experiment = experiment_class(experiment_configuration, learning_configuration,
                                    logging_configuration, gpu_configuration)
    experiment.run(epochs=running_configuration.n_epochs, n_runs=running_configuration.n_runs)
    assert True

#TODO, Paul: InputLength should become obsolete
@pytest.mark.parametrize("auction_function_with_params, input_length", testdata, ids=ids)
def test_auction(auction_function_with_params, input_length):
    #TODO: Set runs to 3, set logging and printing and regret to 1, activate all metrics possible
    #TODO: Add bne metric to LLLLGG and test for failure
    #TODO: Disable logging (by a variable that is checked just before writing)
    gpu_configuration = GPUController(specific_gpu=2)
    # Log and plot frequent but few
    auction_function_with_params[1].plot_frequency=1
    auction_function_with_params[1].regret_frequency=1
    auction_function_with_params[1].plot_points=10
    auction_function_with_params.regret_batch_size = 2**2
    auction_function_with_params.regret_grid_size = 2**2
    run_auction_test(auction_function_with_params,input_length,gpu_configuration)
