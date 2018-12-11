"""
SRM - Migrated to DARKNESS-pipeline unchanged 2017-04-09

Author: Julian van Eyken    Date: Apr 30 2013
Definitions of all data flags used by the pipeline.
Currently dictionaries to map flag descriptions to integer values.
May update to use pytables Enums at some point down the road....
"""

#Flat cal. flags:
flatCal = {
           'good':0,                #No flagging.
           'infWeight':1,           #Spurious infinite weight was calculated - weight set to 1.0
           'zeroWeight':2,          #Spurious zero weight was calculated - weight set to 1.0
           'belowWaveCalRange':10,  #Derived wavelength is below formal validity range of calibration
           'aboveWaveCalRange':11,  #Derived wavelength is above formal validity range of calibration
           'undefined':20,          #Flagged, but reason is undefined.
           'undetermined':99,       #Flag status is undetermined.
           }

#Flux cal. flags
fluxCal = {
           'good':0,                #No flagging.
           'infWeight':1,           #Spurious infinite weight was calculated - weight set to 1.0
           'LEzeroWeight':2,        #Spurious less-than-or-equal-to-zero weight was calculated - weight set to 1.0
           'nanWeight':3,           #NaN weight was calculated.
           'belowWaveCalRange':10,  #Derived wavelength is below formal validity range of calibration
           'aboveWaveCalRange':11,  #Derived wavelength is above formal validity range of calibration
           'undefined':20,          #Flagged, but reason is undefined.
           'undetermined':99        #Flag status is undetermined.
           }

# Wavelength calibration flags
waveCal = {0: "histogram fit - converged and validated",
           1: "histogram not fit - not enough data points",
           2: "histogram not fit - too much data (hot pixel)",
           3: "histogram not fit - not enough data left after arrival time cut",
           4: "histogram not fit - not enough data left after negative phase only cut",
           5: "histogram not fit - not enough histogram bins to fit the model",
           6: "histogram not fit - best fit did not converge",
           7: "histogram not fit - best fit converged but failed validation",
           10: "energy fit - converged and validated",
           11: "energy not fit - not enough data points",
           12: "energy not fit - data not monotonic enough",
           13: "energy not fit - best fit did not converge",
           14: "energy not fit - best fit converged but failed validation"}

#Bad pixel calibration flags (including hot pixels, cold pixels, etc.)
badPixCal = {
             'good':0,              #No flagging.
             'hot':1,               #Hot pixel
             'cold':2,              #Cold pixel
             'dead':3,              #Dead pixel
             'undefined':20,        #Flagged, but reason is undefined.
             'undetermined':99      #Flag status is undetermined.
             }

#Beammap flags (stored in beammap file)
beamMapFlags = {
                'good':0,           #No flagging
                'failed':1,         #Beammap failed to place pixel
                'yFailed':2,        #Beammap succeeded in x, failed in y
                'xFailed':3,        #Beammap succeeded in y, failed in x
                'wrongFeedline':4   #Beammap placed pixel in wrong feedline
                }

#Flags stored in HDF5 file. Works as a bitmask to allow for multiple flags
h5FileFlags = {
               'good':0b00000000,               #No flags!
               'noDacTone':0b00000001,          #pixel not given a DAC tone in readout
               'beamMapFailed':0b00000010,      #Bad beammap
               'waveCalFailed':0b00000100,      #No wavecal solution
               'flatCalFailed':0b00001000       #No flatcal solution
               }

HOTPIXEL = badPixCal['hot']
DEADPIXEL = badPixCal['dead']


def valid(flag, error=False):
    """Test flag (or array of flags) for validity"""
    #TODO implement

    valid = True
    invalidflag = 0
    if error and not valid:
        raise ValueError('{} is not a valid flag.'.format(invalidflag))

    return valid