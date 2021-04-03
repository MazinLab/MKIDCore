"""Note that this code is necessary for processing of very old (2017b and earlier) data"""

import numpy as np
import tables
from logging import getLogger
import warnings


def _correct_timestamps(timestamps):
    """
    Corrects errors in timestamps due to firmware bug present through PAL2017b.

    Parameters
    ----------
    timestamps: numpy array of integers
        List of timestamps from photon list. Must be in original, unsorted order.

    Returns
    -------
    Array of corrected timestamps, dtype is uint32
    """
    timestamps = np.array(timestamps, dtype=np.int64)  # convert timestamps to signed values
    photonTimestamps = timestamps % 500
    hdrTimestamps = timestamps - photonTimestamps

    for ind in np.where(np.diff(timestamps) < 0)[0] + 1:  # mark locations n where T(n)<T(n-1):
        ndx = np.where(hdrTimestamps == hdrTimestamps[ind])[0]
        hdrTimestamps[ndx[ndx >= ind]] += 500

    x = hdrTimestamps + photonTimestamps
    if np.any(np.diff(x) < 0):
        x = _correct_timestamps(x)

    return x.astype(np.uint32)


def fix_timestamp_bug(file):
    """ Note that"""
    # which writes the same photonlist twice to certain resIDs
    noResIDFlag = 2 ** 32 - 1
    hfile = tables.open_file(file, mode='a')
    beamMap = hfile.root.BeamMap.Map.read()
    photonTable = hfile.get_node('/Photons/PhotonTable/')
    photonList = photonTable.read()

    resIDDiffs = np.diff(photonList['ResID'])
    if np.any(resIDDiffs < 0):
        warnings.warn('Photon list not sorted by ResID! This could take a while...')
        photonList = np.sort(photonList, order='ResID',
                             kind='mergsort')  # mergesort is stable, so time order will be preserved
        resIDDiffs = np.diff(photonList['ResID'])

    resIDBoundaryInds = np.where(resIDDiffs > 0)[
                            0] + 1  # indices in masterPhotonList where ResID changes; ie marks boundaries between pixel tables
    resIDBoundaryInds = np.insert(resIDBoundaryInds, 0, 0)
    resIDList = photonList['ResID'][resIDBoundaryInds]
    resIDBoundaryInds = np.append(resIDBoundaryInds, len(photonList['ResID']))
    correctedTimeListMaster = np.zeros(len(photonList))

    for resID in beamMap:
        resIDInd0 = np.where(resIDList == resID)[0]
        if resID == noResIDFlag or len(resIDInd0) == 0:
            continue
        resIDInd = resIDInd0[0]
        photonList_resID = photonList[resIDBoundaryInds[resIDInd]:resIDBoundaryInds[resIDInd + 1]]
        timeList = photonList_resID['Time']
        timestamps = np.array(timeList, dtype=np.int64)  # convert timestamps to signed values
        repeatTest = np.array(np.where(timestamps == timestamps[0]))
        if len(repeatTest[0]) > 1:
            getLogger(__name__).debug(f"ResID {resID} repeatTest[0] >1")
            correctedTimeList = np.concatenate((_correct_timestamps(timestamps[0:repeatTest[0][1]]),
                                                _correct_timestamps(timestamps[repeatTest[0][1]:len(timestamps)])))
        else:
            correctedTimeList = _correct_timestamps(timeList)
        assert len(photonList_resID) == len(timeList), 'Timestamp list does not match length of photon list!'
        correctedTimeListMaster[resIDBoundaryInds[resIDInd]:resIDBoundaryInds[resIDInd + 1]] = correctedTimeList

    assert len(photonList) == len(correctedTimeListMaster), 'Timestamp list does not match length of photon list!'
    assert correctedTimeListMaster.ndim == 1, 'correctedTimeListMaster is not flat'
    photonTable.modify_column(column=correctedTimeListMaster, colname='Time')
    photonTable.flush()
    hfile.close()
