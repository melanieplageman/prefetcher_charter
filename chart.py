import pandas as pd
import matplotlib.pyplot as plt
import math
import os

# CONSUMPTIONS
#      consumption_time
# 0         8.532247e+08

# COMPLETIONS
#       latency  submission_time  completion_time  prefetch_distance  cnc  inflight  max_prefetch_distance
#0     0.243057     8.532247e+08     8.532247e+08                  4    0         7                    128

# WAITS
#         wait_start      wait_end  wait_length
# 0     8.532247e+08  8.532247e+08     0.028614

def get_wait_df(wait_log, xmin, xmax):
    waits = pd.read_csv(wait_log)
    output = {}
    for i in range(xmin, xmax + 1):
        output[i] = 0

    for row in waits.itertuples():
        wait_start = math.floor(row.wait_start)
        wait_end = math.ceil(row.wait_end) + 1
        for i in range(wait_start, wait_end):
            output[math.ceil(i)] = 1

    data = []
    for key, val in output.items():
        data.append({'tick': key, 'wait': val})
    df = pd.DataFrame.from_records(data)
    df.set_index('tick', drop=False)
    return df

width = 15
height = 20
figure = plt.figure(figsize=(width, height))

class ChartGroupCollection:
    def __init__(self, chart_groups):
        self.members = chart_groups

    def global_absolute_xmax(self):
        global_xmax = self.members[0].xmax
        for chart_group in self.members:
            if chart_group.xmax > self._xmax:
                global_xmax = chart_group.xmax
        return global_xmax

    def plot(self):
        # rows is the number of different chart types -- currently is completions,
        # consumptions, waits, and throughput
        max_nrows = 4
        ncols = len(self.members)
        width = 11 * ncols
        height = 5 * max_nrows

        figure = plt.figure(figsize=(width, height))
        axes = figure.subplots(max_nrows, ncols, squeeze=False)

        for member in self.members:
            member.make_time_relative()

        global_relative_xmax = 0
        global_nios_ymax = 0
        global_latency_ymax = 0
        global_throughput_ymax = 0
        for member in self.members:
            member_relative_xmax = member.get_max_relative_time()
            if member_relative_xmax > global_relative_xmax:
                global_relative_xmax = member_relative_xmax

            member_nios_ymax = member.get_nios_max()
            if member_nios_ymax > global_nios_ymax:
                global_nios_ymax = member_nios_ymax

            member_latency_ymax = member.completions.latency.max()
            if member_latency_ymax > global_latency_ymax:
                global_latency_ymax = member_latency_ymax

            member_throughput_ymax = member.consumptions.avg_tput.max()
            if member_throughput_ymax > global_throughput_ymax:
                global_throughput_ymax = member_throughput_ymax

        global_nios_ymax *= 1.2
        global_latency_ymax *= 1.2
        global_throughput_ymax *= 1.2
        global_relative_xmax *= 1.01

        for col, member in enumerate(self.members):
            axes[member.nios_row][col].set_ylim([0, global_nios_ymax])
            axes[member.latency_row][col].set_ylim([0, global_latency_ymax])
            axes[member.throughput_row][col].set_ylim([0, global_throughput_ymax])

        for ax in axes.flat:
            ax.set_xlim([0, global_relative_xmax])

        for col, chart_group in enumerate(self.members):
            chart_group.plot(col, axes)

        plt.savefig('current.png')


class ChartGroup:
    def __init__(self, version):
        self.version = version
        self.logdir = '/tmp/pgsr_pfd'
        self._waits = None
        self._completions = None
        self._consumptions = None
        self._xmax = None
        self._xmin = None
        self.wait_row = 0
        self.nios_row = 1
        self.latency_row = 2
        self.throughput_row = 3

    @property
    def xmin(self):
        if self._xmin is not None:
            return self._xmin
        self._xmin = math.floor(self.completions.submission_time.min())
        return self._xmin

    @property
    def xmax(self):
        if self._xmax is not None:
            return self._xmax
        completion_xmax = math.ceil(self.completions.completion_time.max())
        consumption_xmax = math.ceil(self.consumptions.consumption_time.max())
        self._xmax = max(completion_xmax, consumption_xmax)
        return self._xmax

    @property
    def waits(self):
        if self._waits is not None:
            return self._waits
        wait_log = os.path.join(self.logdir, 'wait_log_' + self.version)
        self._waits = get_wait_df(wait_log, self.xmin, self.xmax)
        return self._waits

    @property
    def completions(self):
        if self._completions is not None:
            return self._completions
        completion_log = os.path.join(self.logdir, 'completion_log_' + self.version)
        self._completions = pd.read_csv(completion_log)
        self._completions = self._completions.set_index('completion_time',
                                                        drop=False)
        return self._completions

    @property
    def consumptions(self):
        if self._consumptions is not None:
            return self._consumptions
        consumption_log = os.path.join(self.logdir, 'consumption_log_' + self.version)
        self._consumptions = pd.read_csv(consumption_log)
        self._consumptions = self._consumptions.set_index('consumption_time',
                                                          drop=False)
        return self._consumptions

    def make_time_relative(self):
        completions_zero = self.completions.completion_time.min()
        self._completions['relative_time'] = self.completions.completion_time.apply(
            lambda t: t - completions_zero)

        consumptions_zero = self.consumptions.consumption_time.min()
        self._consumptions['relative_time'] = self.consumptions.consumption_time.apply(
            lambda t: t - consumptions_zero)

        waits_zero = self.waits.tick.min()
        self._waits['relative_time'] = self.waits.tick.apply(
            lambda t: t - waits_zero)

    def get_max_relative_time(self):
        return max(
                self.completions.relative_time.max(),
                self.waits.relative_time.max(),
                self.consumptions.relative_time.max()
                )

    def get_nios_max(self):
        return max(
                self.completions.inflight.max(),
                self.completions.cnc.max(),
                self.completions.prefetch_distance.max()
                )

    def plot(self, col, axes):
        self.waits.plot.area(x='relative_time', stacked=False,
                             ax=axes[self.wait_row][col])

        self.completions.plot(x='relative_time', y=['inflight', 'cnc',
                                                    'prefetch_distance'],
                              ax=axes[self.nios_row][col])

        self.completions.plot(x='relative_time', y=['latency'],
                              ax=axes[self.latency_row][col])

        self.consumptions.plot(x='relative_time', y=['avg_tput'],
                               ax=axes[self.throughput_row][col])

        # Put the title above the first row of each column
        axes[0][col].set_title(self.version)


versions = [ 'patched','og']

chart_groups = []
for version in versions:
    chart_groups.append(ChartGroup(version))

cg_collection = ChartGroupCollection(chart_groups)

cg_collection.plot()
