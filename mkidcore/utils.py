import os.path
from functools import wraps
import inspect
import multiprocessing as mp
from logging import getLogger
import ast
from glob import glob
from datetime import datetime
import numpy as np
import astropy
from astroplan import Observer
_manager = None

# dict of path roots each a dict with where keys are the night start time and values are dictss
# obslogs (list of obslog files), ditherlogs (list of dither log files), bindir (the bin dir)
# dithers, if present is a parsed collection of the dither log files
_datadircache = {}


def astropy_observer(telescope):
    """wrapper for astroplan.Observer and astropy.coordinates.EarthLocation"""
    if telescope.lower() == 'clay':
        telescope = 'LAS CAMPANAS OBSERVATORY'
    else:
        telescope = telescope
    site = astropy.coordinates.EarthLocation.of_site(telescope)
    apo = Observer.at_site(telescope)
    return site, apo

def next_second(x: datetime):
    """Return the next second"""
    x = round(x.hour * 3600 + x.minute * 60 + x.second + x.microsecond + .5)
    if x >= 24 * 3600:
        x = 0
    return x


def mjd_to(mjd, zone):
    from astropy.time import Time
    from pytz import timezone
    return Time(mjd, format='mjd').to_datetime(timezone=timezone(zone))


def parse_dither(file):
    parsed_log = {}
    with open(file, 'r') as f:
        lines = f.readlines()
    for i, l in enumerate(lines):
        if not l.strip().startswith('starts'):
            continue
        try:
            assert lines[i + 1].strip().startswith('ends') and lines[i + 2].strip().startswith('path')
            starts = ast.literal_eval(l.partition('=')[2])
            ends = ast.literal_eval(lines[i + 1].partition('=')[2])
            pos = ast.literal_eval(lines[i + 2].partition('=')[2])
        except (AssertionError, IndexError, ValueError, SyntaxError):
            # Bad dither
            getLogger(__name__).error('Dither l{}:{} corrupt'.format(i - 1, lines[i - 1]))
            continue
        parsed_log[(min(starts), max(ends))] = starts, ends, pos
    return parsed_log


def manager(*args, **kwargs):
    """Get a singleton of the multiprocessing manager"""
    global _manager
    if _manager is None:
        _manager = mp.Manager(*args, **kwargs)
    return _manager


def query(question, yes_or_no=False, default="no"):
    """
    Ask a question via raw_input() and return their answer.
    "question" is a string that is presented to the user.
    "yes_or_no" specifies if it is a yes or no question
    "default" is the presumed answer if the user just hits <Enter>.
    It must be "yes" (the default), "no" or None (meaning an answer is required of
    the user). Only used if yes_or_no=True.
    The "answer" return value is the user input for a general question. For a yes or
    no question it is True for "yes" and False for "no".
    """
    if yes_or_no:
        valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if not yes_or_no:
        prompt = ""
        default = None
    elif default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)
    while True:
        print(question + prompt)
        choice = input().lower()
        if not yes_or_no:
            return choice
        elif default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' (or 'y' or 'n').")


def freeze(cls, msg="Class {cls} is frozen. Cannot set {key} = {value}"):
    """Wrap and freeze a class so that a=A(); a.foo=4 fails if .foo isn't defined by the class """
    cls.__frozen = False

    def frozensetattr(self, key, value):
        if self.__frozen and not hasattr(self, key):
            raise AttributeError(msg.format(cls=cls.__name__, key=key, value=value))
        else:
            object.__setattr__(self, key, value)

    def init_decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            func(self, *args, **kwargs)
            self.__frozen = True

        return wrapper

    cls.__setattr__ = frozensetattr
    cls.__init__ = init_decorator(cls.__init__)

    return cls


def caller_name(skip=2):
    """Get a name of a caller in the format module.class.method

       `skip` specifies how many levels of stack to skip while getting caller
       name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

       An empty string is returned if skipped levels exceed stack height
    """
    stack = inspect.stack()
    start = 0 + skip
    if len(stack) < start + 1:
        return ''
    parentframe = stack[start][0]

    name = []
    module = inspect.getmodule(parentframe)
    # `modname` can be None when frame is executed directly in console
    if module:
        name.append(module.__name__)
    # detect classname
    if 'self' in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        #      be just a function call
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':  # top level usually
        name.append(codename)  # function or a method
    del parentframe
    return ".".join(name)


def derangify(s, delim=','):
    """
    Takes a range in form of "a-b" and generate a list of numbers between
    a and b inclusive.
    Also accepts comma separated ranges like "a-b,c-d,f" will build a
    list which will include
    Numbers from a to b, a to d and f
    http://code.activestate.com/recipes/577279-generate-list-of-
    numbers-from-hyphenated-and-comma/
    """
    s = "".join(s.split())  # removes white space
    r = set()
    for x in s.split(delim):
        t = x.split('-')
        if len(t) not in [1, 2]:
            raise SyntaxError("'{}'".format(s) +
                              "does not seem to be derangeifyable")
        if len(t) == 1:
            r.add(int(t[0]))
        else:
            r.update(set(range(int(t[0]), int(t[1]) + 1)))
    l = list(r)
    l.sort()
    return tuple(l)


