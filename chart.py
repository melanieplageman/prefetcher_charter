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
    return pd.DataFrame.from_records(data, index='tick')

width = 15
height = 20
figure = plt.figure(figsize=(width, height))

class ChartGroupCollection:
    def __init__(self, chart_groups):
        self.members = chart_groups
        self._xmin = None
        self._xmax = None

    @property
    def xmin(self):
        if self._xmin is not None:
            return self._xmin
        self._xmin = self.members[0].xmin
        for chart_group in self.members:
            if chart_group.xmin < self._xmin:
                self._xmin = chart_group.xmin
        return self._xmin

    @property
    def xmax(self):
        if self._xmax is not None:
            return self._xmax
        self._xmax = self.members[0].xmax
        for chart_group in self.members:
            if chart_group.xmax > self._xmax:
                self._xmax = chart_group.xmax
        return self._xmax

    def plot(self, axes):
        for ax in axes.flat:
            ax.set_xlim([self.xmin, self.xmax])

        for chart_group in self.members:
            chart_group.plot(axes)


class ChartGroup:
    def __init__(self, version):
        self.version = version
        self.logdir = '/tmp/pgsr_pfd'
        self._waits = None
        self._completions = None
        self._consumptions = None
        self._xmax = None
        self._xmin = None

    @property
    def xmin(self):
        if self._xmin is not None:
            return self._xmin
        self._xmin = math.floor(min(self.completions.submission_time))
        return self._xmin

    @property
    def xmax(self):
        if self._xmax is not None:
            return self._xmax
        completion_xmax = math.ceil(max(self.completions.completion_time))
        consumption_xmax = math.ceil(max(self.consumptions.consumption_time))
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
        return self._consumptions

    def plot(self, axes):
        self.waits.plot.area(stacked=False, ax=axes[0][0])
        self.completions.plot(y=['inflight', 'cnc', 'prefetch_distance'], ax=axes[1][0])
        self.completions.plot(y=['latency'], ax=axes[2][0])
        output_image_filename = self.version + '.png'
        plt.savefig(output_image_filename)


versions = ['patched']
# rows is the number of different chart types -- currently is completions,
# consumptions, and waits
max_nrows = 3
ncols = len(versions)
axes = figure.subplots(max_nrows, ncols, squeeze=False)

chart_groups = []
for version in versions:
    chart_groups.append(ChartGroup(version))

cg_collection = ChartGroupCollection(chart_groups)

cg_collection.plot(axes)
