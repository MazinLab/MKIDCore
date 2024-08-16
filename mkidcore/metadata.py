import numpy as np
from datetime import datetime
import copy
import os
from glob import glob
import json
import pkg_resources as pkg
import csv
from bisect import bisect
from collections import defaultdict

import astropy
from astropy.io.fits import Card, Header
from astropy.time import Time, TimezoneInfo
import astropy.units as u
from astropy.coordinates import SkyCoord
import astropy.wcs as wcs
from mkidcore.utils import astropy_observer
from mkidcore.corelog import getLogger

MEC_TIME_KEYS = ('HST-END', 'HST-STR', 'MJD-END', 'MJD-STR', 'UT-END', 'UT-STR')
XKID_TIME_KEYS = ('MJD', 'MJD-END', 'MJD-STR', 'UNIXEND', 'UNIXSTR', 'UT', 'UT-END', 'UT-STR')
TIME_KEYS = MEC_TIME_KEYS
PIPELINE_KEYS = ('E_BASELI', 'E_BMAP', 'E_CFGHSH', 'E_FLTCAL', 'E_GITHSH', 'E_H5FILE',
                 'E_SPECAL', 'E_WAVCAL', 'E_WCSCAL')

_FITS_STD = ('BSCALE', 'BUNIT', 'BZERO', 'CDELT', 'CRPIX', 'CRVAL', 'CTYPE', 'CUNIT', 'PC')

_LEGACY_OBSLOG_MAP = {"comment": "comment", "el": "ALTITUDE", "equinox": "EQUINOX", "utctcs": "UT",
                      "tcs-utc": "UT", "az": "AZIMUTH",
                      "instrument": "INSTRUME", "device_orientation": "E_DEVANG", "ra": "RA", "airmass": "AIRMASS",
                      "dither_pos": ("E_CONEXX", "E_CONEXY"), "dither_ref": ("E_CXREFX", "E_CXREFY"),
                      "parallactic": 'D_IMRPAD',
                      'd_imrpad': 'D_IMRPAD', "ut": "UT",
                      # NB these two keys were updated in readout so they may be present here
                      "ha": None, "utc": "UTC-STR", "observatory": "OBSERVAT", "laser": None, "target": "OBJECT",
                      "filter": "E_FLTPOS", "dither_home": ("E_PREFX", "E_PREFY"), "platescale": "E_PLTSCL",
                      "flipper": "E_FLPPOS", "dec": "DEC"}


class MetadataSeries(object):
    def __init__(self, times=None, values=None):
        if bool(times) ^ bool(values):
            raise ValueError("Either both or neither times and values must be passed")
        self.times = list(times) if times else []
        self.values = list(values) if values else []

    def is_empty(self):
        return len(self.values) == 0

    def add(self, time, value):
        """Caution will happily overwrite duplicate times"""
        ndx = bisect(self.times, time)
        if ndx != 0 and self.times[ndx - 1] == time:
            getLogger(__name__).debug("Replacing {} with {} at {}".format(self.values[ndx - 1], value, time))
            self.values[ndx - 1] = value
        else:
            self.times.insert(ndx, time)
            self.values.insert(ndx, value)

    def __iadd__(self, other):
        """ Replaces any existing times """
        if not other.times:
            return self
        if not self.times:
            self.times.extend(other.times)
            self.values.extend(other.values)
        if max(other.times) <= min(self.times):
            self.times[0:0] = other.times
            self.values[0:0] = other.values
        elif min(other.times) >= max(self.times):
            self.times.extend(other.times)
            self.values.extend(other.values)
        else:
            cur = {k: v for k, v in zip(self.times, self.values)}
            cur.update({k: v for k, v in zip(other.times, other.values)})
            self.times, self.values = map(list, zip(*sorted(cur.items())))
        return self

    def get(self, timestamp, preceeding=True):
        if not self.times:
            raise ValueError('No metadata available for {}'.format(timestamp))

        if timestamp is None:
            return self.values[0]

        delta = np.asarray(self.times) - timestamp
        try:
            return np.asarray(self.values)[delta < 0][-1] if preceeding else self.values[np.abs(delta).argmin()]
        except IndexError:
            raise ValueError('No metadata available for {}, records from '.format(timestamp) +
                             '{} to {}'.format(min(self.times), max(self.times)))

    def range(self, time, duration):
        """
        Selects a range of values, one prior record is always included if extant, an empty series if there are no
        records  prior.
        Raises ValueError if there are times but no values or value but no times. If this happens something is weird!

        Only unique values are returned
        """
        t = np.asarray(self.times)
        use = (t >= time) & (t <= time + duration)
        if use.any():
            preceeding_ndx = np.argwhere(use).min() - 1
            if preceeding_ndx > 0:
                use[preceeding_ndx] = True
            times, values = list(t[use]), list(np.asarray(self.values)[use])
        else:
            if time > max(self.times):
                times = [self.times[len(self.times) - 1]]
                values = [self.values[len(self.times) - 1]]
            else:
                times, values = [], []

        i = 1
        while i < len(values) - 1:
            if values[i] == values[i - 1]:
                times.pop(i)
                values.pop(i)
            else:
                i += 1

        return MetadataSeries(times, values)

    @property
    def domain(self):
        return (min(self.times), max(self.times)) if self.times else None


