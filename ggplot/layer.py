from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
from copy import deepcopy

import pandas as pd
import pandas.core.common as com

from .components.aes import aes, is_calculated_aes
from .scales.scales import scales_add_defaults
from .utils.exceptions import GgplotError
from .utils import discrete_dtypes, ninteraction
from .utils import check_required_aesthetics, defaults


class layer(object):

    def __init__(self, geom=None, stat=None,
                 data=None, mapping=None,
                 position=None, params=None,
                 inherit_aes=False, group=None):
        self.geom = geom
        self.stat = stat
        self.data = data
        self.mapping = mapping
        self.position = position
        self.params = params
        self.inherit_aes = inherit_aes
        self.group = group

    def __deepcopy__(self, memo):
        """
        Deep copy without copying the self.data dataframe
        """
        # In case the object cannot be initialized with out
        # arguments
        class _empty(object):
            pass
        result = _empty()
        result.__class__ = self.__class__
        for key, item in self.__dict__.items():
            # don't make a deepcopy of data!
            if key == "data":
                result.__dict__[key] = self.__dict__[key]
                continue
            result.__dict__[key] = deepcopy(self.__dict__[key], memo)
        return result

    def layer_mapping(self, mapping):
        """
        Return the mappings that are active in this layer
        """
        # For certain geoms, it is useful to be able to
        # ignore the default aesthetics and only use those
        # set in the layer
        if self.inherit_aes:
            aesthetics = defaults(self.mapping, mapping)
        else:
            aesthetics = self.mapping

        # drop aesthetics that are manual or calculated
        manual = set(self.geom.manual_aes.keys())
        calculated = set(is_calculated_aes(aesthetics))
        d = dict((ae, v) for ae, v in aesthetics.items()
                 if not (ae in manual) and not (ae in calculated))
        return aes(**d)

    def compute_aesthetics(self, data, plot):
        """
        Return a dataframe where the columns match the
        aesthetic mappings
        """
        aesthetics = self.layer_mapping(plot.mapping)

        # Override grouping if set in layer.
        if not self.group is None:
            aesthetics['group'] = self.group

        scales_add_defaults(plot.scales, data, aesthetics)

        colnames = []  # columns to rename with aesthetics names
        aenames = []   # aesthetics names to use
        settings = {}  # for manual settings withing aesthetics
        for ae, col in aesthetics.items():
            if isinstance(col, six.string_types):
                colnames.append(col)
                aenames.append(ae)
            elif com.is_list_like(col):
                n = len(col)
                if n != len(data) or n != 1:
                    raise GgplotError(
                        "Aesthetics must either be length one, " +
                        "or the same length as the data")
                settings[ae] = col
            else:
                msg = "Do not know how to deal with aesthetic '{}'"
                raise GgplotError(msg.format(ae))

        evaled = pd.DataFrame()
        for ae, col in zip(aenames, colnames):
            evaled[ae] = data[col]
        evaled.update(settings)

        if len(data) == 0 and settings:
            # No data, and vectors suppled to aesthetics
            evaled['PANEL'] = 1
        else:
            evaled['PANEL'] = data['PANEL']

        return evaled

    def calc_statistic(self, data, scales):
        """
        Verify required aethetics and return the
        statistics as computed by the stat object
        """
        if not len(data):
            return pd.DataFrame()

        check_required_aesthetics(
            self.stat.REQUIRED_AES,
            list(data.columns) + list(self.stat.params.keys()),
            self.stat.__class__.__name__)

        return self.stat._calculate_groups(data, scales)

    def map_statistic(self, data, plot):
        """
        """
        if len(data) == 0:
            return pd.DataFrame()

        # Assemble aesthetics from layer, plot and stat mappings
        aesthetics = deepcopy(self.mapping)
        if self.inherit_aes:
            aesthetics = defaults(aesthetics, plot.mapping)

        aesthetics = defaults(aesthetics, self.stat.DEFAULT_AES)

        # The new aesthetics are those that the stat calculates
        # and have been mapped to with dot dot notation
        # e.g aes(y='..count..'), y is the new aesthetic and
        # 'count' is the computed column in data
        new = {}  # {'aesthetic_name': 'calculated_stat'}
        stat_data = pd.DataFrame()
        for ae in is_calculated_aes(aesthetics):
            new[ae] = strip_dots(aesthetics[ae])
            stat_data[ae] = data[new[ae]]

        if not new:
            return data

        # Add any new scales, if needed
        scales_add_defaults(plot.scales, data, new)

        # Transform the values, if the scale say it's ok
        if self.stat.retransform:
            # TODO: Implement this
            # data = scales_transform_df(plot.scales, stat_data)
            pass

        data = pd.concat([data, stat_data], axis=1)
        return data

def add_group(data):
    if len(data) == 0:
        return data
    if not ('group' in data):
        disc = discrete_columns(data, ignore=['label'])
        if disc:
            data['group'] = ninteraction(data[disc], drop=True)
        else:
            data['group'] = 1
    else:
        data['group'] = ninteraction(data['group'], drop=True)

    return data


def discrete_columns(df, ignore):
    """
    Return a list of the discrete columns in the
    dataframe `df`. `ignore` is a list|set|tuple with the
    names of the columns to skip.
    """
    lst = []
    for col in df:
        if (df[col].dtype in discrete_dtypes) and not (col in ignore):
            lst.append(col)
    return lst
