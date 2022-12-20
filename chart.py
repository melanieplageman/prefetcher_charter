import pandas as pd
import matplotlib.pyplot as plt
import math
import os
from enum import Enum

class Metric(Enum):
    AVG_TPUT = 0
    LATENCY = 1
    PFD = 2
    INFLIGHT = 3
    CNC = 4
    WAIT = 5

def global_max(local_max, global_max):
    if local_max > global_max:
        return local_max
    return global_max

class Lineup:
    def __init__(self, chart_groups):
        self.members = chart_groups
        self._global_xmax = None

    def plot(self, metric_groups):
        # For now, add one for the wait chart
        max_nrows = len(metric_groups) + 1
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
                xmax = global_max(member.data.relative_time.max(), xmax)

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
        self._waits = None

    @property
    def waits(self):
        if self._waits is not None:
            return self._waits
        output = []
        for row in self.data[self.data['metric'] == 5].itertuples():
            wait_start = math.floor(row.relative_time)
            output.append({'relative_time': wait_start, 'value': 1})
            wait_end = math.ceil(wait_start + row.value)
            output.append({'relative_time': wait_end, 'value': 0})

        df = pd.DataFrame.from_records(output)
        self._waits = df.set_index('relative_time', drop=False)
        return self._waits

    @property
    def data(self):
        log = os.path.join(self.logdir, 'metric_log_' +
                                     self.version)
        self._data = pd.read_csv(log)
        self._data = self._data.sort_values(by=['time'])
        zero = self._data.time.min()
        self._data['relative_time'] = self._data.time.apply(
                lambda t: t - zero)
        self._data = self._data.set_index('relative_time', drop=False)
        return self._data

    def max_for_metric_group(self, metric_group):
        return self.data[self.data['metric'].isin([metric.value for metric in metric_group])]['value'].max()

    def plot(self, col, axes, metric_groups):
        for row, metric_group in enumerate(metric_groups):
            df = self.data[self.data['metric'].isin([metric.value for metric in
                                                     metric_group])]
            for metric in metric_group:
                getattr(df.plot, 'line')(y='value', ax=axes[row][col],
                                         label=metric.name)

        self.waits.plot.area(y='value', ax=axes[len(metric_groups)][col],
                             label=Metric.WAIT.name)
        axes[0][col].set_title(self.version)


versions = [ 'patched','og']

chart_groups = []
for version in versions:
    chart_groups.append(Member(version))

lineup = Lineup(chart_groups)

metric_groups = [[Metric.AVG_TPUT],[Metric.LATENCY],[Metric.INFLIGHT]]
lineup.plot(metric_groups)
