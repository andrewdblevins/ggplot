from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .geom import geom
from ..utils import hex_to_rgba


class geom_hline(geom):
    DEFAULT_AES = {'color': 'black', 'linetype': 'solid',
                   'size': 1.0, 'alpha': 1, 'y': None,
                   'xmin': None, 'xmax': None}
    REQUIRED_AES = {'yintercept'}
    DEFAULT_PARAMS = {'stat': 'hline', 'position': 'identity',
                      'show_guide': False}

    layer_params = {'inherit_aes': False}

    _aes_renames = {'size': 'linewidth', 'linetype': 'linestyle'}
    _units = {'alpha'}

    def draw_groups(self, data, scales, ax, **kwargs):
        """
        Plot all groups
        """
        pinfos = self._make_pinfos(data)
        for pinfo in pinfos:
            self.draw(pinfo, scales, ax, **kwargs)

    def draw(self, pinfo, scales, ax, **kwargs):
        try:
            del pinfo['y']
        except KeyError:
            pass
        y = pinfo.pop('yintercept')
        xmin = pinfo.pop('xmin')
        xmax = pinfo.pop('xmax')

        range_x = scales['x'].coord_range()
        if xmin is None:
            xmin = range_x[0]

        if xmax is None:
            xmax = range_x[1]

        alpha = pinfo.pop('alpha')
        pinfo['color'] = hex_to_rgba(pinfo['color'], alpha)
        ax.hlines(y, xmin, xmax, **pinfo)