class KeyInfo(object):
    def __init__(self, **kwargs):
        kwargs['name'] = kwargs.pop('fits_card')
        for k in kwargs:
            try:
                kwargs[k] = kwargs[k].strip()
            except:
                pass
        self.__dict__.update(kwargs)

    @property
    def fits_card(self):
        return Card(keyword=self.name, value=self.default, comment=self.description)


def _parse_inst_keys(csv_file):
    """ spaces to _ ? to null strip whitespace, keys are column 0 values are dict of other columns
    all keys forced to lower case
    """
    with open(pkg.resource_filename('mkidcore', csv_file)) as f:
        data = [row for row in csv.reader(f)]
    data = [{k.strip().lower().replace(' ', '_').replace('?', ''): v.strip() for k, v in zip(data[0], l)} for l in
            data[1:]]
    for k in data:
        k['default'] = k['default'].strip()
        if k['type'].lower().startswith('f'):
            try:
                k['default'] = float(k['default'])
            except:
                pass
        if k['type'].lower().startswith('i'):
            try:
                k['default'] = int(k['default'])
            except:
                pass
        for kk in ('from_tcs', 'from_instrument', 'from_observer',
                   'from_pipeline', 'ignore_changes_during_data_capture',
                   'required_by_pipeline'):
            k[kk] = k[kk] == '1'
        k['has_source'] = int(k['has_source'])
        k['fits_card'] = k['fits_card'].upper()

    return {k['fits_card']: KeyInfo(**k) for k in data if k['fits_card'] not in _FITS_STD}


def mec_time_builder(unix_start, unix_stop, metadata):
    hst = TimezoneInfo(utc_offset=-10 * u.hour)
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
    return metadata


def xkid_time_builder(unix_start, unix_stop, metadata):
    t1 = Time(unix_start, format='unix')
    t2 = Time(unix_stop, format='unix')
    tmid = Time((unix_stop + unix_start) / 2, format='unix')
    metadata['MJD-END'] = t2.mjd
    metadata['MJD-STR'] = t1.mjd
    metadata['MJD'] = tmid.mjd
    metadata['UT-END'] = t2.iso[-12:-1]
    metadata['UT-STR'] = t1.iso[-12:-1]
    metadata['UT'] = tmid.iso[-12:-1]
    metadata['DATE-OBS'] = t1.strftime('%Y-%m-%d')
    return metadata

MEC_KEY_INFO = _parse_inst_keys('mec_keys.csv')
XKID_KEY_INFO = _parse_inst_keys('xkid_keys.csv')
XKID_REDIS_TO_FITS = {v.redis_key: v.name for v in XKID_KEY_INFO.values() if v.redis_key != '.'}
DEFAULT_MEC_CARDSET = {k: v.fits_card for k, v in MEC_KEY_INFO.items()}
DEFAULT_XKID_CARDSET = {k: v.fits_card for k, v in XKID_KEY_INFO.items()}
DEFAULT_CARDSET = DEFAULT_MEC_CARDSET
_metadata = {'files': [], 'data': defaultdict(MetadataSeries)}

INSTRUMENT_KEY_MAP = {
    'mec': {'time': MEC_TIME_KEYS,
            'keys': MEC_KEY_INFO,
            'card': DEFAULT_MEC_CARDSET,
            'builder': mec_time_builder,
            'wcs':{'RA': 'D_IMRRA', 'DEC': 'D_IMRDEC','ANG': 'D_IMRPAD'}},
    'xkid': {'time': XKID_TIME_KEYS,
             'keys': XKID_KEY_INFO,
             'card': DEFAULT_XKID_CARDSET,
             'builder': xkid_time_builder,
             'wcs':{'RA': 'RA', 'DEC': 'DEC'}}}


