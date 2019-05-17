import numpy as np
from mkidcore.instruments import DEFAULT_ARRAY_SIZES
from glob import glob
import pkg_resources as pkg
import mkidcore.config
from mkidcore.corelog import getLogger
import copy


from datetime import datetime
import json


class DashboardState(dict):
    def __init__(self, string):
        super(DashboardState, self).__init__()
        self._json = json.loads(string)
        self.update(self._json)
        self.utc = datetime.strptime(self.utc, "%Y%m%d%H%M%S")

    def __repr__(self):
        return json.dumps(self._json)


class Beammap(object):
    """
    Simple wrapper for beammap file.
    Attributes:
        resIDs
        flags
        xCoords
        yCoords
    """
    yaml_tag = u'!bmap'

    def __init__(self, file=None, xydim=None, default='MEC', freqpath=''):
        """
        Constructor.

        INPUTS:
            beammap - either a path to beammap file, instrument name, or
                beammap object.
                    If path, loads data from beammap file.
                    If instrument (either 'mec' or 'darkness'), loads corresponding
                        default beammap.
                    If instance of Beammap, creates a copy
        """
        self.file = file
        self.resIDs = None
        self.flags = None
        self.xCoords = None
        self.yCoords = None
        self.frequencies = None
        self.freqpath = freqpath

        if file is not None:
            self._load(file)
            try:
                self.ncols, self.nrows = xydim
            except TypeError:
                raise ValueError('xydim is a required parameter when loading a beammap from a file')
            if (self.ncols * self.nrows) != len(self.resIDs):
                raise Exception('The dimensions of the beammap entered do not match the beammap read in')
        else:
            try:
                self._load(pkg.resource_filename(__name__, '{}.bmap'.format(default.lower())))
                self.ncols, self.nrows = DEFAULT_ARRAY_SIZES[default.lower()]
            except IOError:
                opt = ', '.join([f.rstrip('.bmap').upper() for f in glob(pkg.resource_filename(__name__, '*.bmap'))])
                raise ValueError('Unknown default beampmap "{}". Options: {}'.format(default, opt))

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_mapping(cls.yaml_tag, dict(file=node.file, nrows=node.nrows, ncols=node.ncols))

    @classmethod
    def from_yaml(cls, constructor, node):
        d = mkidcore.config.extract_from_node(constructor,('file', 'nrows', 'ncols', 'default', 'freqfiles'), node)

        if 'default' in d:
            bmap = cls(default=d['default'])
        else:
            bmap = cls(file=d['file'], xydim=(int(d['ncols']), int(d['nrows'])))

        if 'freqfiles' in d:
            try:
                bmap.loadFrequencies(d['freqfiles'])
            except Exception:
                getLogger(__name__).error('Failed to load frequencies into beammap', exc_info=True)

        return bmap

    def setData(self, bmData):
        """
        Sets resIDs, flags, xCoords, yCoords, (and optionally frequencies) to data in bmData
        INPUTS:
            bmData - Nx4 or Nx5 numpy array in same format as beammap file
        """
        if bmData.shape[1] == 4:
            self.resIDs = np.array(bmData[:, 0], dtype=int)
            self.flags = np.array(bmData[:, 1], dtype=int)
            self.xCoords = np.array(bmData[:, 2])
            self.yCoords = np.array(bmData[:, 3])
        elif bmData.shape[1] == 5:
            self.resIDs = np.array(bmData[:, 0], dtype=int)
            self.flags = np.array(bmData[:, 1], dtype=int)
            self.xCoords = np.array(bmData[:, 2])
            self.yCoords = np.array(bmData[:, 3])
            self.frequencies = np.array(bmData[:, 4], dtype=float)
        else:
            raise Exception("This data is not in the proper format")

    def _load(self, filename):
        """
        Loads beammap data from filename
        """
        self.file = filename
        getLogger(__name__).debug('Reading {}'.format(self.file))
        self.resIDs, self.flags, self.xCoords, self.yCoords = np.loadtxt(filename, unpack=True)

    def loadFrequencies(self, filepath):
        self.freqpath = filepath
        powerSweeps = glob(filepath)
        if not powerSweeps:
            raise FileNotFoundError('No powersweeps found matching {}'.format(filepath))
        psData = np.loadtxt(powerSweeps[0])
        for sweep in powerSweeps[1:]:
            psData = np.concatenate((psData, np.loadtxt(sweep)))
        self.frequencies = np.full(self.resIDs.shape, np.nan)
        # psData has the form [Resonator ID, Frequency (Hz), Attenuation (dB)]
        for rID, freq, _ in psData:
            self.frequencies[self.resIDs == rID] = freq / (10 ** 6)

    def save(self, filename, forceIntegerCoords=False):
        """
        Saves beammap data to file.
        INPUTS:
            filename - full path of save file
            forceIntegerCoords - if true floors coordinates and saves as integers
        """
        if forceIntegerCoords:
            fmt = '%4i %4i %4i %4i'
        else:
            fmt = '%4i %4i %0.5f %0.5f'
        np.savetxt(filename, np.transpose([self.resIDs, self.flags, self.xCoords, self.yCoords]), fmt=fmt)

    def copy(self):
        """
        Returns a deep copy of itself
        """
        return copy.deepcopy(self)

    def resIDat(self, x, y):
        return self.resIDs[(np.floor(self.xCoords) == x) & (np.floor(self.yCoords) == y)]

    def getResonatorsAtCoordinate(self, x, y):
        resonators = [self.getResonatorData(r) for r in  self.resIDat(x,y)]
        return resonators

    def get(self, attribute='', flNum=None):
        """
        :params attribute and flNum:
        :return the values of the attribute for a single feedline (denoted by the first number of its resID:
        for use in the beammap shifting code
        """
        if attribute:
            x = self.getBeammapAttribute(attribute)
        else:
            x = None
            raise Exception("This attribute does not exist")
        if flNum:
            mask = flNum == np.floor(self.resIDs / 10000)
        else:
            mask = np.ones_like(self.resIDs, dtype=bool)
        if x.shape == mask.shape:
            return x[mask]
        else:
            raise Exception('Your attribute contained no data')

    def getBeammapAttribute(self, attribute=''):
        """
        :param attribute:
        :return list of attribute values, the length of the beammap object:
        This is for use in the get function
        """
        if attribute.lower() == 'resids':
            return self.resIDs
        elif attribute.lower() == 'flags':
            return self.flags
        elif attribute.lower() == 'xcoords':
            return self.xCoords
        elif attribute.lower() == 'ycoords':
            return self.yCoords
        elif attribute.lower() == 'frequencies':
            return self.frequencies
        else:
            raise Exception('This is not a valid Beammap attribute')

    def getResonatorData(self, resID):
        index = np.where(self.resIDs == resID)[0][0]  #TODO Noah don't use where!
        resonator = [int(self.resIDs[index]), int(self.flags[index]), int(self.xCoords[index]), int(self.yCoords[index]),
                     float(self.frequencies[index])]
        return resonator

    def beammapDict(self):
        return {'resID': self.resIDs, 'freqCh': self.freqs, 'xCoord': self.xCoords,
                'yCoord': self.yCoords, 'flag': self.flags}

    @property
    def failmask(self):
        mask = np.ones((self.nrows, self.ncols), dtype=bool)
        use = (self.yCoords.astype(int) < self.nrows) & (self.xCoords.astype(int) < self.ncols)
        mask[self.yCoords[use].astype(int), self.xCoords[use].astype(int)] = self.flags[use] != 0
        return mask

    @property
    def residmap(self):
        map = np.zeros((self.ncols, self.nrows), dtype=self.resIDs.dtype)
        use = (self.yCoords.astype(int) < self.nrows) & (self.xCoords.astype(int) < self.ncols)
        map[self.xCoords[use].astype(int), self.yCoords[use].astype(int)] = self.resIDs
        return map

    @property
    def flagmap(self):
        map = np.zeros((self.ncols, self.nrows), dtype=self.flags.dtype)
        use = (self.yCoords.astype(int) < self.nrows) & (self.xCoords.astype(int) < self.ncols)
        map[self.xCoords[use].astype(int), self.yCoords[use].astype(int)] = self.flags
        return map

    def __repr__(self):
        return '<file={}, ncols={}, nrows={}, freqpath={}>'.format(self.file, self.ncols, self.nrows, self.freqpath)

    def __str__(self):
        return 'File: "{}"\nWell Mapped: {}'.format(self.file, self.nrows * self.ncols - (self.flags!=0).sum())



mkidcore.config.yaml.register_class(Beammap)