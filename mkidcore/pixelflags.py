"""
SRM - Migrated to DARKNESS-pipeline unchanged 2017-04-09

Author: Julian van Eyken    Date: Apr 30 2013
Definitions of all data flags used by the pipeline.
Currently dictionaries to map flag descriptions to integer values.
May update to use pytables Enums at some point down the road....
"""
import numpy as np
from mkidcore.corelog import getLogger
wavecal = {'bad':1}

# Flat cal. flags:
flatcal = {'inf_weight': 1,  # Spurious infinite weight was calculated - weight set to 1.0
           'zero_eight': 2,  # Spurious zero weight was calculated - weight set to 1.0
           'below_range': 4,  # Derived wavelength is below formal validity range of calibration
           'above_range': 8,  # Derived wavelength is above formal validity range of calibration
           }

# Spectral cal. flags
speccal = {'inf_weight': 1,  # Spurious infinite weight was calculated - weight set to 1.0
           'lz_weight': 2,  # Spurious less-than-or-equal-to-zero weight was calculated - weight set to 1.0
           'nan_weight': 4,  # NaN weight was calculated.
           'below_range': 8,  # Derived wavelength is below formal validity range of calibration
           'above_range': 16,  # Derived wavelength is above formal validity range of calibration
           }

# Bad pixel calibration flags (including hot pixels, cold pixels, etc.)
pixcal = {'hot': 1,  # Hot pixel
          'cold': 2,  # Cold pixel}
          'unstable': 3
          }

# Beammap flags (stored in beammap file)   #If these aren't bit flags then the & eeds to be converted to an ==
beammap = {'noDacTone':1,      #Pixel not read out
                'failed':2,         #Beammap failed to place pixel
                'yFailed':3,        #Beammap succeeded in x, failed in y
                'xFailed':4,        #Beammap succeeded in y, failed in x
                'double':5,         #Multiple locations found for pixel
                'wrongFeedline':6,  #Beammap placed pixel in wrong feedline
                'duplicatePixel':7  #Beammap placed pixel on top of another one, and no neighbor could be found
                }

wcscal = {}
general = {}

#META FLAGS
'beamMapFailed'
'waveCalFailed'
'flatCalFailed'


HOTPIXEL = h5FileFlags['hotPixel']
GOODPIXEL = 0


FLAG_DICTS = {'wavecal': wavecal, 'flatcal': flatcal, 'speccal': speccal, 'wcscal': wcscal, 'beammap': beammap,
              'general': general, 'pixcal': pixcal}

FLAG_LIST = tuple(['{}.{}'.format(k, v) for k in FLAG_DICTS for v in FLAG_DICTS[k]])
FLAG_LIST_BITS = tuple([2**i for i in range(FLAG_LIST.size)])

PROBLEM_FLAGS = ('pixcal.hot', 'beammap.notone', )  # TODO finish or make flags objects and build programatically


def beammap_flagmap_to_h5_flagmap(beammap_flagmap):
    bf = beammap_flagmap.astype(int)  # as type due to legacy issues with flags being used as floats TODO @nswimmer FIX elsewhere and remove
    h5map = np.zeros_like(bf)
    #TODO vectorize
    for i in range(bf.size):     # convert each bit to the new bit
        ndxs = [FLAG_LIST.index('beammap.{}'.format(k)) for k,v in beammap.items() if v & bf[i]]
        h5map.flat[i] = np.bitwise_or.reduce([FLAG_LIST_BITS[ndx] for ndx in ndxs])
    return h5map


def flag_bitmask(flag_names, flag_list=FLAG_LIST):
    return np.bitwise_or.reduce([2 ** i for i, f in enumerate(flag_list) if f in flag_names])


def to_flag_names(flag_group, bitmask):
    return tuple(['{}.{}'.format(flag_group,k) for k, v in FLAG_LIST[flag_group] if v&bitmask])


def problem_flag_bitmask(flag_list):
    return flag_bitmask(PROBLEM_FLAGS, flag_list=flag_list)


def valid(flag, error=False):
    """Test flag (or array of flags) for validity"""
    # TODO implement
    # getLogger(__name__).warning('Flag validity test not yet implemented, assuming valid.')

    valid = True
    if error and not valid:
        raise ValueError('{} is not a valid flag.'.format('FOO'))
    return valid
