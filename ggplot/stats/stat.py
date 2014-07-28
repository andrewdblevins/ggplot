from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import sys
from copy import deepcopy

from ggplot.utils.exceptions import GgplotError
import ggplot.geoms

__all__ = ['stat']
__all__ = [str(u) for u in __all__]


class stat(object):
    """Base class of all stats"""
    REQUIRED_AES = set()
    DEFAULT_PARAMS = dict()

    # Stats may modify existing columns or create extra
    # columns.
    #
    # Any extra columns that may be created by the stat
    # should be specified in this set
    # see: stat_bin
    CREATES = set()

    # used by _print_warning to keep track of the
    # warning messages printed to the standard error
    _warnings_printed = set()

    def __init__(self, *args, **kwargs):
        _params, kwargs = self._find_stat_params(kwargs)
        self.params = deepcopy(self.DEFAULT_PARAMS)
        self.params.update(_params)

        self._cache = {}
        # Whatever arguments cannot be recognised as
        # parameters, will be used to create a geom
        self._cache['args'] = args
        self._cache['kwargs'] = kwargs

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

    def _print_warning(self, message):
        """
        Prints message to the standard error.
        """
        if message not in self._warnings_printed:
            sys.stderr.write(message)
            self._warnings_printed.add(message)

    def _calculate(self, data):
        msg = "{} should implement this method."
        raise NotImplementedError(
            msg.format(self.__class__.__name__))

    def __radd__(self, gg):
        # Create and add a layer to ggplot object
        _g = getattr(ggplot.geoms, 'geom_' + self.params['geom'])
        _geom = _g(*self._cache['args'], **self._cache['kwargs'])
        _geom.params['stat'] = self.__class__.__name__
        _geom.params['position'] = self.params['position']
        _geom._stat = self

        l = layer(geom=self._geom, stat=self, data=self.data,
                  mapping=self.aes,
                  position=self.params['position'])
        gg.layers.append(l)
        return gg

    def _find_stat_params(self, kwargs):
        """
        Identity and return the stat parameters.

        The identified parameters are removed from kwargs

        Parameters
        ----------
        kwargs : dict
            keyword arguments passed to stat.__init__

        Returns
        -------
        d : dict
            stat parameters
        kwargs : dict
            rest of the kwargs
        """
        d = {}
        for k in list(kwargs.keys()):
            if k in self.DEFAULT_PARAMS:
                d[k] = kwargs.pop(k)
        return d, kwargs

    def _verify_aesthetics(self, data):
        """
        Check if all the required aesthetics have been specified

        Raise an Exception if an aesthetic is missing
        """
        missing_aes = self.REQUIRED_AES - set(data.columns)
        if missing_aes:
            msg = '{} requires the following missing aesthetics: {}'
            raise GgplotError(msg.format(
                self.__class__.__name__, ', '.join(missing_aes)))
