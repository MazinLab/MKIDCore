import numpy as np
from datetime import datetime
import copy
import os
from glob import glob
import json
from astropy.io.fits import Card, Header

from mkidcore.corelog import getLogger
import mkidcore.config
from astropy.time import Time
from astropy.time import TimezoneInfo
import astropy.units as u
from datetime import datetime
import pkg_resources as pkg

_metadata = {}


class KeyInfo(object):
    def __init__(self, **kwargs):
        kwargs['name']=kwargs.pop('fits_card')
        self.__dict__.update(kwargs)

    @property
    def fits_card(self):
        return Card(keyword=self.name, value=self.default, comment=self.description)

import csv
def parse_mec_keys():
    with open(pkg.resource_filename('mkidcore','mec_keys.csv')) as f:
        data = [row for row in csv.reader(f)]

    data=[{k.strip().lower().replace(' ','_').replace('?','') :v.strip() for k,v in zip(data[0],l)} for l in data[1:]]
    for k in data:
        if k['type'].lower().startswith('f'):
            try:
                k['default'] = float(k['default'])
            except:
                pass
        for kk in ('from_tcs','from_mec', 'from_observer', 'from_pipeline', 'ignore_changes_during_data_capture',
                   'required_by_pipeline'):
            k[kk] = bool(k[kk])
        k['has_source'] = int(k['has_source'])
        k['fits_card'] = k['fits_card'].upper()

    return {k['fits_card']: KeyInfo(**k) for k in data}

MEC_KEY_INFO = parse_mec_keys()

DEFAULT_CARDSET = {k: v.fits_card for k,v in MEC_KEY_INFO.items()}


def build_header(metadata=None):
    """ Build a header with all of the keys and their default values with optional updates via metadata. Additional
    novel cards may be included via metadata as well.

    metadata is a dict of keyword:value|Card pairs. Value for keys in the default cardset, Cards for novel keywords.

    raises ValueError if any novel keyword is not a Card
    """
    if metadata is not None:
        unix_start = metadata['UNIXSTR']
        unix_stop = metadata['UNIXEND']
        TIME_KEYS = ('HST-END', 'HST-STR', 'MJD-END', 'MJD-STR', 'UT-END', 'UT-STR')
        if not unix_start and not unix_stop:
            assert [metadata[key] is not None for key in TIME_KEYS], 'header must contain UNIXSTR, UNIXEND or all of {}'.format(TIME_KEYS)
        else:
            hst = TimezoneInfo(utc_offset=-10*u.hour)
            t1 = Time(unix_start, format='unix')
            t2 = Time(unix_stop, format='unix')
            dt1 = datetime.fromtimestamp(t1.value, tz=hst)
            dt2 = datetime.fromtimestamp(t2.value, tz=hst)
            metadata['HST-END'] = '{:02d}:{:02d}:{:02d}.{:02d}'.format(dt2.hour, dt2.day, dt2.second, dt2.microsecond)
            metadata['HST-STR'] = '{:02d}:{:02d}:{:02d}.{:02d}'.format(dt1.hour, dt1.day, dt1.second, dt1.microsecond)
            metadata['MJD-END'] = t2.mjd
            metadata['MJD-STR'] = t1.mjd
            metadata['UT-END'] = t2.iso[-12:-1]
            metadata['UT-STR'] = t1.iso[-12:-1]

    novel = set(metadata.keys()).difference(set(DEFAULT_CARDSET.keys()))
    bad = [k for k in novel if not isinstance(metadata[k], Card)]
    if bad:
        raise ValueError('Keys {} are not known and must be passed as astropy.io.fits.Card'.format(bad))

    cardset = copy.deepcopy(DEFAULT_CARDSET)
    if metadata is not None:
        for k in metadata:
            try:
                cardset[k].value = metadata[k]
            except KeyError:
                cardset[k] = metadata[k]

    return Header(cardset.values())


def validate_metadata_dict(md, warn=True, error=False):
    missing = []
    for k in DEFAULT_CARDSET:
        if k not in md:
            missing.append(k)
    if warn and missing:
        getLogger(__name__).warning('Key(s) {} missing from {}'.format(str(missing), md))
    if error and missing:
        raise KeyError('Missing keys: {}'.format(str(missing)))

    return len(missing) != 0


