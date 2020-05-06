from bnelearn.experiment.configurations import *
from bnelearn.experiment.single_item_experiment import UniformSymmetricPriorSingleItemExperiment, \
    GaussianSymmetricPriorSingleItemExperiment, TwoPlayerAsymmetricUniformPriorSingleItemExperiment

from bnelearn.experiment.combinatorial_experiment import LLGExperiment, LLLLGGExperiment
from bnelearn.experiment.multi_unit_experiment import MultiUnitExperiment, SplitAwardExperiment

def single_item_uniform_symmetric(n_runs: int, n_epochs: int,
                                      n_players: [int], payment_rule: str, model_sharing=True,
                                      u_lo=0, u_hi=1,
                                      risk=1.0,
                                      log_metrics=['opt', 'l2', 'regret'], regret_batch_size=2 ** 4,
                                      regret_grid_size=2 ** 4,
                                      specific_gpu=0,
                                      logging=True):
    running_configuration = RunningConfiguration(n_runs=n_runs, n_epochs=n_epochs, specific_gpu=specific_gpu,
                                                 n_players=n_players)
    logging_configuration = LoggingConfiguration(log_metrics=log_metrics,
                                                 regret_batch_size=regret_batch_size,
                                                 regret_grid_size=regret_grid_size,
                                                 enable_logging=logging
                                                 )

    experiment_configuration = ExperimentConfiguration(payment_rule=payment_rule, model_sharing=model_sharing,
                                                       u_lo=u_lo, u_hi=u_hi, risk=risk)
    experiment_class = UniformSymmetricPriorSingleItemExperiment
    return running_configuration, logging_configuration, experiment_configuration, experiment_class


def single_item_gaussian_symmetric(n_runs: int, n_epochs: int,
                                       n_players: [int], payment_rule: str, model_sharing=True, valuation_mean=15,
                                       valuation_std=10,
                                       risk=1.0, eval_batch_size=2 ** 16,
                                       log_metrics=['opt', 'l2', 'regret'], regret_batch_size=2 ** 8,
                                       regret_grid_size=2 ** 8,
                                       specific_gpu=1,
                                       logging=True):
    if eval_batch_size == 2 ** 16:
        print("Using eval_batch_size of 2**16. Use at least 2**22 for proper experiment runs!")
    running_configuration = RunningConfiguration(n_runs=n_runs, n_epochs=n_epochs, specific_gpu=specific_gpu,
                                                 n_players=n_players)
    logging_configuration = LoggingConfiguration(log_metrics=log_metrics,
                                                 regret_batch_size=regret_batch_size,
                                                 regret_grid_size=regret_grid_size,
                                                 eval_batch_size=eval_batch_size,
                                                 enable_logging=logging
                                                 )
    experiment_configuration = ExperimentConfiguration(payment_rule=payment_rule, model_sharing=model_sharing,
                                                       valuation_mean=valuation_mean, valuation_std=valuation_std,
                                                       risk=risk)
    experiment_class = GaussianSymmetricPriorSingleItemExperiment
    return running_configuration, logging_configuration, experiment_configuration, experiment_class


def single_item_asymmetric_uniform(
        n_runs: int,
        n_epochs: int,
        payment_rule='first_price',
        model_sharing=False,
        u_lo=[0, 6],  # [5, 5],     [0, 6]
        u_hi=[5, 7],  # [15, 25],   [5, 7]
        risk=1.0,
        eval_batch_size=2 ** 18,
        log_metrics=['opt', 'l2', 'regret'],
        regret_batch_size=2 ** 8,
        regret_grid_size=2 ** 8,
        specific_gpu=1,
        logging=True
    ):
    n_players = [2]
    running_configuration = RunningConfiguration(n_runs=n_runs, n_epochs=n_epochs,
                                                 specific_gpu=specific_gpu, n_players=n_players)
    logging_configuration = LoggingConfiguration(log_metrics=log_metrics,
                                                 regret_batch_size=regret_batch_size,
                                                 regret_grid_size=regret_grid_size,
                                                 eval_batch_size=eval_batch_size
                                                 )

    experiment_configuration = ExperimentConfiguration(payment_rule=payment_rule, model_sharing=model_sharing,
                                                       u_lo=u_lo, u_hi=u_hi, risk=risk)
    experiment_class = TwoPlayerAsymmetricUniformPriorSingleItemExperiment
    return running_configuration, logging_configuration, experiment_configuration, experiment_class


