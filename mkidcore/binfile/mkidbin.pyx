"""
When updating this code:
You must also recompile the setup.py file located in the current directory
which contains the information to make(compile) the cythonized file.
(in current repository, in .../MKIDPipeline dir)
$ python setup.py build_ext --inplace
"""
import numpy as np
cimport numpy as np
import os
from mkidcore.corelog import getLogger
from mkidcore.objects import Beammap
# from mkidcore.headers import PhotonNumpyType as np_photon
# from mkidcore.headers import PhotonNumpyTypeBin as np_photon_bin
import ctypes

PHOTON_BIN_SIZE_BYTES = 8
PHOTON_SIZE_BYTES = 4*4


# This what is in the binprocessor.c
PhotonNumpyTypeBin = np.dtype([('resID', np.uint32),
                               ('time', np.uint32),
                               ('wavelength', np.float32),
                               ('baseline', np.float32)
                               ], align=True)

# PhotonNumpyType and PhotonCType are based on what we get back from an H5 file (based on PhotonDescription)
PhotonNumpyType = np.dtype([('resID', np.uint32),
                            ('time', np.uint32),
                            ('wavelength', np.float32),
                            ('weight', np.float32)])


class PhotonCType(ctypes.Structure):
    _fields_ = [('resID', ctypes.c_uint32),
                ('time', ctypes.c_uint32),
                ('wavelength', ctypes.c_float),
                ('weight', ctypes.c_float)]

np_photon = PhotonNumpyType
np_photon_bin = PhotonNumpyTypeBin

cdef extern from "binprocessor.h":
    struct photon
    long extract_photons(const char *dname, unsigned long start, unsigned long inttime,
                     long *DiskBeamMap, int n_bm_entries, unsigned int bmap_ncol,
                     unsigned int bmap_nrow, unsigned long n_max_photons, photon* photons, int verbose);
    long extract_photons_dummy(const char *dname, unsigned long start, unsigned long inttime, const char *bmap,
                               unsigned int x, unsigned int y, unsigned long n_max_photons, photon* photons)
    long cparsebin(const char *fName, unsigned long max_len, float* baseline, float* wavelength,
                   unsigned long long* timestamp, unsigned int* ycoord, unsigned int* xcoord, unsigned int* roach)


def extract(directory, start, inttime, beammap, x, y, include_baseline=False, verbose=0):
    files = [os.path.join(directory, '{}.bin'.format(t)) for t in range(start-1, start+inttime+1)]
    files = filter(os.path.exists, files)
    if isinstance(beammap, str):
        beammap = Beammap(beammap, xydim=(x, y))

    if np.ceil(inttime*1e6) > 2**32:
        raise ValueError('Integration times longer than 4294 s are not supported due to uint32 rollover')

    bmarr = np.vstack((beammap.resIDs, beammap.flags, beammap.xCoords, beammap.yCoords)).T
    if np.any(np.isnan(bmarr)):
        raise Exception('NaNs in beammap')
    if np.any((beammap.xCoords >= x) | (beammap.xCoords < 0) | (beammap.yCoords >= y) | (beammap.yCoords < 0)):
        raise Exception('Beammap coords out of range')
    bmarr = np.ascontiguousarray(bmarr.astype(int)) #bmarr is nPix x 4
    n_bm_entries = int(bmarr.shape[0])

    n_max_photons = int(np.ceil(sum([os.stat(f).st_size for f in files])/PHOTON_BIN_SIZE_BYTES))
    getLogger(__name__).debug('Calling C to extract ~{:g} photons, will require ~{:.1f}GB of RAM'.format(n_max_photons,
                                                                                   n_max_photons*PHOTON_SIZE_BYTES/1024/1024/1024))
    photons = np.zeros(n_max_photons, dtype=np_photon_bin)
    photons = np.ascontiguousarray(photons)
    nphotons = extract_photons(directory.encode('UTF-8'), start, inttime, <long*>np.PyArray_DATA(bmarr), n_bm_entries,
                            x, y, n_max_photons, <photon*> np.PyArray_DATA(photons), verbose)
    getLogger(__name__).debug('C code returned {} photons'.format(nphotons))
    photons = photons[:nphotons]

    baselines = photons['baseline']
    baseline_median = np.median(baselines)
    getLogger(__name__).debug('BL median is ' + str(baseline_median))
    photons2 = np.zeros(nphotons, dtype=np_photon)

    photons2['wavelength'] = photons['wavelength']
    if not include_baseline:
        photons2['wavelength'] += photons['baseline'] - baseline_median
    photons2['resID'] = photons['resID']
    photons2['time'] = photons['time']
    photons2['weight'] = 1.0
    return photons2


