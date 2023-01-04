import pandas as pd
import matplotlib.pyplot as plt
import math
import os
from enum import Enum

class Metric(Enum):
    AVG_TPUT = 0
    LATENCY = 1
    PFD = 2
    SUBMITTED = 3
    INFLIGHT = 4
    CNC = 5
    COMPLETED = 6
    CONSUMED = 7
    REAL_CONSUMED = 8
    WAIT = 9

def global_max(local_max, global_max):
    if local_max > global_max:
        return local_max
    return global_max

class Lineup:
    def __init__(self, chart_groups):
        self.members = chart_groups
        self._global_xmax = None

    def plot(self, metric_groups):
        max_nrows = len(metric_groups)
        ncols = len(self.members)
        width = 11 * ncols
        height = 5 * max_nrows

        figure = plt.figure(figsize=(width, height))
        axes = figure.subplots(max_nrows, ncols, squeeze=False)

        xmax = 0
        for row, metric_group in enumerate(metric_groups):
            ymax = 0
            for col, member in enumerate(self.members):
                ymax = global_max(member.max_for_metric_group(metric_group), ymax)
                xmax = global_max(member.data.index.max(), xmax)

            for col in range(len(self.members)):
                axes[row][col].set_ylim([0, ymax * 1.2])

        for ax in axes.flat:
            ax.set_xlim([0, xmax * 1.01])

        for col, member in enumerate(self.members):
            member.plot(col, axes, metric_groups)

        plt.savefig('current.png')


class Member:
    def __init__(self, version):
        self.version = version
        self.logdir = '/tmp/pgsr_pfd'
        self._data = None

    @property
    def data(self):
        if self._data is not None:
            return self._data

        log = os.path.join(self.logdir, 'metric_log_' +
                                     self.version)
        self._data = pd.read_csv(log)
        self._data = self._data.sort_values(by=['time'])
        zero = self._data.time.min()
        self._data['relative_time'] = self._data.time.apply(lambda t: t - zero)
        # self._data = self._data.drop_duplicates(['relative_time','value','metric'])
        df = self._data[self._data['metric'] == Metric.AVG_TPUT.value]
        df.to_csv(f'{self.version}.csv')
        self._data = self._data.drop_duplicates(['relative_time','metric'])

        # self._data = self._data.set_index('relative_time')
        pd.set_option('display.max_rows', None)
        # print(self._data[['relative_time','value','metric']])
        self._data = self._data.pivot(index='relative_time', columns='metric',
                                      values='value')
        self._data[Metric.WAIT.value] = self._data[Metric.WAIT.value].cumsum()
        return self._data

    def max_for_metric_group(self, metric_group):
        return max(self.data[metric.value].max() for metric in metric_group)

    def plot(self, col, axes, metric_groups):
        for row, metric_group in enumerate(metric_groups):
            for metric in metric_group:
                df = self.data.dropna(subset=[metric.value])
                df.plot(y=metric.value, ax=axes[row][col], label=metric.name)

        axes[0][col].set_title(self.version)


versions = [ 'patched','og']

chart_groups = []
for version in versions:
    chart_groups.append(Member(version))

lineup = Lineup(chart_groups)

metric_groups = [[Metric.CONSUMED, Metric.REAL_CONSUMED],
                 [Metric.AVG_TPUT], [Metric.LATENCY],
                 [Metric.COMPLETED],
                 [Metric.SUBMITTED],
                 [Metric.CNC, Metric.INFLIGHT, Metric.PFD],
                 [Metric.WAIT]]

lineup.plot(metric_groups)
