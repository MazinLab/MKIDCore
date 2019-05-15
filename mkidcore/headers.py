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

strLength = 100


def WaveCalDescription(n_wvl):
    wavecal_description = {"pixel_row": UInt16Col(pos=0),  # beam map row
                           "pixel_col": UInt16Col(pos=1),  # beam map column
                           "resid": UInt32Col(pos=2),  # unique resonator id
                           "wave_flag": UInt16Col(pos=3),  # fit flag
                           "soln_range": Float32Col(2, pos=4),  # wavelength range
                           "polyfit": Float64Col(3, pos=5),  # fit polynomial
                           "sigma": Float64Col(n_wvl, pos=6),  # 1 sigma DelE
                           "R": Float64Col(n_wvl, pos=7)}  # E/DelE
    return wavecal_description


def WaveCalDebugDescription(n_wvl, n_fit, max_hist):
    debug_desc = {"pixel_row": UInt16Col(pos=0),  # beam map row
                  "pixel_col": UInt16Col(pos=1),  # beam map column
                  "resid": UInt32Col(pos=2),  # unique resonator id
                  "hist_flag": UInt16Col(n_wvl, pos=3),  # histogram fit flags
                  "has_data": BoolCol(n_wvl, pos=4),  # bool if there is histogram data
                  "bin_width": Float64Col(n_wvl, pos=5),  # bin widths for histograms
                  "poly_cov": Float64Col(9, pos=6)}  # covariance for poly fit
    for i in range(n_wvl):
        # histogram fits
        debug_desc['hist_fit' + str(i)] = Float64Col(n_fit, pos=7 + 4 * i)
        # histogram covariance
        debug_desc['hist_cov' + str(i)] = Float64Col(n_fit ** 2, pos=7 + 4 * i + 1)
        # histogram bin centers
        debug_desc['phase_centers' + str(i)] = Float64Col(max_hist, pos=7 + 4 * i + 2)
        # histogram bin counts
        debug_desc['phase_counts' + str(i)] = Float64Col(max_hist, pos=7 + 4 * i + 3)
    return debug_desc


class WaveCalHeader(IsDescription):
    model_name = StringCol(80)


def FlatCalSoln_Description(nWvlBins=13, max_power=10):
    description = {"resid": UInt32Col(),  # unique resonator id
                    "y": UInt16Col(),  # physical x location - from beam map
                    "x": UInt16Col(),  # physical y location
                    "weight": Float64Col(nWvlBins),  #
                    "spectrum": Float64Col(nWvlBins),  #
                    "err": Float64Col(nWvlBins),
                    "coeff": Float64Col(max_power+1), #
                    "bad": UInt16Col(),
                    "flag": UInt16Col()}  #
    return description


CalLookup_Description = {
    'obs_run': StringCol(strLength),
    'obs_date': StringCol(strLength),
    'obs_tstamp': StringCol(strLength),
    'waveSoln_run': StringCol(strLength),
    'waveSoln_date': StringCol(strLength),
    'waveSoln_tstamp': StringCol(strLength),
    'waveSoln_isMasterCal': BoolCol(),
    'flatSoln_run': StringCol(strLength),
    'flatSoln_date': StringCol(strLength),
    'flatSoln_tstamp': StringCol(strLength),
    'flatSoln_isIllumCal': StringCol(strLength),
    'fluxSoln_run': StringCol(strLength),
    'fluxSoln_date': StringCol(strLength),
    'fluxSoln_tstamp': StringCol(strLength),
    'timeMask_run': StringCol(strLength),
    'timeMask_date': StringCol(strLength),
    'timeMask_tstamp': StringCol(strLength),
    'timeAdjustments_run': StringCol(strLength),
    'timeAdjustments_date': StringCol(strLength),
    'timeAdjustments_tstamp': StringCol(strLength),
    'cosmicMask_run': StringCol(strLength),
    'cosmicMask_date': StringCol(strLength),
    'cosmicMask_tstamp': StringCol(strLength),
    'beammap_run': StringCol(strLength),
    'beammap_date': StringCol(strLength),
    'beammap_tstamp': StringCol(strLength),
    'centroidList_run': StringCol(strLength),
    'centroidList_date': StringCol(strLength),
    'centroidList_tstamp': StringCol(strLength),
}


class ObsHeader(IsDescription):
    target = StringCol(255)
    dataDir = StringCol(255)
    beammapFile = StringCol(255)
    isWvlCalibrated = BoolCol()
    isFlatCalibrated = BoolCol()
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

    metadata = StringCol(4*1024*1024)


class ObsFileCols(IsDescription):
    ResID = UInt32Col(pos=0)
    Time = UInt32Col(pos=1)
    Wavelength = Float32Col(pos=2)
    SpecWeight = Float32Col(pos=3)
    NoiseWeight = Float32Col(pos=4)


timeMaskReasonList = ["unknown",
                      "Flash in r0",
                      "Flash in r1",
                      "Flash in r2",
                      "Flash in r3",
                      "Flash in r4",
                      "Flash in r5",
                      "Flash in r6",
                      "Flash in r7",
                      "Flash in r8",
                      "Flash in r9",
                      "Merged Flash",
                      "cosmic",
                      "poofing",
                      "hot pixel",
                      "cold pixel",
                      "dead pixel",
                      "manual hot pixel",
                      "manual cold pixel",
                      "laser not on",  # Used in flashing wavecals
                      "laser not off",  # Used in flashing wavecals
                      "none"]  # To be used for photon lists where the photon is NOT time-masked.

timeMaskReason = tables.Enum(timeMaskReasonList)


class TimeMask(tables.IsDescription):
    """The pytables derived class that stores time intervals to be masked"""
    tBegin = tables.UInt32Col()  # beginning time of this mask (clock ticks)
    tEnd = tables.UInt32Col()  # ending time of this mask (clock ticks)
    reason = tables.EnumCol(timeMaskReason, "unknown", base='uint8')


# This what is in the binprocessor.c
PhotonNumpyTypeBin = np.dtype([('resID', np.uint32),
                               ('timestamp', np.uint32),
                               ('wvl', np.float32),
                               ('wSpec', np.float32),
                               ('wNoise', np.float32)], align=True)

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
