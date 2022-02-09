import numpy as np
from mkidcore.corelog import getLogger





PROBLEM_FLAGS = ('pixcal.hot', 'pixcal.cold', 'pixcal.dead', 'beammap.noDacTone', 'wavecal.bad',
                 'wavecal.failed_validation', 'wavecal.failed_convergence', 'wavecal.not_monotonic',
                 'wavecal.not_enough_histogram_fits', 'wavecal.no_histograms',
                 'wavecal.not_attempted')  # TODO finish or make flags objects and build programatically
# flags for indicating something may be up with the wavecal
# linear fits are only questionable if they are the fallback fit type
WAVECAL_QUESTIONABLE_FLAGS = ('wavecal.histogram_fit_problems', 'wavecal.linear')


class Flag(object):
    def __init__(self, name, bit, description):
        self.name = str(name)
        self.description = str(description)
        self.bit = int(bit)
        if self.bit < 0:
            raise ValueError('bit must be >=0')

    @property
    def bitmask(self):
        return 1 << self.bit

    def __str__(self):
        return "Flag {} (bit {})".format(self.name, self.bit)


class FlagSet(object):
    def __init__(self, flags):
        from collections import defaultdict
        collision = defaultdict(lambda: set())
        for f in flags:
            collision[f.bit].add(f)
            collision[f.name].add(f)
        badflags = []
        for k, v in collision.items():
            if len(v) > 1:
                badflags.append(v)
        if badflags:
            raise ValueError("Flags must not use the same bits or name: {}".format(badflags))
        self.flags = {f.name: f for f in flags}

    @property
    def names(self):
        bits = [i.bit for i in self.flags.values()]
        return tuple(zip(*sorted(zip(bits, self.flags.keys()))))[1]

    @staticmethod
    def define(*flags):
        return FlagSet([Flag(*f) if not isinstance(f, Flag) else f for f in flags])

    def bitmask(self, flags, unknown='error'):
        """Return the bitmask corresponding to the flags"""
        if not flags:
            return np.uint64(0)
        if isinstance(flags, str):
            flags = [flags]

        def notify(f):
            if unknown[0] == 'w':
                getLogger(__name__).warning('Flag {} not in flag set, excluded from bitmask'.format(f))
            elif unknown[0] == 'e':
                raise ValueError('Flag {} not in flag set'.format(f))
            return 0

        return np.bitwise_or.reduce([2 ** self.flags[f].bit if f in self.flags else notify(f) for f in flags])

    def flag_names(self, bitmask):
        return tuple([name for name, f in self.flags.items() if f.bitmask & bitmask])

    def valid(self, bitmask, error=True):
        if np.isscalar(bitmask):
            bitmask = np.array([bitmask])
        if (bitmask < 2**len(self.flags)).all():
            return True
        elif error:
            raise ValueError('Bitmask invalid for flagset.')
        return False

    def __iter__(self):
        for f in self.flags.values():
            yield f


# DO not edit these without considering MKIDReadout!
BEAMMAP_FLAGS = FlagSet.define(
    ('noDacTone', 1, 'Pixel not read out'),
    ('failed', 2, 'Beammap failed to place pixel'),
    ('yFailed', 3, 'Beammap succeeded in x, failed in y'),
    ('xFailed', 4, 'Beammap succeeded in y, failed in x'),
    ('double', 5, 'Multiple locations found for pixel'),
    ('wrongFeedline', 6, 'Beammap placed pixel in wrong feedline'),
    ('duplicatePixel', 7, 'Beammap placed pixel on top of another one, and no neighbor could be found'),
)


# for legacy mkidreadout use, must be in sync with BEAMAP_FLAG bits above
# Beammap flags (stored in beammap file)   #If these aren't bit flags then the & eeds to be converted to an ==
beammap = {'good': 0,
           'noDacTone': 1,  # Pixel not read out
           'failed': 2,  # Beammap failed to place pixel
           'yFailed': 3,  # Beammap succeeded in x, failed in y
           'xFailed': 4,  # Beammap succeeded in y, failed in x
           'double': 5,  # Multiple locations found for pixel
           'wrongFeedline': 6,  # Beammap placed pixel in wrong feedline
           'duplicatePixel': 7  # Beammap placed pixel on top of another one, and no neighbor could be found
           }
# Flags for the optimal filter routine
filters = {'not_started': 0,  # calculation has not been started.
           'pulses_computed': 1,  # finished finding the pulses.
           'noise_computed': 2,  # finished the noise calculation.
           'template_computed': 4,  # finished the template calculation.
           'filter_computed': 8,  # finished the filter calculation.
           'bad_pulses': 16,  # not enough pulses found satisfying the configuration conditions.
           'bad_noise': 32,  # noise calculation failed. Assuming white noise.
           'bad_template': 64,  # template calculation failed. Using the fallback template.
           'bad_template_fit': 128,  # the template fit failed. Using the raw data.
           'bad_filter': 256}  # filter calculation failed. Using the template as a filter.