def _process_legacy_record(rdict):
    """Returns a dict with modern keys and values from a legacy obslog record"""
    dat = {}
    for k, v in rdict.items():
        newkey = _LEGACY_OBSLOG_MAP.get(k, None) or MEC_KEY_INFO.get(k.upper(), None)
        if isinstance(newkey, KeyInfo):
            newkey = newkey.name
        if not newkey:
            continue
        if not isinstance(newkey, tuple):
            newkey = [newkey]
            v = [v]
        for kk, vv in zip(newkey, v):
            dat[kk] = vv
    return dat


def parse_obslog(file, instrument='mec'):
    """
    File consists of a series of JSON dicts in time.
    Translate them into a dict of MetadataSeries with a subset of all the keys (only listed keys included).
    Both legacy and modern formats are supported. Legacy formats will have unused values silently dropped
    """
    with open(file, 'r') as f:
        lines = f.readlines()
    key_info = INSTRUMENT_KEY_MAP[instrument]['keys']
    dat = {}
    for l in lines:
        ldict = json.loads(l)
        if 'device_orientation' in l:
            ldict = _process_legacy_record(ldict)
        if 'OBSERVAT' in l:
            ldict['TELESCOP'] = ldict['OBSERVAT']
        from datetime import timezone
        try:
            t = ldict['UTC-STR']
            fmt = "%Y%m%d%H%M%S"
        except KeyError:
            t = (ldict['DATE-OBS'] + ldict['UT-STR'])
            fmt = "%Y-%m-%d%H:%M:%S.%f"
        utc = datetime.strptime(t, fmt).replace(tzinfo=timezone.utc)
        def typer(k, v):
            if k not in key_info:
                return v
            try:
                t = key_info[k].type.lower()[0]
            except IndexError:
                t = None
            if t=='f':
                t=float
            elif t=='i':
                t=int
            else:
                t=str
            try:
                return t(v)
            except:
                return v
        for k, v in ldict.items():
            k = k.upper()
            if k not in key_info:
                getLogger(__name__).debug('"{}" is not a known key, ignoring.'.format(k))
            if k == 'EXPTIME':
                getLogger(__name__).debug('"{}" will be save as a singular value and not a series.'.format(k))
                continue
            try:
                dat[k].add(utc.timestamp(), typer(k, v))
            except KeyError:
                dat[k] = MetadataSeries(times=[utc.timestamp()], values=[typer(k, v)])
    return dat


def load_observing_metadata(path='', files=tuple(), use_cache=True, instrument='mec'):
    """Return a list of mkidcore.config.ConfigThings with the contents of the metadata from observing log files"""
    global _metadata
    instrument=instrument.lower()
    # _metadata is a dict of file: parsed_file records
    files = set(files)
    if path:
        files.update(glob(os.path.join(path, 'obslog*.json')))

    if use_cache:
        md = _metadata['data']
        parsed = _metadata['files']
    else:
        md = defaultdict(MetadataSeries)
        parsed = []

    for f in files:
        if f not in parsed:
            try:
                recs = parse_obslog(f, instrument=instrument)
            except PermissionError:
                getLogger(__name__).warning('Insufficient permissions: {}. Skipping.'.format(f))
                continue
            except IOError as e:
                getLogger(__name__).warning('IOError: {}. Skipping.'.format(f))
                continue

            for k, v in recs.items():
                md[k] += v
            parsed.append(f)
    return md


def validate_metadata_dict(md, warn='all', error=False, allow_missing=tuple(), instrument='mec'):
    """ warn and error can be set to 'all'/True, 'required', 'none'/False
    place keys in allow_missing if it is ok that they aren't present."""
    missing, missing_required = [], []
    instrument = instrument.lower()
    for k in INSTRUMENT_KEY_MAP[instrument]['keys']:
        if k not in md and k not in allow_missing:
            missing.append(k)
            if INSTRUMENT_KEY_MAP[instrument]['keys'][k].required_by_pipeline:
                missing_required.append(k)
    if warn in (True, 'all') and missing:
        getLogger(__name__).warning('Key(s) {} missing'.format(str(missing)))
    elif warn == 'required' and missing_required:
        getLogger(__name__).warning('Required key(s) {} missing'.format(str(missing_required)))
    if error in (True, 'all') and missing:
        raise KeyError('Missing keys: {}'.format(str(missing)))
    elif error == 'required' and missing_required:
        raise KeyError('Missing keys: {}'.format(str(missing_required)))
    return len(missing) != 0


