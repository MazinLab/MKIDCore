import re
import os
import numpy as np
import mkidcore.config
from mkidcore.corelog import getLogger
import astropy.units


MEC_FEEDLINE_INFO = dict(num=10, width=14, length=146)
DARKNESS_FEEDLINE_INFO = dict(num=5, width=25, length=80)
XKID_FEEDLINE_INFO = dict(num=5, width=25, length=80)

FEEDLINE_INFO = {'mec': MEC_FEEDLINE_INFO, 'darkness':DARKNESS_FEEDLINE_INFO, 'xkid':XKID_FEEDLINE_INFO}

DEFAULT_ARRAY_SIZES = {'mec': (140, 146), 'darkness': (80, 125), 'xkid': (80, 125)}


MEC_NUM_FL_MAP = {228: '1a', 229: '1b', 238: '5a', 239: '5b', 220: '6a', 221: '6b',
                  222: '7a', 223: '7b', 232: '8a', 233: '8b',
                  236: '9a', 237: '9b', 224: '10a', 225: '10b'}

#NB FLs are arbitrary as instrument isn't installed
DARKNESS_NUM_FL_MAP = {112: '1a', 114: '1b', 115: '5a', 116: '5b',
                       117: '6a', 118: '6b', 119: '7a', 120: '7b', 121: '8a',
                       122: '8b'}

XKID_NUM_FL_MAP = {112: '5a', 114: '5b', 115: '2a', 116: '2b',
                   117: '1a', 118: '1b', 119: '3a', 120: '3b', 121: '4a',
                   122: '4b'}

MEC_FL_NUM_MAP = {v: str(k) for k, v in MEC_NUM_FL_MAP.items()}

DARKNESS_FL_NUM_MAP = {v: str(k) for k, v in MEC_NUM_FL_MAP.items()}

XKID_FL_NUM_MAP = {v: str(k) for k, v in XKID_NUM_FL_MAP.items()}

ROACHES = {'mec': MEC_NUM_FL_MAP.keys(), 'darkness': DARKNESS_NUM_FL_MAP.keys(),
           'bluefors': []}
ROACHESA = {'mec': [k for k, v in MEC_NUM_FL_MAP.items() if 'a' in v],
            'darkness': [k for k, v in DARKNESS_NUM_FL_MAP.items() if 'a' in v],
            'xkid': [k for k, v in XKID_NUM_FL_MAP.items() if 'a' in v],
            'bluefors': []}
ROACHESB = {'mec': [k for k, v in MEC_NUM_FL_MAP.items() if 'b' in v],
            'darkness': [k for k, v in DARKNESS_NUM_FL_MAP.items() if 'b' in v],
            'xkid': [k for k, v in XKID_NUM_FL_MAP.items() if 'b' in v],
            'bluefors': []}

for k in list(ROACHES):
    ROACHES[k.upper()] = ROACHES[k]
for k in list(ROACHESA):
    ROACHESA[k.upper()] = ROACHESA[k]
for k in list(ROACHESB):
    ROACHESB[k.upper()] = ROACHESB[k]

INSTRUMENT_INFO = {'mec': dict(deadtime_us=10, energy_bin_width_ev=0.1, minimum_wavelength=700, filter_cutoff_min=950,
                               maximum_wavelength=1500, nominal_platescale_mas=10.05, device_orientation_deg=-43.24,
                               maximum_count_rate=5000, name='MEC'),
                   'darkness': dict(deadtime_us=10, energy_bin_width_ev=0.1, minimum_wavelength=700,
                                    maximum_wavelength=1500, nominal_platescale_mas=10.4, device_orientation_deg=0,
                                    maximum_count_rate=5000, name='DARKNESS'),
                   'xkid': dict(deadtime_us=10, energy_bin_width_ev=0.1, minimum_wavelength=700,
                                    maximum_wavelength=1500, nominal_platescale_mas=10.4, device_orientation_deg=0,
                                    maximum_count_rate=5000, name='XKID')
                   }


