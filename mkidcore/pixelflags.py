"""
SRM - Migrated to DARKNESS-pipeline unchanged 2017-04-09

Author: Julian van Eyken    Date: Apr 30 2013
Definitions of all data flags used by the pipeline.
Currently dictionaries to map flag descriptions to integer values.
May update to use pytables Enums at some point down the road....
"""

# Flat cal. flags:
flatcal = {'good': 0,  # No flagging.
           'infWeight': 1,  # Spurious infinite weight was calculated - weight set to 1.0
           'zeroWeight': 2,  # Spurious zero weight was calculated - weight set to 1.0
           'belowWaveCalRange': 10,  # Derived wavelength is below formal validity range of calibration
           'aboveWaveCalRange': 11,  # Derived wavelength is above formal validity range of calibration
           'undefined': 20,  # Flagged, but reason is undefined.
           'undetermined': 99,  # Flag status is undetermined.
           }

# Spectral cal. flags
speccal = {'good': 0,  # No flagging.
           'infWeight': 1,  # Spurious infinite weight was calculated - weight set to 1.0
           'LEzeroWeight': 2,  # Spurious less-than-or-equal-to-zero weight was calculated - weight set to 1.0
           'nanWeight': 3,  # NaN weight was calculated.
           'belowWaveCalRange': 10,  # Derived wavelength is below formal validity range of calibration
           'aboveWaveCalRange': 11,  # Derived wavelength is above formal validity range of calibration
           'undefined': 20,  # Flagged, but reason is undefined.
           'undetermined': 99  # Flag status is undetermined.
           }

# Bad pixel calibration flags (including hot pixels, cold pixels, etc.)
badpixcal = {'good': 0,  # No flagging.
             'hot': 1,  # Hot pixel
             'cold': 2,  # Cold pixel
             'dead': 3,  # Dead pixel
             'undefined': 20,  # Flagged, but reason is undefined.
             'undetermined': 99  # Flag status is undetermined.
             }

# Beammap flags (stored in beammap file)
beamMapFlags = {'good': 0,  # No flagging
                'failed': 1,  # Beammap failed to place pixel
                'yFailed': 2,  # Beammap succeeded in x, failed in y
                'xFailed': 3,  # Beammap succeeded in y, failed in x
                'wrongFeedline': 4  # Beammap placed pixel in wrong feedline
                }

# Flags stored in HDF5 file. Works as a bitmask to allow for multiple flags
h5FileFlags = {'good': 0,  # No flags!
               'noDacTone': 1,  # pixel not given a DAC tone in readout
               'beamMapFailed': 2,  # Bad beammap
               'waveCalFailed': 4,  # No wavecal solution
               'flatCalFailed': 8,  # No flatcal solution
               'hotPixel': 16}

HOTPIXEL = h5FileFlags['hotPixel']
GOODPIXEL = 0


def valid(flag, error=False):
    """Test flag (or array of flags) for validity"""
    # TODO implement

    valid = True
    invalidflag = 0
    if error and not valid:
        raise ValueError('{} is not a valid flag.'.format(invalidflag))

    return valid
