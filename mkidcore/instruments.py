import re
from mkidcore.corelog import getLogger
import os
import numpy as np

MEC_FEEDLINE_INFO = dict(num=10, width=14, length=146)
DARKNESS_FEEDLINE_INFO = dict(num=5, width=25, length=80)

DEFAULT_ARRAY_SIZES = {'mec': (140, 146), 'darkness': (80, 125)}

MEC_NUM_FL_MAP = {236: '1a', 237: '1b', 238: '5a', 239: '5b',
                  220: '6a', 221: '6b', 222: '7a', 223: '7b', 232: '8a',
                  233: '8b', 228: '9a', 229: '9b', 224: '10a', 225: '10b'}
MEC_FL_NUM_MAP = {v: str(k) for k, v in MEC_NUM_FL_MAP.items()}


def CONEX2PIXEL(xCon, yCon):
    """ Emprically determined """
    # from scipy.optimize import curve_fit
    # xCon0 = -0.035
    # xCon1 = 0.23
    # xCon2 = 0.495
    #
    # yCon0 = -0.76
    # yCon1 = -0.38
    # yCon2 = 0.0
    # yCon3 = 0.38
    #
    # xPos0array = np.array([125.46351537124369, 124.79156638384541])
    # xPos1array = np.array([107.98640545380867, 106.53992257621843, 106.04177093203712])
    # xPos2array = np.array([93.809781273378277, 93.586178673966316, 91.514837557492427, 89.872003744327927])
    #
    # yPos0array = np.array([36.537397207881689])
    # yPos1array = np.array([61.297923464154792, 61.535802615842933, 61.223871938056725])
    # yPos2array = np.array([88.127237564834743, 90.773675516601259, 90.851982786156569])
    # yPos3array = np.array([114.66071882865981, 115.42948957872515])
    #
    # xPos0 = np.median(xPos0array)
    # xPos1 = np.median(xPos1array)
    # xPos2 = np.median(xPos2array)
    #
    # yPos0 = np.median(yPos0array)
    # yPos1 = np.median(yPos1array)
    # yPos2 = np.median(yPos2array)
    # yPos3 = np.median(yPos3array)
    #
    # xPos0err = np.std(xPos0array)
    # xPos1err = np.std(xPos1array)
    # xPos2err = np.std(xPos2array)
    #
    # yPos0err = np.std(yPos0array)
    # yPos1err = np.std(yPos1array)
    # yPos2err = np.std(yPos2array)
    # yPos3err = np.std(yPos3array)
    #
    # xConFit = np.array([xCon0, xCon1, xCon2])
    # xPosFit = np.array([xPos0, xPos1, xPos2])
    # xPoserrFit = np.array([xPos0err, xPos1err, xPos2err])
    #
    # yConFit = np.array([yCon0, yCon1, yCon2, yCon3])
    # yPosFit = np.array([yPos0, yPos1, yPos2, yPos3])
    # yPoserrFit = np.array([np.sqrt(yPos0array[0]), yPos1err, yPos2err, yPos3err])

    def func(x, slope, intercept):
        return x * slope + intercept

    # xopt, xcov = curve_fit(func, xConFit, xPosFit, sigma=xPoserrFit)
    # yopt, ycov = curve_fit(func, yConFit, yPosFit, sigma=yPoserrFit)

    xopt = np.array([-65.43754816, 122.74171408])
    yopt = np.array([70.84760994, 88.23558729])

    def con2Pix(xCon, yCon, func):
        return [func(xCon, *xopt), func(yCon, *yopt)]

    xPos, yPos = con2Pix(xCon, yCon, func)

    return [-xPos, -yPos]



def roachnum(fl, band, instrument='MEC'):
    if instrument.lower() != 'mec':
        raise NotImplementedError
    return MEC_FL_NUM_MAP['{}{}'.format(fl, band)]


def guessFeedline(filename):
    # TODO generaize and find a home for this function
    try:
        flNum = int(re.search('fl\d', filename, re.IGNORECASE).group()[-1])
    except AttributeError:
        try:
            ip = int(os.path.splitext(filename)[0][-3:])
            flNum = int(MEC_NUM_FL_MAP[ip][0])
        except (KeyError, ValueError, IndexError):
            getLogger(__name__).warning('Could not guess feedline from filename {}.')
            raise ValueError('Unable to guess feedline')

    getLogger(__name__).debug('Guessing FL{} for filename {}'.format(flNum, os.path.basename(filename)))
    return flNum
