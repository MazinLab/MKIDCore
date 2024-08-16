import os
import numpy as np
from mkidcore.instruments import DEFAULT_ARRAY_SIZES
from glob import glob
import pkg_resources as pkg
import mkidcore.config
from mkidcore.corelog import getLogger
import copy
from mkidcore.pixelflags import beammap as beamMapFlags

from datetime import datetime
import json


class TimeStream(object):
    """
    Class for holding a resonator's phase time-stream.

    Args:
        file_path: string
            The file name containing the phase time-stream.
        phase: numpy.ndarray (optional)
            The phase data to use if 'file_path' doesn't exist yet.
        name: any (optional)
            An object that can be used to identify the time stream. It is not
            used directly by this class.
    """
    yaml_tag = u'!ts'

    def __init__(self, file_path, phase=None, name=None):
        self.file_path = file_path
        self.name = name if name is not None else os.path.splitext(os.path.basename(file_path))[0]

        # defer loading data
        self.zip = None
        self.phase = phase

    @property
    def phase(self):
        """The phase time-stream of the resonator."""
        if self._phase is None:
            self._phase = self.zip[self.zip.keys()[0]]
        return self._phase

    @phase.setter
    def phase(self, value):
        self._phase = value

    @property
    def zip(self):
        """A dictionary-like object which lazily loads data from a file."""
        if self._npz is None:
            self._npz = np.load(self.file_path)
        return self._npz

    @zip.setter
    def zip(self, value):
        self._npz = value

    def clear(self):
        """Free memory by removing all file bound attributes."""
        self.phase = None
        self.zip = None

    def save(self):
        """Save the time-stream data to the object's file path."""
        try:
            np.savez(self.file_path, self.phase)
        except IOError:
            path = self.file_path.rsplit('/', 1)
            if len(path) <= 1:
                raise
            getLogger(__name__).info('Making directory: ' + path[0])
            os.mkdir(path[0])
            np.savez(self.file_path, self.phase)

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_mapping(cls.yaml_tag, dict(file=node.file, name=node.name))

    @classmethod
    def from_yaml(cls, constructor, node):
        d = dict(constructor.construct_pairs(node))
        file_path = d.pop("file")
        directory = d.pop("directory", None)
        if directory is not None:
            file_path = os.path.join(directory, os.path.basename(file_path))
        ts = cls(file_path, **d)
        return ts


