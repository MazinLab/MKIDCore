import errno
import logging
import logging.config
import os
import sys

import yaml
from multiprocessing_logging import install_mp_handler
try:
    import coloredlogs
except ImportError:
    pass

# import progressbar
# progressbar.streams.wrap_stderr()

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


def getLogger(*args, **kwargs):
    setup = kwargs.pop('setup', False)
    if setup:
        setup_logging(**kwargs)
    kwargs.pop('logfile', None)
    kwargs.pop('configfile',None)
    kwargs.pop('env_key',None)
    log = logging.getLogger(*args, **kwargs)
    if not setup:
        log.addHandler(logging.NullHandler())
    return log


_setup = False


def mkdir_p(path):
    """http://stackoverflow.com/a/600612/190597 (tzot)"""
    if not path:
        return
    try:
        os.makedirs(path, exist_ok=True)  # Python>3.2
    except TypeError:
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise


class MakeFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=0):
        mkdir_p(os.path.dirname(filename))
        logging.FileHandler.__init__(self, filename, mode, encoding, delay)


def setup_logging(configfile='', env_key='MKID_LOG_CONFIG', logfile=None, **kwargs):
    """Setup logging configuration"""
    global _setup
    if _setup:
        return
    _setup = True
    value = os.getenv(env_key, '')
    path = configfile if os.path.exists(configfile) else value
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), 'corelog.yaml')

    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f.read())
        if logfile:
            config['handlers']['file']['filename'] = logfile
        logging.config.dictConfig(config)
    except:
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger()
        logger.error('Could not load log config file "{}" failing back to basicConfig'.format(path),
                     exc_info=True)

    try:
        coloredlogs.install()
    except NameError:
        pass
    logging.captureWarnings(True)
    install_mp_handler()
    logging.getLogger('matplotlib').setLevel(logging.INFO)


def create_log(name, logfile='', console=True, mpsafe=True, propagate=False,
               fmt='%(asctime)s %(levelname)s %(message)s (pid=%(process)d)',
               level=logging.DEBUG, stdout=True):

    log = logging.getLogger(name)
    if logfile:
        handler = MakeFileHandler(logfile)
        handler.setFormatter(logging.Formatter(fmt))
        handler.setLevel(level)
        log.addHandler(handler)
    else:
        logging.getLogger().debug('not adding file handler to {}'.format(name))

    if console and not len(list(filter(lambda h: type(h) == logging.StreamHandler, log.handlers))):
        handler = logging.StreamHandler(sys.stdout if stdout else sys.stderr)
        handler.setFormatter(logging.Formatter(fmt))
        handler.setLevel(level)
        log.addHandler(handler)
    else:
        logging.getLogger().debug('not adding console handler to {}'.format(name))

    log.setLevel(level)
    log.propagate = propagate


    import multiprocessing
    logger = multiprocessing.log_to_stderr()
    logger.setLevel(multiprocessing.SUBDEBUG)

    if mpsafe:
        install_mp_handler(logger=log)

    return log
