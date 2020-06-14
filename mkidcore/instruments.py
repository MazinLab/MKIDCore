import re
from mkidcore.corelog import getLogger
import os
import numpy as np
import matplotlib.pyplot as plt

MEC_FEEDLINE_INFO = dict(num=10, width=14, length=146)
DARKNESS_FEEDLINE_INFO = dict(num=5, width=25, length=80)

FEEDLINE_INFO = {'mec': MEC_FEEDLINE_INFO, 'darkness':DARKNESS_FEEDLINE_INFO}

DEFAULT_ARRAY_SIZES = {'mec': (140, 146), 'darkness': (80, 125)}


MEC_NUM_FL_MAP = {228: '1a', 229: '1b', 238: '5a', 239: '5b', 220: '6a', 221: '6b', 
                  222: '7a', 223: '7b', 232: '8a', 233: '8b', 
                  236: '9a', 237: '9b', 224: '10a', 225: '10b'}

#NB FLs are arbitrary as instrument isn't installed
DARKNESS_NUM_FL_MAP = {112: '1a', 114: '1b', 115: '5a', 116: '5b',
                       117: '6a', 118: '6b', 119: '7a', 120: '7b', 121: '8a',
                       122: '8b'}

MEC_FL_NUM_MAP = {v: str(k) for k, v in MEC_NUM_FL_MAP.items()}

DARKNESS_FL_NUM_MAP = {v: str(k) for k, v in MEC_NUM_FL_MAP.items()}

ROACHES = {'mec': MEC_NUM_FL_MAP.keys(), 'darkness': DARKNESS_NUM_FL_MAP.keys(),
           'bluefors': []}
ROACHESA = {'mec': [k for k, v in MEC_NUM_FL_MAP.items() if 'a' in v],
            'darkness': [k for k, v in DARKNESS_NUM_FL_MAP.items() if 'a' in v],
            'bluefors': []}
ROACHESB = {'mec': [k for k, v in MEC_NUM_FL_MAP.items() if 'b' in v],
            'darkness': [k for k, v in DARKNESS_NUM_FL_MAP.items() if 'b' in v],
            'bluefors': []}
for k in list(ROACHES):
    ROACHES[k.upper()] = ROACHES[k]
for k in list(ROACHESA):
    ROACHESA[k.upper()] = ROACHESA[k]
for k in list(ROACHESB):
    ROACHESB[k.upper()] = ROACHESB[k]