def llg(n_runs: int, n_epochs: int,
            payment_rule: str, model_sharing=True,
            u_lo=[0, 0, 0], u_hi=[1, 1, 2],
            risk=1.0,
            log_metrics=['opt', 'l2', 'regret'], regret_batch_size=2 ** 8, regret_grid_size=2 ** 8,
            specific_gpu=1,
            logging=True):
    n_players = [3]
    running_configuration = RunningConfiguration(n_runs=n_runs, n_epochs=n_epochs, specific_gpu=specific_gpu,
                                                 n_players=n_players)
    logging_configuration = LoggingConfiguration(log_metrics=log_metrics,
                                                 regret_batch_size=regret_batch_size,
                                                 regret_grid_size=regret_grid_size,
                                                 enable_logging=logging
                                                 )

    experiment_configuration = ExperimentConfiguration(payment_rule=payment_rule, model_sharing=model_sharing,
                                                       u_lo=u_lo, u_hi=u_hi, risk=risk)
    experiment_class = LLGExperiment
    return running_configuration, logging_configuration, experiment_configuration, experiment_class


def llllgg(n_runs: int, n_epochs: int,
               payment_rule: str, model_sharing=True,
               u_lo=[0, 0, 0, 0, 0, 0], u_hi=[1, 1, 1, 1, 2, 2],
               risk=1.0, eval_batch_size=2 ** 12,
               log_metrics=['regret'], regret_batch_size=2 ** 8, regret_grid_size=2 ** 8,
               core_solver="NoCore",
               specific_gpu=1,
               logging=True):
    n_players = [6]
    running_configuration = RunningConfiguration(n_runs=n_runs, n_epochs=n_epochs, specific_gpu=specific_gpu,
                                                 n_players=n_players)
    logging_configuration = LoggingConfiguration(log_metrics=log_metrics,
                                                 regret_batch_size=regret_batch_size,
                                                 regret_grid_size=regret_grid_size,
                                                 eval_batch_size=eval_batch_size,
                                                 enable_logging=logging
                                                 )

    experiment_configuration = ExperimentConfiguration(payment_rule=payment_rule, model_sharing=model_sharing,
                                                       u_lo=u_lo, u_hi=u_hi, risk=risk, core_solver=core_solver)
    experiment_class = LLLLGGExperiment
    return running_configuration, logging_configuration, experiment_configuration, experiment_class


def multiunit(
            n_runs: int, n_epochs: int,
            n_players: list = [2],
            payment_rule: str = 'vcg',
            n_units=2,
            log_metrics=['opt', 'l2', 'regret'],
            model_sharing=True,
            u_lo=[0, 0], u_hi=[1, 1],
            risk=1.0,
            constant_marginal_values: bool = False,
            item_interest_limit: int = None,
            regret_batch_size=2 ** 8,
            regret_grid_size=2 ** 8,
            specific_gpu=0,
            logging=True
    ):
    running_configuration = RunningConfiguration(
        n_runs=n_runs, n_epochs=n_epochs,
        specific_gpu=specific_gpu, n_players=[2]
    )
    logging_configuration = LoggingConfiguration(
        log_metrics=log_metrics,
        regret_batch_size=regret_batch_size,
        regret_grid_size=regret_grid_size,
        plot_points=1000,
        enable_logging=logging
    )
    experiment_configuration = ExperimentConfiguration(
        payment_rule=payment_rule, n_units=n_units,
        model_sharing=model_sharing,
        u_lo=u_lo, u_hi=u_hi, risk=risk,
        constant_marginal_values=constant_marginal_values,
        item_interest_limit=item_interest_limit
    )
    experiment_class = MultiUnitExperiment
    return running_configuration, logging_configuration, experiment_configuration, experiment_class


def splitaward(
            n_runs: int, n_epochs: int,
            n_players: list = [2],
            payment_rule: str = 'first_price',
            n_units=2,
            model_sharing=True,
            log_metrics=['opt', 'l2', 'regret'],
            u_lo=[1, 1], u_hi=[1.4, 1.4],
            risk=1.0,
            constant_marginal_values: bool = False,
            item_interest_limit: int = None,
            efficiency_parameter: float = 0.3,
            regret_batch_size=2 ** 8,
            regret_grid_size=2 ** 8,
            specific_gpu=1,
            logging=True
    ):
    running_configuration = RunningConfiguration(
        n_runs=n_runs, n_epochs=n_epochs,
        specific_gpu=specific_gpu, n_players=[2]
    )
    logging_configuration = LoggingConfiguration(
        log_metrics=log_metrics,
        regret_batch_size=regret_batch_size,
        regret_grid_size=regret_grid_size,
        enable_logging=logging
    )

    experiment_configuration = ExperimentConfiguration(
        payment_rule=payment_rule, n_units=n_units,
        model_sharing=model_sharing,
        u_lo=u_lo, u_hi=u_hi, risk=risk,
        constant_marginal_values=constant_marginal_values,
        item_interest_limit=item_interest_limit,
        efficiency_parameter=efficiency_parameter
    )
    experiment_class = SplitAwardExperiment
    return running_configuration, logging_configuration, experiment_configuration, experiment_class