def parse_datadir(path):
    """Look through a data directory and return paths for nights, logs, and obslogs"""
    pathdata = {}
    date = ''
    for d in (d for d in glob(os.path.join(path, '*')) if os.path.isdir(d)):
        night = os.path.relpath(d, path)
        try:
            date = datetime.strptime(night, '%Y%m%d')
        except ValueError:
            pass
        if not date:
            try:
                date = datetime.strptime(night, 'ut%Y%m%d')
            except ValueError:
                getLogger(__name__).debug('Skipping {}'.format(d))
                continue
        obslogs = glob(os.path.join(d, 'logs', 'obslog*.json'))
        ditherlogs = glob(os.path.join(d, 'logs', 'dither*.log'))
        if os.path.exists(os.path.join(d, 'bin')):
            d = os.path.join(d, 'bin')
            bin = glob(os.path.join(d, '*.bin'))
        else:
            bin = glob(os.path.join(d, '*.bin'))
        if not bin:
            if obslogs or ditherlogs:
                getLogger(__name__).warning('No binfiles in {} despite presence of logs'.format(d))
            continue
        times = np.array(list(map(lambda x: int(os.path.splitext(os.path.basename(x))[0]), bin)))
        nmin = times.min()
        pathdata[nmin] = dict(obslogs=obslogs, ditherlogs=ditherlogs, bindir=d)

    return pathdata


def get_ditherdata_for_time(base, start):
    global _datadircache
    try:
        pathdata = _datadircache[base]
    except KeyError:
        pathdata = _datadircache[base] = parse_datadir(base)

    keys = np.array(list(pathdata.keys()))
    try:
        nightdata = pathdata[keys[keys < start].max()]
    except ValueError:
        raise ValueError('No directory in {} found for start {}'.format(base, start))

    try:
        nightdata['dithers']
    except KeyError:
        nightdata['dithers'] = {}
        for f in nightdata['ditherlogs']:
            nightdata['dithers'].update(parse_dither(f))

    try:
        start = start.timestamp()
    except AttributeError:
        pass

    for (t0, t1), v in nightdata['dithers'].items():
        if t0 - (t1 - t0) <= start <= t1:
            return v
    raise ValueError('No dither found for time {}'.format(start))


def get_bindir_for_time(base, start):
    global _datadircache
    try:
        pathdata = _datadircache[base]
    except:
        pathdata = _datadircache[base] = parse_datadir(base)

    keys = np.array(list(pathdata.keys()))
    try:
        return pathdata[keys[keys < start].max()]['bindir']
    except ValueError:
        raise ValueError('No directory in {} found for start {}'.format(base, start))


def get_obslogs(base, start=None):
    """If start time is passed only obslogs files for that night will be returned"""
    global _datadircache
    try:
        pathdata = _datadircache[base]
    except:
        pathdata = _datadircache[base] = parse_datadir(base)

    if not start:
        nightdata = pathdata.values()
    else:
        keys = np.array(list(pathdata.keys()))
        try:
            nightdata = [pathdata[keys[keys < start].max()]]
        except ValueError:
            raise ValueError('No directory in {} found for start {}'.format(base, start))

    return [l for n in nightdata for l in n['obslogs']]


def find_clock_offsets(olog_data, dither, timezone=True, timezone_shift=7):
    """
    Takes in data from an obslog as a dict of {'key':<mkidcore.metadata.MetadataSeries>} and an
    <mkidppipeline.definitions.MKIDDither> object to find any discrepancies in the clock synchronization
    between when the CONEX mirror was moved (from the obslog data) and when the dither believes that step in the
    sequence occurred.
    If timezone==True, <timezone_shift> hours (PT = UTC-7:00) will be subtracted from the UNIX timestamps
    that are pulled from the obslog data. This stems from an issue where it is converted to a UNIX timestamp twice and
    BOTH times, an assumption is made that the timestamp is in local time which causes a discrepancy of 7 hours between
    the timestamps from the obslog metadataseries and the time of observation.

    Returns a list of offsets from the start of the corresponding dither step to when the conex moved.
    """

    def find_conex_time_from_dither_step(olog_xs, olog_ys, olog_ts, dither_step):
        """
        Takes in a list of conex x and y positions, a corresponding list of times, and a single dither step
         <mkidppipeline.definitions.MKIDDither>.obs[step_number]

        Returns the difference between the timestep that the conex logged is move at and the start of the dither step.
        If the conex moved before the step started this will be negative,
        if the conex moved after the step started, it will be positive
        """
        dither_x = dither_step.dither_pos[0]
        dither_y = dither_step.dither_pos[1]

        same_place_mask = (olog_xs == dither_x) & (olog_ys == dither_y)

        conex_move_times = olog_ts[same_place_mask]

        time_difference = abs(conex_move_times - dither_step.start)
        closest_time = conex_move_times[time_difference == time_difference.min()]

        return float(closest_time - dither_step.start)

    conex_x_metadata = olog_data['E_CONEXX'].values
    conex_y_metadata = olog_data['E_CONEXY'].values
    if timezone:
        conex_timestamps = np.array(olog_data['E_CONEXX'].times) - timezone_shift * 3600
    else:
        conex_timestamps = np.array(olog_data['E_CONEXX'].times)

    offsets = [find_conex_time_from_dither_step(conex_x_metadata,
                                                conex_y_metadata,
                                                conex_timestamps,
                                                frame) for frame in dither.obs]

    return offsets