class InstrumentInfo(mkidcore.config.ConfigThing):
    yaml_tag = u'!InstrumentInfo'

    def __init__(self, *args, **kwargs):
        default = ''
        if len(args) == 1 and isinstance(args[0], str):
            default = args[0]
        try:
            default = kwargs.pop('default')
        except KeyError:
            pass

        if default:
            super(InstrumentInfo, self).__init__(**kwargs)
            try:
                for k, v in INSTRUMENT_INFO[default.lower()].items():
                    if 'nominal_platescale_mas' in k:
                        v *= astropy.units.mas
                    if 'device_orientation_deg' in k:
                        v *= astropy.units.deg
                    self.register(k, v)
            except KeyError:
                raise ValueError('Unknown instrument: ' + args[0])
        else:
            super(InstrumentInfo, self).__init__(*args, **kwargs)

    @classmethod
    def to_yaml(cls, representer, node):
        x = {k: v for k, v in node.items()}
        for k in ('nominal_platescale_mas', 'device_orientation_deg'):
            try:
                x[k] = float(x[k].value)
            except:
                x[k] = float(x[k])
        return representer.represent_mapping(cls.yaml_tag, x)

    @classmethod
    def from_yaml(cls, loader, node):
        ret = super(InstrumentInfo, cls).from_yaml(loader, node)
        return ret


mkidcore.config.yaml.register_class(InstrumentInfo)


def CONEX2PIXEL(xCon, yCon, slopes, ref_pix, ref_con):
    """ Returns pixel location corresponding to CONEX location (xCon, yCon) given reference pixel ref_pix and reference
    CONEX position ref_con """
    def func(x, slope, intercept):
        return x * slope + intercept
    # Pre-fall 2021 (ends with the 20210910 run)
    # xopt = (-63.36778615, 88.47319224)
    # yopt = (68.5940592, 83.7997898)

    # Post-fall 2021 (starts with the 20211014 run)
    # xopt = (-67.03698001, 116.81715145)
    # yopt = (69.29451828, 66.30860825)
    xopt = (slopes[0], ref_pix[0])
    yopt = (slopes[1], ref_pix[1])
    return np.asarray((func(xCon - ref_con[0], *xopt), func(yCon - ref_con[1], *yopt)))


def compute_wcs_ref_pixel(position, reference=(0, 0), reference_pixel=(0, 0), conex_deltas=(0, 0), instrument='mec'):
    """
    A function to convert the conex offset to pixel displacement

    Params
    ------
    position : tuple, CommentedSeq
        conex position for dither. Conex units i.e. -3<x<3
    center : tuple, CommentedSeq
        Origin of conex grid. Conex units i.e. -3<x<3. Typically (0, 0)
    target_center_at_ref : tuple, CommentedSeq
        Center of rotation of dithers in pixel coordinate of the Canvas grid center. Derotated images will be smeared
        if this is off. drizzler.get_star_offset() can be used to calibrate this.
    instrument : str
        the MKID instrument

    Returns
    -------
    The reference pixel for Canvas grid relative to its center

    """
    if instrument.lower() != 'mec':
        raise NotImplementedError('MEC is only supported instrument.')
    #TODO this ::-1 flips the reference pixel. Why are we doing this?
    return CONEX2PIXEL(position[0], position[1], slopes=conex_deltas, ref_pix=reference_pixel, ref_con=reference)[::-1]


def roachnum(fl, band, instrument='MEC'):
    if instrument.lower() == 'darkness':
        return DARKNESS_FL_NUM_MAP['{}{}'.format(fl, band)]
    elif instrument.lower() == 'xkid':
        return XKID_FL_NUM_MAP['{}{}'.format(fl, band)]
    elif instrument.lower() == 'mec':
        return MEC_FL_NUM_MAP['{}{}'.format(fl, band)]


def guessFeedline(filename):
    try:
        flNum = int(re.search(r'fl\d+', filename, re.IGNORECASE).group()[2:])
    except AttributeError:
        try:
            ip = int(os.path.splitext(filename)[0][-3:])
            flNum = int(MEC_NUM_FL_MAP[ip][:-1])
        except (KeyError, ValueError, IndexError):
            getLogger(__name__).warning('Could not guess feedline from filename {}.')
            raise ValueError('Unable to guess feedline')

    getLogger(__name__).debug('Guessing FL{} for filename {}'.format(flNum, os.path.basename(filename)))
    return flNum
