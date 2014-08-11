from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib as mpl
from patsy.eval import EvalEnvironment

from .components import aes
from .components import colors, shapes
from .components.legend import add_legend
from .geoms import *
from .scales import *
from .facets import *
from .themes.theme_gray import theme_gray
from .utils.exceptions import GgplotError, gg_warning
from .panel import Panel
from .layer import add_group
from .scales.scales import Scales
from .scales.scales import scales_add_missing

import six

__all__ = ["ggplot"]
__all__ = [str(u) for u in __all__]

import sys
import warnings
from copy import deepcopy

# Show plots if in interactive mode
if sys.flags.interactive:
    plt.ion()

# Workaround for matplotlib 1.1.1 not having a rc_context
if not hasattr(mpl, 'rc_context'):
    from .utils import _rc_context
    mpl.rc_context = _rc_context



class ggplot(object):
    """
    ggplot is the base layer or object that you use to define
    the components of your chart (x and y axis, shapes, colors, etc.).
    You can combine it with layers (or geoms) to make complex graphics
    with minimal effort.

    Parameters
    -----------
    aesthetics :  aes (ggplot.components.aes.aes)
        aesthetics of your plot
    data :  pandas DataFrame (pd.DataFrame)
        a DataFrame with the data you want to plot

    Examples
    ----------
    >>> p = ggplot(aes(x='x', y='y'), data=diamonds)
    >>> print(p + geom_point())
    """

    CONTINUOUS = ['x', 'y', 'size', 'alpha']
    DISCRETE = ['color', 'shape', 'marker', 'alpha', 'linestyle']

    def __init__(self, mapping, data):
        if not isinstance(data, pd.DataFrame):
            mapping, data = data, mapping

        self.data = data
        self.mapping = mapping
        self.facet = facet_null()
        self.labels = mapping  # TODO: Should allow for something else!!
        self.layers = []
        self.scales = Scales()
        # default theme is theme_gray
        self.theme = theme_gray()
        self.plot_env = EvalEnvironment.capture(1)

    def __repr__(self):
        """Print/show the plot"""
        figure = self.draw()
        # We're going to default to making the plot appear when __repr__ is
        # called.
        #figure.show() # doesn't work in ipython notebook
        plt.show()
        # TODO: We can probably get more sugary with this
        return "<ggplot: (%d)>" % self.__hash__()

    def __deepcopy__(self, memo):
        '''deepcopy support for ggplot'''
        # This is a workaround as ggplot(None, None) does not really work :-(
        class _empty(object):
            pass
        result = _empty()
        result.__class__ = self.__class__
        # don't make a deepcopy of data, or plot_env
        shallow = {'data', 'plot_env'}
        for key, item in self.__dict__.items():
            if key in shallow:
                result.__dict__[key] = self.__dict__[key]
                continue
            result.__dict__[key] = deepcopy(self.__dict__[key], memo)

        return result

    def draw(self):
        # Adding rc=self.rcParams does not validate/parses the params which then
        # throws an error during plotting!
        with mpl.rc_context():
            # Use a throw away rcParams, so subsequent plots will not have any
            # residual from this plot
            # @todo: change it to something more like
            # rcParams = theme.get_rcParams()
            rcParams = self.theme.get_rcParams()
            for key in six.iterkeys(rcParams):
                val = rcParams[key]
                # there is a bug in matplotlib which does not allow None directly
                # https://github.com/matplotlib/matplotlib/issues/2543
                try:
                    if key == 'text.dvipnghack' and val is None:
                        val = "none"
                    mpl.rcParams[key] = val
                except Exception as e:
                    msg = """Setting "mpl.rcParams['%s']=%s" raised an Exception: %s""" % (key, str(val), str(e))
                    warnings.warn(msg, RuntimeWarning)
            # draw is not allowed to show a plot, so we can use to result for ggsave
            # This sets a rcparam, so we don't have to undo it after plotting
            mpl.interactive(False)
            self.plot_build()

    def add_to_legend(self, legend_type, legend_dict, scale_type="discrete"):
        """Adds the the specified legend to the legend

        Parameters
        ----------
        legend_type : str
            type of legend, one of "color", "linestyle", "marker", "size"
        legend_dict : dict
            a dictionary of {visual_value: legend_key} where visual_value
            is color value, line style, marker character, or size value;
            and legend_key is a quantile.
        scale_type : str
            either "discrete" (default) or "continuous"; usually only color
            needs to specify which kind of legend should be drawn, all
            other scales will get a discrete scale.
        """
        # scale_type is up to now unused
        # TODO: what happens if we add a second color mapping?
        # Currently the color mapping in the legend is overwritten.
        # What does ggplot do in such a case?
        if legend_type in self.legend:
            pass
            #msg = "Adding a secondary mapping of {0} is unsupported and no legend for this mapping is added.\n"
            #sys.stderr.write(msg.format(str(legend_type)))
        self.legend[legend_type] = legend_dict

    def plot_build(self):
        # TODO:
        # - copy the plot_data in here and give each layer
        #   a separate copy. Currently this is happening in
        #   facet.map_layout
        # - Do not alter the user dataframe, create a copy
        #   that keeps only the columns mapped to aesthetics.
        #   Currently, this space conservation is happening
        #   in compute_aesthetics. Can we get this evaled
        #   dataframe before train_layout!!!
        if not self.layers:
            raise GgplotError('No layers in plot')

        plot = deepcopy(self)

        layers = self.layers
        layer_data = [x.data for x in self.layers]
        all_data = [plot.data] + layer_data
        scales = plot.scales

        def dlapply(f):
            """
            Call the function f with the dataframe and layer
            object as arguments.
            """
            out = [None] * len(data)
            for i in range(len(data)):
                out[i] = f(data[i], layers[i])
            return out

        # Initialise panels, add extra data for margins & missing facetting
        # variables, and add on a PANEL variable to data
        panel = Panel()
        panel.layout = plot.facet.train_layout(all_data)
        data = plot.facet.map_layout(panel.layout, layer_data, plot.data)

        # Compute aesthetics to produce data with generalised variable names
        data = dlapply(lambda d, l: l.compute_aesthetics(d, plot))
        data = list(map(add_group, data))

        # Transform all scales

        # Map and train positions so that statistics have access to ranges
        # and all positions are numeric
        x_scale = scales.get_scales('x')
        y_scale = scales.get_scales('y')

        panel.train_position(data, x_scale, y_scale)
        data = panel.map_position(data, x_scale, y_scale)

        # Apply and map statistics
        data = panel.calculate_stats(data, layers)
        data = dlapply(lambda d, l: l.map_statistic(d, plot))
        # data = list(map(order_groups, data)) # !!! look into this

        # Make sure missing (but required) aesthetics are added
        scales_add_missing(plot, ('x', 'y'))

        # Reparameterise geoms from (e.g.) y and width to ymin and ymax
        data = dlapply(lambda d, l: l.reparameterise(d))

        # Apply position adjustments
        data = dlapply(lambda d, l: l.adjust_position(d))

        print(data[0])
        # print(scales)
        # print(panel.layout)
        # print(plot.scales)
        return panel


def _is_identity(x):
    if x in colors.COLORS:
        return True
    elif x in shapes.SHAPES:
        return True
    elif isinstance(x, (float, int)):
        return True
    else:
        return False