def CONEX2PIXEL(xCon, yCon):
    """
    Emprically determined from a white light dither done over the whole array on 12/13/19
    -Sarah Steiger
    """
    # from scipy.optimize import curve_fit

    # psf_centers = [[65.0, 68.0],[77.0, 106.0],[89.0, 106.0],[42.0, 108.0],[42.0, 115.0], [124.0, 82.0],[101.0, 122.0],
    #                [66.0, 92.0],[55.0, 107.0],[137.0, 74.0],[34.0, 100.0],[32.0, 94.0],[38.0, 62.0],[54.0, 61.0],
    #                [123.0, 112.0],[123.0, 67.0],[114.0, 91.0],[33.0, 77.0],[90.0, 74.0],[124.0, 104.0],[136.0, 105.0],
    #                [80.0, 82.0],[79.0, 113.0],[114.0, 82.0],[122.0, 61.0],[123.0, 76.0],[33.0, 84.0],[113.0, 75.0],
    #                [80.0, 66.0],[32.0, 108.0],[89.0, 114.0],[123.0, 129.0],[53.0, 131.0],[76.0, 132.0],[32.0, 131.0],
    #                [49.0, 61.0],[88.0, 122.0],[137.0, 65.0],[101.0, 107.0],[114.0, 60.0],[66.0, 75.0],[122.0, 121.0],
    #                [80.0, 99.0],[114.0, 106.0],[65.0, 100.0],[42.0, 123.0],[135.0, 129.0],[53.0, 91.0],[64.0, 106.0],
    #                [136.0, 114.0],[112.0, 121.0],[134.0, 120.0]]
    #
    # dither_pos = [[0.327, -0.25],[-0.283, -0.083],[-0.283, 0.083],[-0.283, -0.583],[-0.406, -0.584],[0.083, 0.583],
    #               [-0.528, 0.25],[-0.039, -0.25], [-0.283, -0.417],[0.206, 0.75],[-0.161, -0.75],[-0.039, -0.75],
    #               [0.45, -0.75], [0.45, -0.417], [-0.406, 0.583],[0.328, 0.583],[-0.039, 0.416], [0.205, -0.75],
    #               [0.205, 0.083], [-0.283, 0.583], [-0.283, 0.75], [0.083, -0.084],[-0.406, -0.084], [0.083, 0.417],
    #               [0.45, 0.583], [0.206, 0.583],[0.083, -0.75], [0.205, 0.417], [0.328, -0.084], [-0.284, -0.75],
    #               [-0.405, 0.083], [-0.65, 0.583], [-0.65, -0.417], [-0.65, -0.083], [-0.65, -0.75], [0.45, -0.583],
    #               [-0.528, 0.083], [0.328, 0.75], [-0.283, 0.25], [0.45, 0.417], [0.205, -0.25], [-0.528, 0.583],
    #               [-0.161, -0.084], [-0.283, 0.417], [-0.161, -0.25], [-0.528, -0.583], [-0.65, 0.75], [-0.039, -0.417],
    #               [-0.283, -0.25], [-0.406, 0.75], [-0.528, 0.416],[-0.528, 0.75]]
    #
    # xPosFit = np.zeros(len(psf_centers))
    # yPosFit = np.zeros(len(psf_centers))
    #
    # for i, pos in enumerate(psf_centers):
    #     xPosFit[i] = pos[1]
    #     yPosFit[i] = pos[0]
    #
    # xConFit = np.zeros(len(dither_pos))
    # yConFit = np.zeros(len(dither_pos))
    #
    # for i, pos in enumerate(dither_pos):
    #     xConFit[i] = pos[0]
    #     yConFit[i] = pos[1]


    def func(x, slope, intercept):
        return x * slope + intercept
    # 
    #
    # xopt, xcov = curve_fit(func, xConFit, xPosFit)
    # yopt, ycov = curve_fit(func, yConFit, yPosFit)

    def con2Pix(xCon, yCon, func):
        return [func(xCon, *xopt), func(yCon, *yopt)]

    xopt = [-63.36778615, 88.47319224]
    yopt = [68.5940592, 83.7997898]

    xPos, yPos = con2Pix(xCon, yCon, func)

    return [xPos, yPos]


def compute_wcs_ref_pixel(position, center=(0, 0), target_center_at_ref=(0, 0), instrument='mec'):
    """
    A function to convert the connex offset to pixel displacement

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
    position = np.asarray(position)  # asarray converts CommentedSeq type to ndarray
    pix = np.asarray(CONEX2PIXEL(position[0], position[1])) - np.array(CONEX2PIXEL(*center))
    pix += np.asarray(target_center_at_ref).reshape(2)
    return pix[::-1]


def roachnum(fl, band, instrument='MEC'):
    if instrument.lower() == 'darkness':
        return DARKNESS_FL_NUM_MAP['{}{}'.format(fl, band)]
    elif instrument.lower() == 'mec':
        return MEC_FL_NUM_MAP['{}{}'.format(fl, band)]


def guessFeedline(filename):
    # TODO generaize and find a home for this function
    try:
        flNum = int(re.search('fl\d', filename, re.IGNORECASE).group()[-1])
    except AttributeError:
        try:
            ip = int(os.path.splitext(filename)[0][-3:])
            flNum = int(MEC_NUM_FL_MAP[ip][:-1])
        except (KeyError, ValueError, IndexError):
            getLogger(__name__).warning('Could not guess feedline from filename {}.')
            raise ValueError('Unable to guess feedline')

    getLogger(__name__).debug('Guessing FL{} for filename {}'.format(flNum, os.path.basename(filename)))
    return flNum