def extract_fake(nphotons, start=1547683242, intt=150, nres=20000):
    photons = np.zeros(nphotons, dtype=np_photon)
    photons['resID'] = np.random.randint(0, nres, nphotons, np.uint32)
    photons['time'] = np.random.randint(start,start+intt, nphotons, np.uint32)
    photons['wavelength'] = np.random.random(nphotons)
    photons['weight'] = 1.0
    photons['baseline'] = np.random.random(nphotons)
    return photons


def test(nphot=10):
    #see https://stackoverflow.com/questions/17239091/cython-memoryviews-from-array-of-structs
    #https://cython.readthedocs.io/en/latest/src/userguide/memoryviews.html
    photons = np.zeros(nphot, dtype=np_photon)
    photons = np.ascontiguousarray(photons)

    getLogger(__name__).debug('Calling C to extract dummy ~{:g} photons, will require ~{:.1f}GB of RAM'.format(nphot,
                                                                                                         nphot*PHOTON_SIZE_BYTES/1024/1024/1024))
    photons['resID'] = np.arange(nphot)
    photons['time'] = np.arange(nphot)*2
    photons['wavelength'] = np.ones(nphot)
    photons['weight'] = np.ones(nphot)*2
    photons['baseline'] = np.ones(nphot)*4

    ret = extract_photons_dummy('/a/test/dir/'.encode('UTF-8'), 123456789, 54321, '/a/test/beammap'.encode('UTF-8'),
                                111, 222, nphot, <photon*> np.PyArray_DATA(photons))
    getLogger(__name__).debug('C code returned {} photons'.format(ret))

    return photons


def parse(file,_n=0):
    """
    Created by KD and JB Sept 2018
    This cython function will take an input .bin file and send it to be parsed to
    with a .c file and return the data as a python struct. The parsing is
    done in a program binprocessor.c/binprocessor.h
    The parsed data has the full timestamp created from adding the header and
    data packet timestamps in the .bin files.
    The input .bin file to the function contains both header packets and
    "fake photon" data, which is a photon created by the firmware to end an
    ethernet frame. The firmware is set to end a fframe either when there are
    100 photons in the frame or the clock reaches the next 0.5 ms. In the latter
    casse, the firmware MUST generate a fake photon to end the frame. These
    fake photons are not removed in the binlib.c code (they could be. We remove
    them here in the cython file. We have to create a new array, even though it is memory
    intensive, because you cannot change a numpy array's shape (easily).
    File is called by:
    p = mkidbin.parse("fname.bin",n)
    Returns
    p.base = baseline
    p.phase = phase
    p.tstamp = timestamp
    p.y = ycoord
    p.x = xcoord
    p.roach = roachnum
    """

    # Creating pointers to memory bocks that the binlib.c code will fill
    n = int(max(os.stat(file).st_size/8, _n))
    baseline   = np.empty(n, dtype=np.float32)
    wavelength = np.empty(n, dtype=np.float32)
    time  = np.empty(n, dtype=np.uint64)
    y = np.empty(n, dtype=np.uint32)
    x = np.empty(n, dtype=np.uint32)
    roachnum = np.empty(n, dtype=np.uint32)

    # Calling parsebin from binlib.c
    # npackets is the number of real+fake photons processed by binlib.c
    npackets = cparsebin(file.encode('UTF-8'), n,
                 <float*>np.PyArray_DATA(baseline),
                 <float*>np.PyArray_DATA(wavelength),
                 <unsigned long long*>np.PyArray_DATA(time),
                 <unsigned int*>np.PyArray_DATA(y),
                 <unsigned int*>np.PyArray_DATA(x),
                 <unsigned int*>np.PyArray_DATA(roachnum))
    getLogger(__name__).debug("number of parsed photons = {}".format(npackets))

    if npackets>n:
        return parse(file,abs(npackets))
    elif npackets<0:
        errors = {-1:'Data not found'}
        raise RuntimeError(errors.get(npackets, 'Unknown Error: {}'.format(npackets)))

    # Create new struct from output from binlib.c
    # What this does is only grab the elements of the arrays that are real valued
    # This essentially clips the data since we declared it to be as long as the .bin
    #  file, but some of those lines were headers, which are now empty in the returned arrays
    #  We also combine the arrays into a single struct. It's a for loop, but its actually a fast one
    dt  = np.dtype([('baseline', float),('phase', float), ('tstamp', np.uint64),('y', int), ('x', int),('roach', int)])
    cdef p = np.zeros(npackets,dtype=dt)
    for name, x in zip(dt.names, [baseline[:npackets],wavelength[:npackets],
                                  time[:npackets],y[:npackets],x[:npackets],roachnum[:npackets]]):
        p[name] = x
    p = p.view(np.recarray)

    # Remove Fake Photons
    #   fake photons translate to x=511 when you read the bitvalues as numbers
    #   we just throw them away since they aren't useful to anybody
    ret = p[p.x != 511]

    return ret
