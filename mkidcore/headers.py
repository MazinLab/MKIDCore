"""
CalHeaders.py

Author: Seth Meeker 2017-04-09
Updated from Original in ARCONS-pipeline for DARKNESS-pipeline

Contains the pytables description classes for certain cal files
"""

import tables
from tables import *
import numpy as np
import ctypes

METADATA_BLOCK_BYTES=4*1024*1024
strLength = 100


class ObsHeader(IsDescription):
    target = StringCol(255)
    dataDir = StringCol(255)
    beammapFile = StringCol(255)
    isWvlCalibrated = BoolCol()
    isBadPixMasked = BoolCol()
    isFlatCalibrated = BoolCol()
    isFluxCalibrated = BoolCol()
    isSpecCalibrated = BoolCol()
    isLinearityCorrected = BoolCol()
    isPhaseNoiseCorrected = BoolCol()
    isPhotonTailCorrected = BoolCol()
    timeMaskExists = BoolCol()
    startTime = Int32Col()
    expTime = Int32Col()
    wvlBinStart = Float32Col()
    wvlBinEnd = Float32Col()
    energyBinWidth = Float32Col()
    wvlCalFile = StringCol(255)
    fltCalFile = StringCol(255)
    
    metadata = StringCol(METADATA_BLOCK_BYTES)


class ObsFileCols(IsDescription):
    ResID = UInt32Col(pos=0)
    Time = UInt32Col(pos=1)
    Wavelength = Float32Col(pos=2)
    SpecWeight = Float32Col(pos=3)
    NoiseWeight = Float32Col(pos=4)


# This what is in the binprocessor.c
PhotonNumpyTypeBin = np.dtype([('resID', np.uint32),
                               ('timestamp', np.uint32),
                               ('wvl', np.float32),
                               ('wSpec', np.float32),
                               ('wNoise', np.float32),
                               ('baseline', np.float32)
                               ], align=True)

# PhotonNumpyType and PhotonCType are based on what we get back from an H5 file (based on ObsFileCols)
PhotonNumpyType = np.dtype([('ResID', np.uint32),
                            ('Time', np.uint32),
                            ('Wavelength', np.float32),
                            ('SpecWeight', np.float32),
                            ('NoiseWeight', np.float32)])


class PhotonCType(ctypes.Structure):
    _fields_ = [('ResID', ctypes.c_uint32),
                ('Time', ctypes.c_uint32),
                ('Wavelength', ctypes.c_float),
                ('SpecWeight', ctypes.c_float),
                ('NoiseWeight', ctypes.c_float)]