def observing_metadata_for_timerange(start, duration, metadata_source=None, instrument='mec'):
    """
    Metadata that goes into an H5 consists of records within the duration

    requires metadata_source be an indexable iterable with an attribute utc pointing to a datetime

    Returns a dictionary of MetadataSeries

    Does not include defaults key values (they do not have times).
    """
    if isinstance(metadata_source, str):
        metadata_source = load_observing_metadata(metadata_source, instrument=instrument)

    ret = {}
    missing = []
    for k, v in metadata_source.items():
        try:
            ret[k] = v.range(start, duration)
        except ValueError:
            missing.append(k)
    if missing:
        raise ValueError('No metadata for {:.0f} ({:.0f}s):\n\t'.format(start, duration) +
                         '\n\t'.join(missing))
    return ret


def build_header(metadata=None, unknown_keys='error', use_simbad=True, KEY_INFO=MEC_KEY_INFO,
                 DEFAULT_CARDSET=DEFAULT_CARDSET, TIME_KEYS=MEC_TIME_KEYS, TIME_KEY_BUILDER=mec_time_builder):
    """ Build a header with all of the keys and their default values with optional updates via metadata. Additional
    novel cards may be included via metadata as well.

    unknow_keys='create' may be used to hack in keys during testing

    metadata is a dict of keyword:value|Card pairs. Value for keys in the default cardset, Cards for novel keywords.

    raises ValueError if any novel keyword is not a Card
    """
    if metadata is not None:
        unix_start = metadata['UNIXSTR']
        unix_stop = metadata['UNIXEND']
        if not unix_start and not unix_stop:
            assert [metadata[key] is not None for key in
                    TIME_KEYS], 'header must contain UNIXSTR, UNIXEND or all of {}'.format(TIME_KEYS)
        else:
            metadata = TIME_KEY_BUILDER(unix_start, unix_stop, metadata)

        if 'OBJECT' in metadata and ('RA' not in metadata or 'DEC' not in metadata) and use_simbad:
            getLogger(__name__).info('Fetching coordinates from simbad')
            try:
                sc = SkyCoord.from_name(metadata['OBJECT']).transform_to(frame=astropy.coordinates.FK5(equinox='J2000'))
                metadata.update({'RA': sc.ra.hourangle, 'DEC': sc.dec.deg, 'EQUINOX': 'J2000', 'EPOCH': 'J2000'})
            except Exception:
                getLogger(__name__).warning('Unable to get coordinates for {}'.format(metadata['OBJECT']))
        elif 'RA' not in metadata or 'DEC' not in metadata:
            metadata['RA'] = 0.0
            metadata['DEC'] = 0.0
            metadata['EQUINOX'] = 'J2000'
            metadata['EPOCH'] = 'J2000'

    try:
        metadata['EQUINOX'] = metadata['EPOCH']
    except KeyError:
        pass

    try:
        metadata['EPOCH'] = metadata['EQUINOX']
    except KeyError:
        pass

    try:
        telescope = metadata['TELESCOP']
    except KeyError:
        telescope = None
        pass

    try:
        observat = metadata['OBSERVAT']
    except KeyError:
        observat = None
        pass

    if telescope and not telescope.startswith('#'):
        metadata['OBSERVAT'] = telescope
    if observat and not observat.startswith('#'):
        metadata['TELESCOP'] = observat

    novel = set(metadata.keys()).difference(set(DEFAULT_CARDSET.keys()))
    bad = [k for k in novel if not isinstance(metadata[k], Card)]
    if bad:
        msg = 'Keys {} are not known and must be passed as astropy.io.fits.Card'.format(bad)
        unknown_keys = unknown_keys.lower()
        if unknown_keys == 'error':
            raise ValueError(msg)
        elif unknown_keys == 'warn':
            getLogger(__name__).warning(msg + ' for inclusion.')
        elif unknown_keys == 'create':
            for k in bad:
                metadata[k] = Card(keyword=k, value=metadata[k], comment='No Description')
            bad = []
        for k in bad:
            metadata.pop(k)

    cardset = copy.deepcopy(DEFAULT_CARDSET)
    if metadata is not None:
        for k in metadata:
            try:
                val = metadata[k].to(KEY_INFO[k].unit).value
            except AttributeError:
                val = metadata[k]
            except ValueError:
                getLogger(__name__).debug(
                    'Unit {} not supported by astropy - using raw value'.format(MEC_KEY_INFO[k].unit))
                val = metadata[k].value
            try:
                cardset[k].value = val
            except KeyError:
                cardset[k] = val

    return Header(cardset.values())