mkidcore.config.yaml.register_class(TimeStream)


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

    def __init__(self, specifier='MEC', xydim=None, freqpath=''):
        """
        Constructor.

        INPUTS:
            beammap - either a path to beammap file, instrument name, or
                beammap object.
                    If path, loads data from beammap file.
                    If instrument (either 'mec', 'darkness', or 'xkid'), loads corresponding
                        default beammap.
                    If instance of Beammap, creates a copy
        """
        if not os.path.exists(specifier):
            default = specifier
            file = None
        else:
            file = specifier

        self.file = file
        self.resIDs = None
        self.flags = None
        self.xCoords = None
        self.yCoords = None
        self.frequencies = None
        self.attenuations = None
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
        # d = dict(constructor.construct_pairs(node))
        # discarded = [(k, d.pop(k)) for k in d.keys() if k not in ('file', 'nrows', 'ncols', 'default', 'freqfiles')]
        #TODO NB extract_from_node is MUCH faster than d = dict(constructor.construct_pairs(node))

        d = mkidcore.config.extract_from_node(constructor, ('file', 'nrows', 'ncols', 'default', 'freqfiles'), node)

        if 'default' in d:
            bmap = cls(d['default'])
        else:
            bmap = cls(specifier=d['file'], xydim=(int(d['ncols']), int(d['nrows'])))

        if 'freqfiles' in d:
            try:
                bmap.loadFrequencies(d['freqfiles'])
            except Exception:
                if d['freqfiles'] == "":
                    getLogger(__name__).info("No frequency files specified for this beammap!")
                else:
                    getLogger(__name__).warning('Failed to load frequencies into beammap', exc_info=True)

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
        self.attenuations = np.full(self.resIDs.shape, np.nan)
        # psData has the form [Resonator ID, Frequency (Hz), Attenuation (dB)]
        # TODO: move SweepMetadata to core and use that instead
        if psData.shape[1] == 3:
            for rID, freq, atten in psData:
                location = self.resIDs == rID
                self.frequencies[location] = freq / (10 ** 6)
                self.attenuations[location] = atten
        elif psData.shape[1] == 9:
            for rID, _, _, _, _, freq, atten, _, _ in psData:
                location = self.resIDs == rID
                self.frequencies[location] = freq / (10 ** 6)
                self.attenuations[location] = atten
        else:
            raise Exception('Freq file format not supported')

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
        index, = np.where(self.resIDs == resID)[0]
        if index.size>1:
            getLogger(__name__).warning('resID {} is not unique'.format(resID))
        index = index[0]
        resonator = [int(self.resIDs[index]), int(self.flags[index]), int(self.xCoords[index]), int(self.yCoords[index]),
                     float(self.frequencies[index])]
        return resonator

    def getResonatorFlag(self, resID):
        return self.flags[self.resIDs == resID]

    def retuneMap(self, newIDsboardA=None, newIDsboardB=None):
        """
        newIDs takes in the output of the tuneupfrequencies.py Correlator class in the form of an Nx2 txt file. Column 0
        are the old resIDs, column 1 the new resIDs.
        fullFL = True assumes that both boards which read out the feedline are given. If false, an error will be thrown
        if there are conflicts with resonators being reassigned.
        """
        self.reassignmentList = None
        a, b = None, None
        if newIDsboardA is not None:
            a = np.genfromtxt(str(newIDsboardA))
            feedlineGuess = np.floor(np.average(a[~np.isnan(a[:, 0])][:, 0]) / 10000)
        if newIDsboardB is not None:
            b = np.genfromtxt(str(newIDsboardB))
            feedlineGuess = np.floor(np.average(b[~np.isnan(b[:, 0])][:, 0]) / 10000)

        # feedlineGuess = np.floor(np.average(a[~np.isnan(a[:, 0])][:, 0]) / 10000)
        feedlineBase = feedlineGuess * 10000

        if a is not None:
            aMask = []
            for i in range(len(a)):
                if not np.isnan(a[i][0]) and not np.isnan(a[i][1]):
                    if (a[i][0] <= feedlineBase + 1023) and (a[i][1] <= feedlineBase + 1023):
                        aMask.append(True)
                    else:
                        aMask.append(False)
                elif not np.isnan(a[i][0]) and np.isnan(a[i][1]):
                    if (a[i][0] <= feedlineBase + 1023):
                        aMask.append(True)
                    else:
                        aMask.append(False)
                elif np.isnan(a[i][0]) and not np.isnan(a[i][1]):
                    if (a[i][1] <= feedlineBase + 1023):
                        aMask.append(True)
                    else:
                        aMask.append(False)
            a = a[aMask]

        if b is not None:
            bMask = []
            for i in range(len(b)):
                if not np.isnan(b[i][0]) and not np.isnan(b[i][1]):
                    if (b[i][0] >= feedlineBase + 1024) and (b[i][1] >= feedlineBase + 1024):
                        bMask.append(True)
                    else:
                        bMask.append(False)
                elif not np.isnan(b[i][0]) and np.isnan(b[i][1]):
                    if (b[i][0] <= feedlineBase + 1024):
                        bMask.append(True)
                    else:
                        bMask.append(False)
                elif np.isnan(b[i][0]) and not np.isnan(b[i][1]):
                    if (b[i][1] <= feedlineBase + 1024):
                        bMask.append(True)
                    else:
                        bMask.append(False)
            b = b[bMask]

        if a is not None and b is not None:
            self.reassignmentList = np.concatenate((a, b), axis=0)
        elif a is None and b is not None:
            self.reassignmentList = b
        else:
            self.reassignmentList = a

        self.newResIDs = np.full_like(self.resIDs, np.nan)
        self.newFlags = np.full_like(self.flags, np.nan)  # TODO This isn't valid flags are assumed to be ints

        for i in self.reassignmentList:
            if i[2] == 1:
                mask = self.resIDs == i[0]
                self.newResIDs[mask] = i[1]
                self.newFlags[mask] = beamMapFlags['good']
            elif i[2] == 4:
                mask = self.resIDs == i[0]
                self.newResIDs[mask] = i[1]
                self.newFlags[mask] = beamMapFlags['failed']

        if a and b:
            full = True
            mask = np.floor(self.resIDs / 10000) == feedlineGuess
        elif a and not b:
            full = False
            validIDs = [10000*feedlineGuess, 10000*feedlineGuess + 1023]
            mask = (self.resIDs >= validIDs[0]) & (self.resIDs <= validIDs[1])
        else:
            full = False
            validIDs = [10000*feedlineGuess + 1024, 10000*feedlineGuess + 9999]
            mask = (self.resIDs >= validIDs[0]) & (self.resIDs <= validIDs[1])
        old = self.resIDs[mask]
        new = self.newResIDs[mask]
        unused = np.setdiff1d(old, new)

        for i, j in enumerate(self.resIDs):
            if full:
                if (np.floor(j / 10000) == feedlineGuess) and np.isnan(self.newResIDs[i]):
                    # print(unused[0])
                    self.newResIDs[i] = unused[0]
                    if unused[0] in self.reassignmentList[:, 1]:
                        # print(f'noDacTon {unused[0]}')
                        self.newFlags[i] = beamMapFlags['noDacTone']
                    elif unused[0] in self.reassignmentList[:, 0]:
                        # print(f'failed {unused[0]}')
                        self.newFlags[i] = beamMapFlags['failed']
                    else:
                        # print(f'noDacTone2 {unused[0]}')
                        self.newFlags[i] = beamMapFlags['noDacTone']
                    unused = np.delete(unused, 0)
            else:
                if (j >= validIDs[0]) and (j <= validIDs[1]) and np.isnan(self.newResIDs[i]):
                    # print(unused[0])
                    self.newResIDs[i] = unused[0]
                    if unused[0] in self.reassignmentList[:, 1]:
                        # print(f'noDacTon {unused[0]}')
                        self.newFlags[i] = beamMapFlags['noDacTone']
                    elif unused[0] in self.reassignmentList[:, 0]:
                        # print(f'failed {unused[0]}')
                        self.newFlags[i] = beamMapFlags['failed']
                    else:
                        # print(f'noDacTone2 {unused[0]}')
                        self.newFlags[i] = beamMapFlags['noDacTone']
                    unused = np.delete(unused, 0)

        mask2 = mask & (self.flags == 0)

        self.resIDs[mask] = self.newResIDs[mask]
        self.flags[mask2] = self.newFlags[mask2]


    def beammapDict(self):
        return {'resID': self.resIDs, 'freqCh': self.freqs, 'xCoord': self.xCoords,
                'yCoord': self.yCoords, 'flag': self.flags}

    @property
    def shape(self):
        return self.nrows, self.ncols

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
        return 'File: "{}"\n  Well Mapped: {}'.format(self.file, self.nrows * self.ncols - (self.flags!=0).sum())


mkidcore.config.yaml.register_class(Beammap)
