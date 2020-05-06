"""This module contains utilities for logging of experiments"""

import os
import time
from typing import List
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
from torch.utils.tensorboard.writer import SummaryWriter, FileWriter, scalar
import pandas as pd
import warnings
import matplotlib.pyplot as plt
import torch


# based on https://stackoverflow.com/a/57411105/4755970
# output_dir must be the directory immediately above the runs and each run must have the same shape.
# No aggregation of multiple subdirectories for now.
def log_tb_events(output_dir, write_aggregate=True, write_detailed=False, write_binary=False):
    """
    This function reads all tensorboard event log files in subdirectories and converts their content into
    a single csv file containing info of all runs.
    """
    cross_experiment_log_dir = output_dir.rsplit('/', 1)[0]
    # runs are all subdirectories that don't start with '.' (exclude '.ipython_checkpoints')
    # add more filters as needed
    runs = [x.name for x in os.scandir(output_dir) if
            x.is_dir() and not x.name.startswith('.') and not x.name == 'alternative']

    cur_run_tb_events = {'run': [], 'tag': [], 'epoch': [], 'value': [], 'wall_time': []}
    last_epoch_tb_events = {'run': [], 'tag': [], 'epoch': [], 'value': [], 'wall_time': []}
    for run in runs:
        ea = EventAccumulator(os.path.join(output_dir, run)).Reload()
        tags = ea.Tags()['scalars']

        for tag in tags:
            for event in ea.Scalars(tag):
                cur_run_tb_events['run'].append(run)
                cur_run_tb_events['tag'].append(tag)
                cur_run_tb_events['value'].append(event.value)
                cur_run_tb_events['wall_time'].append(event.wall_time)
                cur_run_tb_events['epoch'].append(event.step)

        last_epoch_tb_events['run'].append(run)
        last_epoch_tb_events['tag'].append(tag)
        last_epoch_tb_events['value'].append(event.value)
        last_epoch_tb_events['wall_time'].append(event.wall_time)
        last_epoch_tb_events['epoch'].append(event.step)

    cur_run_tb_events = pd.DataFrame(cur_run_tb_events)
    last_epoch_tb_events = pd.DataFrame(last_epoch_tb_events)

    if write_detailed:
        f_name = os.path.join(output_dir, f'full_results.csv')
        cur_run_tb_events.to_csv(f_name)

    if write_aggregate:
        f_name = os.path.join(cross_experiment_log_dir, f'aggregate_log.csv')
        last_epoch_tb_events.to_csv(f_name, mode='a', header=not os.path.isfile(f_name))

    if write_binary:
        warnings.warn('Binary serialization not Implemented')


def process_figure(fig, epoch=None, figure_name='plot', tb_group='eval',
                   tb_writer=None, display=False,
                   output_dir=None, save_png=False, save_svg=False):
    """displays, logs and/or saves a figure"""

    if save_png and output_dir:
        plt.savefig(os.path.join(output_dir, 'png', f'{figure_name}_{epoch:05}.png'))

    if save_svg and output_dir:
        plt.savefig(os.path.join(output_dir, 'svg', f'{figure_name}_{epoch:05}.svg'),
                    format='svg', dpi=1200)
    if tb_writer:
        tb_writer.add_figure(f'{tb_group}/{figure_name}', fig, epoch)

    if display:
        plt.show()


class CustomSummaryWriter(SummaryWriter):
    """Extends SummaryWriter with a method to add multiple scalars in the way
    that we intend. The original SummaryWriter can either add a single scalar at a time
    or multiple scalars, but in the latter case, multiple runs are created without
    the option to control these.
    """

    def add_metrics_dict(self, metrics_dict: dict, run_suffices: List[str], global_step=None, walltime=None,
                        group_prefix: str = None ):
        """         
        Args:
            metric_dict (dict): A dict of metrics. Keys are tag names, values are values.
                values can be float, List[float] or Tensor.
                When List or (nonscalar) tensor, the length must match n_models
            run_suffices (List[str]): if each value in metrics_dict is scalar, doesn't need to be supplied.
                When metrics_dict contains lists/iterables, they must all have the same length which should be equal to
                the length of run_suffices
        """
        torch._C._log_api_usage_once("tensorboard.logging.add_scalar")
        walltime = time.time() if walltime is None else walltime
        fw_logdir = self._get_file_writer().get_logdir()

        if run_suffices is None:
            run_suffices = []

        l = len(run_suffices)
        print(l)


        for key, vals in metrics_dict.items():
            tag = key if not group_prefix else group_prefix + '/' + key

            if isinstance(vals, float) or isinstance(vals, int) or (
                torch.is_tensor(vals) and vals.size() in {torch.Size([]), torch.Size([1])}
                ):
                """Only a single value --> log directly in main run""" 
                
                self.add_scalar(tag, vals, global_step, walltime)
            elif len(vals) == l:
                """Log each into a run with its own prefix."""
                for suffix, scalar_value in zip(run_suffices, vals):
                    fw_tag = fw_logdir + "/" + suffix.replace("/", "_")

                    if fw_tag in self.all_writers.keys():
                        fw = self.all_writers[fw_tag]
                    else:
                        fw = FileWriter(fw_tag, self.max_queue, self.flush_secs,
                                        self.filename_suffix)
                        self.all_writers[fw_tag] = fw
                    # Not using caffe2 -->following line is commented out from original SummaryWriter implementation
                    # if self._check_caffe2_blob(scalar_value):
                    #     scalar_value = workspace.FetchBlob(scalar_value)
                    fw.add_summary(scalar(tag, scalar_value),
                                global_step, walltime)
            else:
                raise ValueError('Got list of invalid length.')