def skycoord_from_metadata(md, force_simbad=False):
    if not force_simbad:
        try:
            eq = str(md['EQUINOX'])
            if eq[0].isdigit():
                getLogger(__name__).info('Assuming equinox {} is Julian'.format(eq))
                eq = 'J' + eq
            wcskeys = INSTRUMENT_KEY_MAP[md['INSTRUME'].lower()]['wcs']
            return SkyCoord(md[wcskeys['RA']], md[wcskeys['DEC']], equinox=eq, unit=('hourangle', 'deg'))
        except (KeyError, ValueError) as e:
            pass
    try:
        if not force_simbad:
            getLogger(__name__).info('Using SIMBAD to find coordinates of {}'.format(md["OBJECT"]))
        return SkyCoord.from_name(md['OBJECT']).transform_to(frame=astropy.coordinates.FK5(equinox='J2000'))
    except astropy.coordinates.name_resolve.NameResolveError:
        raise KeyError('Unable resolve {} via SIMBAD and no RA/Dec/Equinox provided'.format(md["OBJECT"]))
    except KeyError:
        pass
    raise KeyError('Neither RA/DEC/EQUINOX nor OBJECT specified')


def build_wcs(md, times, ref_pixels, shape, subtract_parallactic=True, cubeaxis=None):
    """
    Build WCS from a metadata dictionary, must have keys RA, Dec EQUINOX or OBJECT (for simbad target), TELESCOP,
    E_DEVANG, and E_PLTSCL. ref_pixels may be an iterable of reference pixels, set naxis to three for an (uninitialized)
    3rd axis

    The WCS PC matrix corrects for the device rotation angle and, if subtract_parallactic is set, the PA.
    """

    try:
        coord = skycoord_from_metadata(md)
    except KeyError as e:
        getLogger(__name__).warning('Insufficient data to build a WCS solution, {}'.format(e))
        return None

    try:
        __, apo = astropy_observer(md['TELESCOP'])
        devang = np.deg2rad(md['E_DEVANG'])
        platescale = md['E_PLTSCL']  # units should be mas/pix
    except KeyError:
        getLogger(__name__).warning('Insufficient data to build a WCS solution, missing instrument info')
        return None

    corrected_sky_angles = np.full_like(times, fill_value=-devang)
    if subtract_parallactic:
        corrected_sky_angles -= apo.parallactic_angle(times, coord).value  # radians

    try:
        scale = [platescale.to(u.deg).value] * 2
    except AttributeError:
        if platescale > 1:
            ps = (platescale * u.mas).to(u.deg).value
        elif platescale > .0001:
            ps = (platescale * u.arcsec).to(u.deg).value
        elif platescale < 1e-5:
            ps = platescale
        else:
            getLogger(__name__).error(f'Platescale {platescale} not in recognizable format')
        scale = [ps] * 2

    out = []

    wcs_dict = {'CTYPE1': 'RA--TAN', 'CUNIT1': 'deg', 'CDELT1': scale[0], 'CRPIX1': None, 'CRVAL1': coord.ra.deg,
                'NAXIS1': shape[0],
                'CTYPE2': 'DEC-TAN', 'CUNIT2': 'deg', 'CDELT2': scale[1], 'CRPIX2': None, 'CRVAL2': coord.dec.deg,
                'NAXIS2': shape[1]}

    if cubeaxis:
        wcs_dict.update(cubeaxis)

    for ca, ref_pixel in zip(corrected_sky_angles, ref_pixels):
        wcs_dict['CRPIX1'] = ref_pixel[0]
        wcs_dict['CRPIX2'] = ref_pixel[1]
        x = wcs.WCS(wcs_dict)
        x.wcs.pc[:2, :2] = np.array([[np.cos(ca), -np.sin(ca)],
                                     [np.sin(ca), np.cos(ca)]])
        out.append(x)
    return out