def observing_metadata_for_timerange(start, duration, metadata_source=None):
    """
    Metadata that goes into an H5 consists of records within the duration

    requires metadata_source be an indexable iterable with an attribute utc pointing to a datetime
    """
    if not metadata_source:
        metadata_source = load_observing_metadata() #TODO load_observing_metadata requires a path
    # Select the nearest metadata to the midpoint
    start = datetime.fromtimestamp(start)
    time_since_start = np.array([(md.utc - start).total_seconds() for md in metadata_source])
    ok, = np.where((time_since_start < duration.duration) & (time_since_start >= 0))
    mdl = [metadata_source[i] for i in ok]
    for k in DEFAULT_CARDSET:
        {k:v if k.static else }
    return mdl


def parse_obslog(file):
    """Return a list of configthings for each record in the observing log filterable on the .utc attribute"""
    with open(file, 'r') as f:
        lines = f.readlines()
    ret = []
    for l in lines:
        ct = mkidcore.config.ConfigThing(json.loads(l).items())
        ct.register('utc', datetime.strptime(ct.utc, "%Y%m%d%H%M%S"), update=True)
        ret.append(ct)
    return ret


def load_observing_metadata(path, files=tuple(), use_cache=True):
    """Return a list of mkidcore.config.ConfigThings with the contents of the metadata from observing log files"""
    global _metadata

    # _metadata is a dict of file: parsed_file records
    files = set(files)
    if path:
        files.update(glob(os.path.join(path, 'obslog*.json')))

    if use_cache:
        for f in files:
            if f not in _metadata:
                _metadata[f] = parse_obslog(f)
        metad = _metadata
    else:
        metad = {f: parse_obslog(f) for f in files}

    metadata = []
    for f in files:
        metadata += metad[f]

    return metadata


class MetadataSeries(object):
    def __init__(self, times, values):
        self.times = times
        self.values = values

    def get(self, timestamp, preceeding=True):
        if timestamp is None:
            return self.values[0]

        delta = self.times - timestamp
        try:
            return self.values[delta < 0][-1] if preceeding else self.values[np.abs(delta).argmin()]
        except IndexError:
            raise ValueError(f'No metadata available for {timestamp}, records from '
                             f'{self.values.min()} to {self.values.max()}')


def build_wcs(md, times, ref_pixels, derotate=True, naxis=2):
    """Build WCS from a metadata dictonary, must have keys for ra, dec (or simbad target), dither positions, reference,
    platescale, observatory
     """
    from astropy.coordinates import SkyCoord
    import astropy
    import astropy.wcs as wcs
    import astropy.units as u
    from astroplan import Observer
    try:
        coord = SkyCoord(md['RA'], md['Dec'], md['EQUINOX'], unit=('hourangle', 'deg'))
    except KeyError:
        coord = None

    if coord is None:
        try:
            coord = SkyCoord.from_name(md['OBJECT'])
        except astropy.coordinates.name_resolve.NameResolveError:
            getLogger(__name__).warning('Insufficient data to build a WCS solution')
            return None

    try:
        apo = Observer.at_site(md['OBSERVAT'])
        devang = np.deg2rad(md['M_DEVANG'])
        platescale = md['M_PLTSCL']  # units should be mas/pix
    except KeyError:
        getLogger(__name__).warning('Insufficient data to build a WCS solution')
        return None

    pa = apo.parallactic_angle(times, coord).value  # radians
    corrected_sky_angles = -(pa + devang) if derotate else np.full_like(times, fill_value=devang)

    out = []
    for ca, ref_pixel in zip(corrected_sky_angles, ref_pixels):
        x = wcs.WCS(naxis=naxis)
        x.wcs.crpix[:2] = ref_pixel
        x.wcs.crval[:2] = [coord.ra.deg, coord.dec.deg]
        x.wcs.ctype[:2] = ["RA--TAN", "DEC-TAN"]
        x.wcs.pc[:2, :2] = np.array([[np.cos(ca), -np.sin(ca)],
                                     [np.sin(ca), np.cos(ca)]])
        x.wcs.cdelt[:2] = [platescale.to(u.arcsec).value, platescale.to(u.arcsec).value]
        x.wcs.cunit[:2] = ["deg", "deg"]
        out.append(x)
    return out
